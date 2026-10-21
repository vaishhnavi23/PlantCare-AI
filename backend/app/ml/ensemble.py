"""Combine member classifiers by soft voting (mean of class probabilities) and judge agreement."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class MemberOutput:
    name: str
    classes: list
    probs: np.ndarray  # shape (n_classes,), sums to ~1


def aggregate(outputs: list[MemberOutput], low_conf: float = 0.60, margin_min: float = 0.10, top_k: int = 3) -> dict:
    """All outputs must share the same class list (the registry guarantees this).

    Returns the ensemble top-k, each member's own top prediction, an agreement fraction and
    the reasons (if any) the result should be treated as uncertain or conflicting.
    """
    if not outputs:
        raise ValueError("No model outputs to aggregate.")
    classes = outputs[0].classes
    mean = np.mean([o.probs for o in outputs], axis=0)
    order = np.argsort(mean)[::-1]
    top = [{"label": classes[i], "probability": float(mean[i])} for i in order[:top_k]]
    best = int(order[0])
    members = []
    agree = 0
    for o in outputs:
        i = int(np.argmax(o.probs))
        agree += int(i == best)
        members.append({"name": o.name, "label": classes[i], "probability": float(o.probs[i])})
    agreement = agree / len(outputs)
    margin = float(mean[order[0]] - mean[order[1]]) if len(order) > 1 else 1.0

    reasons, status = [], "ok"
    if len(outputs) > 1 and agreement < 0.67:
        status = "conflict"
        reasons.append(f"The models disagree: only {agree} of {len(outputs)} chose the combined result.")
    if float(mean[best]) < low_conf:
        status = status if status == "conflict" else "uncertain"
        reasons.append(f"Low model confidence ({mean[best] * 100:.0f}% is below the {low_conf * 100:.0f}% threshold).")
    elif margin < margin_min:
        status = status if status == "conflict" else "uncertain"
        reasons.append("The top two candidate classes are very close.")
    return {"top": top, "members": members, "agreement": agreement, "margin": margin, "status": status, "reasons": reasons,
            "label": classes[best], "probability": float(mean[best])}
