
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
    """Reorder probabilities to the reference class order."""
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

    def inject(self, members: list) -> None:
        """Used by tests or custom setups to supply ready-made members."""
        self.members = list(members)
        self.reference_classes = list(members[0].classes) if members else []
        self._loaded = True
        self.error = None

    def load(self) -> None:
        with self._lock:
            if self._loaded:
                return

            members: list = []

            # Load the primary Hugging Face ResNet50 model.
            try:
                members.append(HFResNet50Member(self.settings.model_id))
                log.info("Primary model loaded: %s", self.settings.model_id)
            except ModelUnavailable as exc:
                self.error = str(exc)
                log.exception("Primary model unavailable: %s", exc)
            except Exception as exc:
                self.error = f"Unexpected model-loading error: {exc}"
                log.exception("Unexpected error loading primary model")

            # Load optional trained model bundles.
            try:
                bundles, problems = load_bundles(self.settings.model_dir)
            except Exception as exc:
                bundles = []
                problems = [f"joblib/scikit-learn error: {exc}"]
                log.exception("Failed to load model bundles")

            self.skipped.extend(problems)
            members.extend(bundles)

            if members:
                self.reference_classes = list(members[0].classes)
                compatible = []

                for member in members:
                    if sorted(map(canon, member.classes)) == sorted(
                        map(canon, self.reference_classes)
                    ):
                        compatible.append(member)
                    else:
                        message = (
                            f"{member.name}: class list differs from "
                            f"{members[0].name}; not used in the ensemble."
                        )
                        self.skipped.append(message)
                        log.warning(message)

                self.members = compatible
                if compatible:
                    self.error = None

            self._loaded = True

            if not self.members:
                log.error(
                    "No disease-detection model is available. "
                    "Model ID: %s; model directory: %s; skipped: %s",
                    self.settings.model_id,
                    self.settings.model_dir,
                    self.skipped,
                )

    @property
    def available(self) -> bool:
        return bool(self.members)

    def ensure(self) -> None:
        if not self._loaded:
            self.load()

        if not self.members:
            raise ModelUnavailable(
                self.error or "No disease-detection model is available."
            )

    def predict(self, image) -> dict:
        self.ensure()
        outputs, failures = [], []

        for member in self.members:
            try:
                outputs.append(
                    _reorder(member.predict(image), self.reference_classes)
                )
            except Exception as exc:
                log.exception("Member %s failed during prediction", member.name)
                failures.append(f"{member.name}: {exc}")

        if not outputs:
            raise ModelUnavailable(
                "All models failed to produce a prediction."
            )

        result = aggregate(
            outputs,
            low_conf=self.settings.low_confidence,
        )
        result["failed_members"] = failures
        result["models_used"] = [output.name for output in outputs]
        return result

    def primary_cnn(self):
        for member in self.members:
            if getattr(member, "kind", "") == "end_to_end":
                return member
        return None

    def status(self) -> dict:
        return {
            "loaded": self._loaded,
            "available": self.available,
            "error": self.error,
            "skipped": self.skipped,
            "models": [member.name for member in self.members],
            "classes": len(self.reference_classes),
        }
