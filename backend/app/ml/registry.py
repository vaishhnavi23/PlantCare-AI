"""Loads models once, keeps the ensemble consistent and runs predictions."""
from __future__ import annotations

import logging
import threading

import numpy as np

from ..config import Settings
from .ensemble import MemberOutput, aggregate
from .labels import canon
from .members import HFResNet50Member, ModelUnavailable, load_bundles

log = logging.getLogger("plantcare.models")


def _reorder(out: MemberOutput, classes: list) -> MemberOutput:
    """Re-order a member's probabilities to the reference class order (matching by canonical name)."""
    idx = {canon(c): i for i, c in enumerate(out.classes)}
    probs = np.array([out.probs[idx[canon(c)]] for c in classes])
    return MemberOutput(out.name, classes, probs)


class ModelRegistry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.Lock()
        self._loaded = False
        self.members: list = []
        self.skipped: list[str] = []
        self.error: str | None = None
        self.reference_classes: list = []

    # -- loading -----------------------------------------------------------------
    def inject(self, members: list) -> None:
        """Used by tests / custom setups to supply ready-made members."""
        self.members = list(members)
        self.reference_classes = list(members[0].classes) if members else []
        self._loaded, self.error = True, None

    def load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            members: list = []
            try:
                members.append(HFResNet50Member(self.settings.model_id))
            except ModelUnavailable as exc:
                self.error = str(exc)
                log.error("Primary model unavailable: %s", exc)
            try:
                bundles, problems = load_bundles(self.settings.model_dir)
            except Exception as exc:
                bundles, problems = [], [f"joblib/scikit-learn error: {exc}"]
            self.skipped.extend(problems)
            members.extend(bundles)
            if members:
                self.reference_classes = list(members[0].classes)
                compatible = []
                for m in members:
                    if sorted(map(canon, m.classes)) == sorted(map(canon, self.reference_classes)):
                        compatible.append(m)
                    else:
                        self.skipped.append(f"{m.name}: class list differs from {members[0].name}; not used in the ensemble.")
                self.members = compatible
                self.error = None if compatible else self.error
            self._loaded = True

    @property
    def available(self) -> bool:
        return bool(self.members)

    def ensure(self) -> None:
        if not self._loaded:
            self.load()
        if not self.members:
            raise ModelUnavailable(self.error or "No disease-detection model is available.")

    # -- inference ---------------------------------------------------------------
    def predict(self, image) -> dict:
        self.ensure()
        outs, failures = [], []
        for m in self.members:
            try:
                outs.append(_reorder(m.predict(image), self.reference_classes))
            except Exception as exc:
                log.exception("Member %s failed", m.name)
                failures.append(f"{m.name}: {exc}")
        if not outs:
            raise ModelUnavailable("All models failed to produce a prediction.")
        result = aggregate(outs, low_conf=self.settings.low_confidence)
        result["failed_members"] = failures
        result["models_used"] = [o.name for o in outs]
        return result

    def primary_cnn(self):
        for m in self.members:
            if getattr(m, "kind", "") == "end_to_end":
                return m
        return None

    def status(self) -> dict:
        return {
            "loaded": self._loaded, "available": self.available, "error": self.error, "skipped": self.skipped,
            "models": [m.name for m in self.members], "classes": len(self.reference_classes),
        }
