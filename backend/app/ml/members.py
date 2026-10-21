"""Model members: the existing fine-tuned ResNet50 plus optional feature-extractor + SVM/RF bundles."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from . import features
from .ensemble import MemberOutput

log = logging.getLogger("plantcare.models")


class ModelUnavailable(RuntimeError):
    """No usable model could be loaded (missing dependency, weights or files)."""


class HFResNet50Member:
    """The project's original model: a fine-tuned ResNet50 classifier from Hugging Face (38 PlantVillage classes)."""

    kind = "end_to_end"

    def __init__(self, model_id: str):
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForImageClassification
        except ImportError as exc:
            raise ModelUnavailable(f"PyTorch/transformers are not installed ({exc.name}).") from exc
        try:
            self.processor = AutoImageProcessor.from_pretrained(model_id)
            self.model = AutoModelForImageClassification.from_pretrained(model_id)
        except Exception as exc:
            raise ModelUnavailable(
                f"Could not load '{model_id}'. The first run needs internet access to download it, or a populated Hugging Face cache.") from exc
        self.torch = torch
        self.device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device).eval()
        self.name = "ResNet50 (fine-tuned)"
        self.model_id = model_id
        id2label = self.model.config.id2label
        self.classes = [id2label[i] for i in sorted(id2label, key=int)]

    def predict(self, image) -> MemberOutput:
        inputs = {k: v.to(self.device) for k, v in self.processor(images=image.convert("RGB"), return_tensors="pt").items()}
        with self.torch.inference_mode():
            probs = self.torch.softmax(self.model(**inputs).logits, dim=-1)[0].cpu().numpy()
        return MemberOutput(self.name, self.classes, probs)


class FeatureClassifierMember:
    """CNN feature extractor (ResNet50 or MobileNetV2) + a scikit-learn SVM or Random Forest, loaded from a joblib bundle.

    Bundle keys: extractor, classifier, model (sklearn estimator/pipeline with predict_proba), classes, metrics (optional).
    """

    kind = "feature_classifier"

    def __init__(self, path: Path):
        import joblib

        bundle = joblib.load(path)
        for key in ("extractor", "classifier", "model", "classes"):
            if key not in bundle:
                raise ModelUnavailable(f"{path.name} is missing '{key}'.")
        if bundle["extractor"] not in features.EXTRACTORS:
            raise ModelUnavailable(f"{path.name}: unknown extractor '{bundle['extractor']}'.")
        if not hasattr(bundle["model"], "predict_proba"):
            raise ModelUnavailable(f"{path.name}: classifier cannot produce probabilities.")
        self.extractor = bundle["extractor"]
        self.estimator = bundle["model"]
        self.classes = list(bundle["classes"])
        self.metrics = bundle.get("metrics")
        pretty = {"resnet50": "ResNet50", "mobilenetv2": "MobileNetV2"}[self.extractor]
        self.name = f"{pretty} + {bundle['classifier']}"
        self.path = path

    def predict(self, image) -> MemberOutput:
        feats = features.extract([image], self.extractor)
        expected = getattr(self.estimator, "n_features_in_", feats.shape[1])
        if feats.shape[1] != expected:
            raise ModelUnavailable(f"{self.name}: feature size {feats.shape[1]} does not match the trained model ({expected}).")
        return MemberOutput(self.name, self.classes, self.estimator.predict_proba(feats)[0])


def load_bundles(model_dir: Path) -> tuple[list, list]:
    """Load every *.joblib bundle in model_dir. Returns (members, problems)."""
    members, problems = [], []
    for path in sorted(Path(model_dir).glob("*.joblib")):
        if path.name == "crop_model.joblib":
            continue
        try:
            members.append(FeatureClassifierMember(path))
        except Exception as exc:  # a bad artifact must not take the app down
            log.warning("Skipping %s: %s", path.name, exc)
            problems.append(f"{path.name}: {exc}")
    return members, problems
