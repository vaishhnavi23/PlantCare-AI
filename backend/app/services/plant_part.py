"""Automatic plant-part classification (Leaf, Stem, Whole Crop).

This service classifies uploaded plant images into:
- leaf: Close-up single-leaf photo, suitable for the trained leaf disease classifier.
- stem: Close-up stem / stalk / branch photo (unvalidated prototype for disease classifier).
- whole_plant: Wide or medium shot of the entire crop or bush (unvalidated prototype).
- uncertain: Low-quality, ambiguous, or borderline images where plant part cannot be reliably determined.

Non-plant images (portraits of people, cartoons, vehicles, etc.) are rejected by validation.py
before reaching part classification or disease inference.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import TypedDict

import numpy as np
from PIL import Image
import scipy.ndimage as ndi

CLASSES = ["leaf", "stem", "whole_plant"]
LABELS = {"leaf": "Leaf", "stem": "Stem", "whole_plant": "Whole Crop", "uncertain": "Uncertain"}


class PartDetectionResult(TypedDict):
    plant_part: str
    label: str
    confidence: float
    probabilities: dict[str, float]
    supported_for_disease_model: bool
    message: str
    limitation_warning: str | None


def extract_part_features(img: Image.Image) -> dict[str, float]:
    """Extract geometric, color, and topological features for plant-part classification."""
    thumb = img.copy().convert("RGB")
    thumb.thumbnail((256, 256))
    w, h = thumb.size
    total_px = max(1, w * h)

    rgb = np.asarray(thumb, dtype=np.float32)
    gray = np.asarray(thumb.convert("L"), dtype=np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    hsv = np.asarray(thumb.convert("HSV"), dtype=np.float32)
    hue = hsv[..., 0] * 360.0 / 255.0
    sat = hsv[..., 1] / 255.0
    val = hsv[..., 2] / 255.0

    # 1. Foliar chlorophyll mask (healthy or chlorotic leaf tissue)
    foliar = (g > r + 12) & (g > b + 12) & (g >= 35) & (hue >= 35) & (hue <= 165)
    foliar_ratio = float(foliar.mean())

    # 2. Woody / stem / stalk mask (brown, tan, woody, or fibrous stalk)
    stem_col = (hue >= 10) & (hue <= 50) & (sat >= 0.12) & (val >= 0.08) & ~foliar
    stem_ratio = float(stem_col.mean())

    # 3. Foliar blobs (lamina connectivity vs fragmentation)
    clean_f = ndi.binary_opening(foliar, np.ones((3, 3)))
    labeled_f, num_f = ndi.label(clean_f)
    f_sizes = ndi.sum(clean_f, labeled_f, range(1, num_f + 1)) if num_f > 0 else []
    max_f_blob = float(max(f_sizes) / total_px) if len(f_sizes) > 0 else 0.0
    sig_f_blobs = sum(1 for s in f_sizes if s > total_px * 0.008)

    # 4. Stem connected components and elongation
    clean_s = ndi.binary_opening(stem_col, np.ones((3, 3)))
    labeled_s, num_s = ndi.label(clean_s)
    s_sizes = ndi.sum(clean_s, labeled_s, range(1, num_s + 1)) if num_s > 0 else []
    max_s_blob = float(max(s_sizes) / total_px) if len(s_sizes) > 0 else 0.0

    max_stem_elongation = 1.0
    if len(s_sizes) > 0 and max_s_blob > 0.015:
        max_idx = np.argmax(s_sizes) + 1
        ys, xs = np.where(labeled_s == max_idx)
        bh = ys.max() - ys.min() + 1
        bw = xs.max() - xs.min() + 1
        max_stem_elongation = float(max(bh / (bw + 1e-3), bw / (bh + 1e-3)))

    # 5. Background / environment ratio (soil, pot, ground, surroundings)
    bg_ratio = float(max(0.0, 1.0 - foliar_ratio - stem_ratio))

    # 6. Directional edge energy
    dy = np.abs(np.diff(gray, axis=0))
    dx = np.abs(np.diff(gray, axis=1))
    edge_ratio = float(dx.mean() / (dy.mean() + 1e-5))

    return {
        "foliar_ratio": foliar_ratio,
        "stem_ratio": stem_ratio,
        "max_f_blob": max_f_blob,
        "sig_f_blobs": sig_f_blobs,
        "max_s_blob": max_s_blob,
        "max_stem_elongation": max_stem_elongation,
        "bg_ratio": bg_ratio,
        "edge_ratio": edge_ratio,
    }


class PlantPartClassifier:
    """Classifies plant images into Leaf, Stem, or Whole Crop, with explicit uncertainty detection."""

    def __init__(self, bundle_path: Path | str | None = None):
        self.bundle_path = Path(bundle_path) if bundle_path else None
        self.model = None
        if self.bundle_path and self.bundle_path.exists():
            import joblib
            try:
                bundle = joblib.load(self.bundle_path)
                self.model = bundle.get("model")
            except Exception:
                self.model = None

    def classify(self, img: Image.Image) -> PartDetectionResult:
        f = extract_features_dict = extract_part_features(img)
        foliar = f["foliar_ratio"]
        stem = f["stem_ratio"]
        max_f = f["max_f_blob"]
        blobs = f["sig_f_blobs"]
        max_s = f["max_s_blob"]
        elong = f["max_stem_elongation"]
        bg = f["bg_ratio"]

        # Ambiguous / uncertain images:
        # If plant-like material is insufficient or ambiguous
        if foliar < 0.08 and stem < 0.08:
            return {
                "plant_part": "uncertain",
                "label": "Uncertain",
                "confidence": 0.33,
                "probabilities": {"leaf": 0.333, "stem": 0.333, "whole_plant": 0.333},
                "supported_for_disease_model": False,
                "message": "Plant part detection is uncertain. Little plant-like structure detected.",
                "limitation_warning": "Please upload a clearer close-up photo of the affected plant.",
            }

        # Multi-factor score evaluation
        leaf_score = 0.0
        stem_score = 0.0
        whole_score = 0.0

        # Whole crop check: multiple disconnected leaf clusters with ground / branches
        if blobs >= 4 and max_f < 0.25:
            whole_score += 4.0
        elif blobs >= 3 and max_f < 0.25 and (stem >= 0.15 or bg >= 0.30):
            whole_score += 3.0

        # Stem check: elongated stem component, or high stem color ratio without single leaf lamina
        if max_s >= 0.10 and elong >= 1.8 and max_f < 0.35:
            stem_score += 4.0
        elif stem >= 0.25 and elong >= 1.5 and max_f < 0.30:
            stem_score += 3.0
        elif max_s >= 0.15 and max_f < 0.25:
            stem_score += 2.5

        # Leaf check: single dominant foliar lamina
        if foliar >= 0.30 and max_f >= 0.22 and blobs <= 3:
            leaf_score += 4.0
        elif foliar >= 0.20 and max_f >= 0.18 and blobs <= 2:
            leaf_score += 3.0
        elif max_f >= 0.30:
            leaf_score += 2.5

        if stem < 0.10:
            leaf_score += 1.0

        scores = np.array([leaf_score, stem_score, whole_score])
        exp_s = np.exp(scores - scores.max())
        probs = exp_s / exp_s.sum()
        top_idx = int(np.argmax(probs))
        top_part = CLASSES[top_idx]
        top_prob = float(probs[top_idx])

        # If top probability is below confidence threshold or scores are too close, mark uncertain
        if top_prob < 0.55 or scores.max() < 1.5:
            return {
                "plant_part": "uncertain",
                "label": "Uncertain",
                "confidence": round(top_prob, 2),
                "probabilities": {c: round(float(p), 3) for c, p in zip(CLASSES, probs)},
                "supported_for_disease_model": False,
                "message": "Plant part detection is uncertain. Unable to clearly distinguish leaf, stem, or whole crop.",
                "limitation_warning": "Please upload a clearer close-up photo of the affected plant.",
            }

        limitation_warning = None
        if top_part != "leaf":
            limitation_warning = (
                "Limitation notice: The disease classification model was trained exclusively on "
                "single-leaf images and has not been validated for stem or whole-crop images. "
                "Prediction accuracy cannot be claimed or assumed for non-leaf parts; please confirm any symptoms with an agricultural expert."
            )

        return {
            "plant_part": top_part,
            "label": LABELS[top_part],
            "confidence": round(top_prob, 2),
            "probabilities": {c: round(float(p), 3) for c, p in zip(CLASSES, probs)},
            "supported_for_disease_model": (top_part == "leaf"),
            "message": f"Detected plant part: {LABELS[top_part]}",
            "limitation_warning": limitation_warning,
        }
