"""Label helpers shared by the models, the disease library and the API."""
from __future__ import annotations

import re

# The 38 PlantVillage classes the existing ResNet50 model is documented to output.
# The live class list is read from the model config at load time and takes precedence.
PLANTVILLAGE_CLASSES = [
    "Apple___Apple_scab", "Apple___Black_rot", "Apple___Cedar_apple_rust", "Apple___healthy",
    "Blueberry___healthy", "Cherry_(including_sour)___Powdery_mildew", "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot", "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight", "Corn_(maize)___healthy", "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)", "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)", "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)", "Peach___Bacterial_spot", "Peach___healthy",
    "Pepper,_bell___Bacterial_spot", "Pepper,_bell___healthy", "Potato___Early_blight",
    "Potato___Late_blight", "Potato___healthy", "Raspberry___healthy", "Soybean___healthy",
    "Squash___Powdery_mildew", "Strawberry___Leaf_scorch", "Strawberry___healthy",
    "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight", "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot", "Tomato___Spider_mites Two-spotted_spider_mite", "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus", "Tomato___healthy",
]


def canon(label: str) -> str:
    """Canonical key: lower-case, every non-alphanumeric run -> '_' (robust to spaces/underscore variants)."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def split_label(label: str) -> tuple[str, str]:
    crop, _, disease = label.partition("___")
    if not disease:
        crop, disease = "Plant", label
    clean = lambda s: re.sub(r"\s+", " ", s.replace("_", " ")).strip()
    return clean(crop).replace(" (including sour)", "").replace(" bell", " (bell)").replace("Pepper, (bell)", "Pepper (bell)"), clean(disease)


def is_healthy(label: str) -> bool:
    return "healthy" in label.lower()


def display(label: str) -> str:
    crop, disease = split_label(label)
    return f"{crop} {disease}".strip()
