"""ResNet50 / MobileNetV2 feature extraction (ImageNet weights) shared by training and inference.

The SVM / Random Forest classifiers are only valid with the exact preprocessing used here:
resize 256 -> centre-crop 224 -> ImageNet normalisation -> global-average-pooled features
(ResNet50: 2048-d, MobileNetV2: 1280-d). torch/torchvision are imported lazily.
"""
from __future__ import annotations

import numpy as np

EXTRACTORS = {"resnet50": 2048, "mobilenetv2": 1280}
_cache: dict = {}


def _load(name: str):
    if name in _cache:
        return _cache[name]
    import torch
    from torchvision import models, transforms

    if name == "resnet50":
        net = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
        net.fc = torch.nn.Identity()
    elif name == "mobilenetv2":
        base = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
        net = torch.nn.Sequential(base.features, torch.nn.AdaptiveAvgPool2d(1), torch.nn.Flatten())
    else:
        raise ValueError(f"Unknown extractor '{name}'")
    net.eval()
    tf = transforms.Compose([
        transforms.Resize(256), transforms.CenterCrop(224), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    _cache[name] = (net, tf)
    return _cache[name]


def extract(images: list, name: str) -> np.ndarray:
    """Return an (n, d) float32 feature matrix for a list of RGB PIL images."""
    import torch

    net, tf = _load(name)
    batch = torch.stack([tf(im.convert("RGB")) for im in images])
    with torch.inference_mode():
        feats = net(batch)
    return feats.reshape(len(images), -1).cpu().numpy().astype(np.float32)
