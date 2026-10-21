import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.ml.ensemble import MemberOutput  # noqa: E402
from app.ml.registry import ModelRegistry  # noqa: E402
from app.services.crop import CropService  # noqa: E402

CLASSES = ["Apple___Black_rot", "Apple___healthy", "Tomato___Late_blight"]


class FakeMember:
    kind = "fake"

    def __init__(self, name="ResNet50 + SVM", probs=(0.92, 0.05, 0.03), classes=CLASSES, fail=False):
        self.name, self.probs, self.classes, self.fail = name, np.array(probs, dtype=float), list(classes), fail

    def predict(self, image):
        if self.fail:
            raise RuntimeError("boom")
        return MemberOutput(self.name, self.classes, self.probs)


def leaf_png(size=300, color=(40, 140, 50), fmt="PNG", seed=0):
    rng = np.random.default_rng(seed)
    base = np.array(color, dtype=np.float32)
    arr = np.clip(base + rng.normal(0, 35, (size, size, 3)), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, fmt)
    return buf.getvalue()


_CACHED_CROP_BUNDLE = None


def make_crop_bundle():
    global _CACHED_CROP_BUNDLE
    if _CACHED_CROP_BUNDLE is not None:
        return _CACHED_CROP_BUNDLE
    import train_crop_model as t
    rng = np.random.default_rng(0)
    rows = []
    centers = {"rice": (80, 45, 40, 24, 82, 6.4, 230), "maize": (78, 48, 20, 22, 65, 6.2, 85), "chickpea": (40, 68, 80, 19, 17, 7.3, 80)}
    for crop_name, c in centers.items():
        for _ in range(60):
            v = rng.normal(c, [6, 6, 6, 1.5, 4, 0.2, 12])
            rows.append(dict(zip(["N", "P", "K", "temperature", "humidity", "ph", "rainfall"], v), label=crop_name))
    _CACHED_CROP_BUNDLE = t.train(pd.DataFrame(rows), source="synthetic-test-data")
    return _CACHED_CROP_BUNDLE


@pytest.fixture()
def env(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", model_dir=tmp_path / "models", secret_key="test-secret-at-least-32-bytes-long-for-jwt-signing!")
    registry = ModelRegistry(settings)
    registry.inject([FakeMember()])
    crop = CropService(settings.model_dir)
    crop.inject(make_crop_bundle())
    app = create_app(settings, registry, crop)
    return type("Env", (), {"settings": settings, "registry": registry, "crop": crop, "app": app})


@pytest.fixture()
def client(env):
    return TestClient(env.app)


def register(client, email="a@example.com", name="Asha", password="Passw0rdX"):
    return client.post("/api/auth/register", json={"name": name, "email": email, "password": password})


@pytest.fixture()
def authed(client):
    assert register(client).status_code == 201
    return client


def upload(client, data=None, name="leaf.png", part="leaf"):
    return client.post("/api/predict", files={"file": (name, data if data is not None else leaf_png(), "image/png")}, data={"plant_part": part})
