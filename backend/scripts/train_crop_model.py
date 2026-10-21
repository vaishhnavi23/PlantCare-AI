r"""Train the crop-recommendation model (separate from the plant-disease models).

Dataset: the public "Crop Recommendation Dataset" (Kaggle, Atharva Ingle) - CSV with columns
N, P, K, temperature, humidity, ph, rainfall, label (22 crops, 100 rows each). Download it yourself
(Kaggle login required) and pass the CSV path. It is NOT bundled with this project.

    python scripts/train_crop_model.py --csv path\to\Crop_recommendation.csv

Writes models/crop_model.joblib. Metrics come from a stratified 80/20 hold-out split and 5-fold CV on the
training part, so they are offline results on this dataset only - not real-world field performance.
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


def train(df: pd.DataFrame, source: str = "unknown", seed: int = 42) -> dict:
    missing = [c for c in FEATURES + ["label"] if c not in df.columns]
    if missing:
        raise SystemExit(f"CSV is missing columns: {missing}")
    df = df.dropna(subset=FEATURES + ["label"])
    X, y = df[FEATURES].astype(float), df["label"].astype(str)
    Xtr, Xte, ytr, yte = train_test_split(X.values, y.values, test_size=0.2, stratify=y, random_state=seed)
    model = RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=-1)
    cv = cross_val_score(model, Xtr, ytr, cv=StratifiedKFold(5, shuffle=True, random_state=seed), scoring="accuracy")
    model.fit(Xtr, ytr)
    pred = model.predict(Xte)
    return {
        "model": model, "features": FEATURES, "classes": list(model.classes_), "algorithm": "RandomForestClassifier (300 trees)",
        "ranges": {f: [float(X[f].min()), float(X[f].max())] for f in FEATURES},
        "importances": {f: float(v) for f, v in zip(FEATURES, model.feature_importances_)},
        "metrics": {"holdout_accuracy": float(accuracy_score(yte, pred)), "holdout_macro_f1": float(f1_score(yte, pred, average="macro")),
                    "cv_accuracy_mean": float(cv.mean()), "cv_accuracy_std": float(cv.std()), "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
                    "scope": "Offline results on the training dataset only; not real-world field performance."},
        "dataset": {"source": source, "rows": int(len(df)), "classes": int(y.nunique()), "trained_on": date.today().isoformat(),
                    "limitations": "Dataset is small, balanced and largely synthetic-looking; it does not cover soil type, season, variety, market or region."},
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "models" / "crop_model.joblib"))
    a = ap.parse_args()
    bundle = train(pd.read_csv(a.csv), source=Path(a.csv).name)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, a.out)
    m = bundle["metrics"]
    print(f"Saved {a.out}\nHold-out accuracy {m['holdout_accuracy']:.3f}, macro-F1 {m['holdout_macro_f1']:.3f}, CV {m['cv_accuracy_mean']:.3f}+/-{m['cv_accuracy_std']:.3f}")
