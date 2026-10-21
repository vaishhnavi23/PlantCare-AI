"""Disease library built from the classes the model supports. Reference text is kept apart from predictions."""
from __future__ import annotations

from .disease_info import get_disease_info, is_high_concern
from .ml.labels import PLANTVILLAGE_CLASSES, canon, display, is_healthy, split_label


def build_library(model_classes: list | None = None) -> list[dict]:
    """One entry per class. `detectable` is True only for classes the loaded model can actually output."""
    detectable = {canon(c) for c in (model_classes or [])}
    classes = list(model_classes) if model_classes else list(PLANTVILLAGE_CLASSES)
    entries = []
    for label in classes:
        crop, disease = split_label(label)
        info = get_disease_info(label)
        entries.append({
            "key": canon(label), "label": label, "crop": crop, "name": "Healthy" if is_healthy(label) else disease,
            "title": display(label), "status": info["status"], "symptoms": info["symptoms"], "causes": info["causes"],
            "risk_factors": info["risk_factors"], "prevention": info["prevention"], "treatment": info["treatment"],
            "pesticide": info["pesticide"], "has_specific_guide": info["has_specific_guide"],
            "high_concern": is_high_concern(label),
            "detectable": (canon(label) in detectable) if detectable else None,
        })
    return sorted(entries, key=lambda e: (e["crop"], e["name"] != "Healthy", e["name"]))
