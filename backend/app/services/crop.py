"""Crop recommendation service - a SEPARATE tabular ML model (not the plant-disease classifier).

Expects a joblib bundle at models/crop_model.joblib created by scripts/train_crop_model.py:
  {model, features, classes, ranges, importances, metrics, dataset}
No model => the service reports itself unavailable; it never guesses.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger("plantcare.crop")

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
UNITS = {"N": "training-data scale", "P": "training-data scale", "K": "training-data scale",
         "temperature": "\u00b0C", "humidity": "% relative", "ph": "pH units", "rainfall": "mm"}
# Physical sanity limits (hard errors). Training-data ranges (soft warnings) come from the bundle.
HARD_LIMITS = {"N": (0, 500), "P": (0, 500), "K": (0, 500), "temperature": (-10, 60), "humidity": (0, 100), "ph": (0, 14), "rainfall": (0, 5000)}
LABELS = {"N": "Nitrogen", "P": "Phosphorus", "K": "Potassium", "temperature": "Temperature", "humidity": "Humidity", "ph": "Soil pH", "rainfall": "Rainfall"}


class CropUnavailable(RuntimeError):
    pass


class InputError(ValueError):
    pass


class CropService:
    def __init__(self, model_dir: Path):
        self.path = Path(model_dir) / "crop_model.joblib"
        self.bundle = None
        self.error: str | None = None
        self._tried = False

    def load(self):
        if self._tried:
            return
        self._tried = True
        if not self.path.exists():
            self.error = "No trained crop model found. Train one with scripts/train_crop_model.py (see README)."
            return
        try:
            import joblib
            b = joblib.load(self.path)
            if list(b["features"]) != FEATURES:
                raise ValueError("feature list does not match the app")
            self.bundle = b
        except Exception as exc:
            self.error = f"Crop model could not be loaded: {exc}"
            log.error(self.error)

    def inject(self, bundle):
        self.bundle, self._tried, self.error = bundle, True, None

    @property
    def available(self) -> bool:
        self.load()
        return self.bundle is not None

    def info(self) -> dict:
        self.load()
        out = {"available": self.available, "error": self.error, "features": FEATURES, "units": UNITS, "labels": LABELS, "limits": HARD_LIMITS}
        if self.bundle:
            out.update({"classes": list(self.bundle["classes"]), "ranges": self.bundle.get("ranges"), "metrics": self.bundle.get("metrics"),
                        "dataset": self.bundle.get("dataset")})
        return out

    def validate(self, raw: dict) -> dict:
        values = {}
        for f in FEATURES:
            if raw.get(f) in (None, ""):
                raise InputError(f"{LABELS[f]} is required.")
            try:
                v = float(raw[f])
            except (TypeError, ValueError):
                raise InputError(f"{LABELS[f]} must be a number.")
            lo, hi = HARD_LIMITS[f]
            if not np.isfinite(v) or v < lo or v > hi:
                raise InputError(f"{LABELS[f]} must be between {lo} and {hi} ({UNITS[f]}).")
            values[f] = v
        return values

    def recommend(self, raw: dict, top_k: int = 3) -> dict:
        self.load()
        if not self.bundle:
            raise CropUnavailable(self.error or "Crop model unavailable.")
        values = self.validate(raw)
        warnings = []
        for f, (lo, hi) in (self.bundle.get("ranges") or {}).items():
            if values[f] < lo or values[f] > hi:
                warnings.append(f"{LABELS[f]} ({values[f]:g}) is outside the range seen in the training data ({lo:g}-{hi:g}); the suggestion is less reliable.")
        x = np.array([[values[f] for f in FEATURES]])
        probs = self.bundle["model"].predict_proba(x)[0]
        classes = list(self.bundle["classes"])
        order = np.argsort(probs)[::-1][:top_k]
        ranked = [{"crop": classes[i], "probability": float(probs[i])} for i in order]
        imp = self.bundle.get("importances") or {}
        factors = sorted(({"feature": f, "label": LABELS[f], "value": values[f], "unit": UNITS[f], "importance": imp.get(f)} for f in FEATURES),
                         key=lambda d: -(d["importance"] or 0))
        return {"recommended": ranked[0]["crop"], "alternatives": ranked[1:], "inputs": values, "warnings": warnings, "factors": factors,
                "note": "Importances are global for the trained model, not a per-prediction explanation. Probabilities are model scores, not guarantees of yield.",
                "model_info": {"algorithm": self.bundle.get("algorithm", "RandomForest"), "dataset": self.bundle.get("dataset"), "metrics": self.bundle.get("metrics")}}
