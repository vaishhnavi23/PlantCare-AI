r"""Train the SVM / Random Forest disease classifiers on ResNet50 and MobileNetV2 features.

Needs PyTorch + torchvision and a PlantVillage-style folder: <data>/<ClassName>/*.jpg where the folder names
match the labels of the existing ResNet50 model (e.g. Apple___Black_rot) so they can join its ensemble.

    python scripts\train_feature_classifiers.py --data C:\data\PlantVillage --max-per-class 300

Produces models/<extractor>_<svm|rf>.joblib (up to 4 bundles) and models/evaluation.json with hold-out
metrics. These are offline test results on the dataset's own split, not real-world accuracy.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


def fit_and_score(Xtr, ytr, Xte, yte, classifier: str, seed: int = 42):
    if classifier == "SVM":
        est = make_pipeline(StandardScaler(), SVC(kernel="rbf", probability=True, random_state=seed))
    else:
        est = RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=-1)
    est.fit(Xtr, ytr)
    pred = est.predict(Xte)
    return est, {"accuracy": float(accuracy_score(yte, pred)), "macro_f1": float(f1_score(yte, pred, average="macro")), "n_test": int(len(yte))}


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from PIL import Image
    from app.ml import features

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "models"))
    ap.add_argument("--max-per-class", type=int, default=300)
    ap.add_argument("--batch", type=int, default=32)
    a = ap.parse_args()

    root = Path(a.data)
    classes = sorted(p.name for p in root.iterdir() if p.is_dir())
    paths, labels = [], []
    for c in classes:
        files = sorted(f for f in (root / c).iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png"})[: a.max_per_class]
        paths += files
        labels += [c] * len(files)
    print(f"{len(paths)} images, {len(classes)} classes")
    idx_tr, idx_te = train_test_split(np.arange(len(paths)), test_size=0.2, stratify=labels, random_state=42)
    y = np.array(labels)
    evaluation = {"dataset": str(root.name), "classes": len(classes), "trained_on": date.today().isoformat(),
                  "scope": "Offline hold-out results on this dataset's split; real-world photos usually score lower.", "models": []}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for ext in ("resnet50", "mobilenetv2"):
        feats = []
        for i in range(0, len(paths), a.batch):
            feats.append(features.extract([Image.open(p).convert("RGB") for p in paths[i:i + a.batch]], ext))
        X = np.vstack(feats)
        for clf in ("SVM", "RF"):
            est, m = fit_and_score(X[idx_tr], y[idx_tr], X[idx_te], y[idx_te], clf)
            name = {"resnet50": "ResNet50", "mobilenetv2": "MobileNetV2"}[ext] + " + " + clf
            joblib.dump({"extractor": ext, "classifier": clf, "model": est, "classes": list(est.classes_), "metrics": m}, out / f"{ext}_{clf.lower()}.joblib")
            evaluation["models"].append({"name": name, **m})
            print(name, m)
    (out / "evaluation.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
