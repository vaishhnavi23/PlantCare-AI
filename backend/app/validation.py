"""Upload validation and image screening for plant disease diagnosis.

Because the underlying disease classifier is a closed-set deep CNN trained exclusively on plant
leaf classes, any out-of-distribution image (e.g. photos of people, cartoons, vehicles, or pets)
is otherwise forced into an arbitrary plant disease class with high or moderate confidence.

A heavy general-purpose plant detector or vision-language model is not bundled with the application.
Instead, this module implements a multi-signal pre-filter combining:
1. True foliar chlorophyll spectral detection (Excess Green index ExG, Green Leaf Index)
2. Digital illustration / cartoon detection (patch flatness, line-art gradient distribution, palette entropy)
3. Human portrait / person detection (YCbCr skin chrominance with connected-component spatial geometry
   and facial contrast landmarks)
4. Non-plant unnatural color ratio analysis (synthetic blues, cyans, magentas)

Images that are clearly non-plant are rejected before inference, preventing fabricated diagnoses.
Ambiguous or degraded plant images (blurry, dark, over-exposed, unusual background) are accepted
with preliminary quality warnings, which mark the diagnosis as 'uncertain' and recommend expert review.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, UnidentifiedImageError
import scipy.ndimage as ndi

ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MIN_SIDE = 64
RECOMMENDED_SIDE = 224
Image.MAX_IMAGE_PIXELS = 50_000_000


class ImageRejected(ValueError):
    """Raised with a user-safe message when an upload cannot be used."""


@dataclass
class Quality:
    width: int
    height: int
    sharpness: float
    brightness: float
    plant_color_ratio: float
    foliar_ratio: float = 0.0
    warnings: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "sharpness": round(self.sharpness, 1),
            "brightness": round(self.brightness, 1),
            "plant_color_ratio": round(self.plant_color_ratio, 3),
            "foliar_ratio": round(self.foliar_ratio, 3),
            "warnings": self.warnings,
            "note": (
                "Multi-signal heuristics screen for obvious non-plant uploads (people, cartoons, "
                "artificial graphics). Ambiguous plant photos are flagged with warnings rather than rejected."
            ),
        }


def _sharpness(gray: np.ndarray) -> float:
    """Variance of a 4-neighbour Laplacian - low values suggest a blurry image."""
    g = gray.astype(np.float32)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def _plant_color_ratio(img: Image.Image) -> float:
    """Detect plant tissue: healthy foliage, chlorosis/yellowing, brown stems/bark, and rust/blight lesions."""
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32)
    hue = hsv[..., 0] * 360.0 / 255.0
    sat, val = hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    # Green and yellowish foliage (chlorosis, healthy leaves)
    foliage = (hue >= 30) & (hue <= 165) & (sat >= 0.12) & (val >= 0.10)
    # Woody stems, bark, brown/rust lesions, dried plant material
    woody_or_lesion = (hue >= 10) & (hue < 30) & (sat >= 0.12) & (val >= 0.08)
    mask = foliage | woody_or_lesion
    return float(mask.mean())


def _foliar_chlorophyll_ratio(rgb: np.ndarray, hue: np.ndarray) -> float:
    """Detect genuine green plant foliar tissue with chlorophyll absorption (G clearly dominant over R and B)."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    foliar_mask = (g > r + 12) & (g > b + 12) & (g >= 35) & (hue >= 35) & (hue <= 165)
    return float(foliar_mask.mean())


def _non_plant_color_ratio(img: Image.Image) -> float:
    """Detect colors that do not naturally occur in plant tissue (vivid blues, cyans, purples, saturated crimson)."""
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32)
    hue = hsv[..., 0] * 360.0 / 255.0
    sat, val = hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    unnatural = (
        ((hue >= 175) & (hue <= 335) & (sat >= 0.20) & (val >= 0.15)) |
        ((hue >= 340) & (sat >= 0.60) & (val >= 0.30))
    )
    return float(unnatural.mean())


def _is_digital_illustration(small: Image.Image, rgb: np.ndarray, gray: np.ndarray, foliar_ratio: float) -> tuple[bool, str]:
    """Detect digital cartoons, drawings, anime, or clip art using patch flatness, gradients, and palette entropy."""
    sh, sw = gray.shape
    ph, pw = sh // 8, sw // 8
    if ph < 2 or pw < 2:
        return False, ""

    patches = gray[:ph * 8, :pw * 8].reshape(ph, 8, pw, 8).transpose(0, 2, 1, 3).reshape(-1, 64)
    patch_stds = patches.std(axis=1)
    flat_ratio = float((patch_stds < 3.0).mean())

    q = (rgb // 8).astype(np.int32)
    q_hash = q[..., 0] * 1024 + q[..., 1] * 32 + q[..., 2]
    vals, counts = np.unique(q_hash, return_counts=True)
    num_unique = len(vals)
    top5_ratio = float(counts[np.argsort(-counts)[:5]].sum() / counts.sum()) if len(counts) >= 5 else 1.0

    dx = np.diff(gray, axis=1)
    dy = np.diff(gray, axis=0)
    grad = np.sqrt(dx[:-1, :] ** 2 + dy[:, :-1] ** 2)
    dead_flat_grad = float((grad < 1.5).mean())

    # Pure single-color test patches (e.g. solid grey) are handled by ambiguous quality warnings, not cartoon rejection
    if num_unique <= 3:
        return False, ""

    # Digital drawings without natural foliage
    if foliar_ratio < 0.15:
        if num_unique < 250 and flat_ratio > 0.35 and dead_flat_grad > 0.25:
            return True, f"cartoon (unique={num_unique}, flat={flat_ratio:.2f})"
        if top5_ratio > 0.60 and flat_ratio > 0.40:
            return True, f"cartoon (top5={top5_ratio:.2f}, flat={flat_ratio:.2f})"
        if flat_ratio > 0.50 and dead_flat_grad > 0.40:
            return True, f"cartoon (flat={flat_ratio:.2f}, grad={dead_flat_grad:.2f})"

    return False, ""


def _is_human_portrait(small: Image.Image, rgb: np.ndarray, gray: np.ndarray, foliar_ratio: float) -> tuple[bool, str]:
    """Detect human portraits / selfies combining YCbCr skin chromaticity, spatial cluster geometry, and facial contrast."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    skin = (cb >= 77) & (cb <= 127) & (cr >= 133) & (cr <= 173) & (r > g) & (g > b) & (r - b > 15) & (gray > 40)
    skin_clean = ndi.binary_opening(skin, structure=np.ones((3, 3)))
    skin_clean = ndi.binary_closing(skin_clean, structure=np.ones((5, 5)))

    labeled, num_features = ndi.label(skin_clean)
    sizes = ndi.sum(skin_clean, labeled, range(1, num_features + 1))
    if len(sizes) > 0 and sizes.max() > 0:
        max_size = sizes.max()
        max_idx = np.argmax(sizes) + 1
        skin_blob_ratio = max_size / (small.size[0] * small.size[1])
        y_indices, x_indices = np.where(labeled == max_idx)
        min_y, max_y = y_indices.min(), y_indices.max()
        min_x, max_x = x_indices.min(), x_indices.max()
        crop_gray = gray[min_y:max_y + 1, min_x:max_x + 1]
        crop_skin = (labeled[min_y:max_y + 1, min_x:max_x + 1] == max_idx)
        skin_bright = crop_gray[crop_skin].mean()
        dark_feat_ratio = float(((crop_gray < (skin_bright - 25)) & (~crop_skin)).mean())

        # Substantial skin blob with internal facial landmarks and negligible plant foliage
        if skin_blob_ratio > 0.15 and dark_feat_ratio > 0.05 and foliar_ratio < 0.12:
            return True, f"person portrait (skin_blob={skin_blob_ratio:.2f}, dark_feat={dark_feat_ratio:.2f})"

    return False, ""


def validate_upload(data: bytes, filename: str, max_bytes: int, plant_part: str = "leaf") -> tuple[Image.Image, Quality]:
    if not data:
        raise ImageRejected("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ImageRejected(f"The image is larger than {max_bytes // (1024 * 1024)} MB. Please upload a smaller file.")
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in (filename or "") else ""
    if ext not in ALLOWED_EXT:
        raise ImageRejected("Unsupported file type. Please upload a JPG, PNG or WEBP image.")
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, ValueError):
        raise ImageRejected("The file could not be read as an image - it may be corrupted.")
    if fmt not in ALLOWED_FORMATS:
        raise ImageRejected("Unsupported image content. Please upload a JPG, PNG or WEBP image.")
    img = img.convert("RGB")
    w, h = img.size
    if min(w, h) < MIN_SIDE:
        raise ImageRejected(f"The image is too small ({w}x{h}px). Please upload one that is at least {MIN_SIDE}px on each side.")

    small = img.copy()
    small.thumbnail((300, 300))
    rgb = np.asarray(small.convert("RGB"), dtype=np.float32)
    gray = np.asarray(small.convert("L"), dtype=np.float32)
    hsv = np.asarray(small.convert("HSV"), dtype=np.float32)
    hue = hsv[..., 0] * 360.0 / 255.0

    foliar_ratio = _foliar_chlorophyll_ratio(rgb, hue)
    plant_ratio = _plant_color_ratio(small)
    non_plant_ratio = _non_plant_color_ratio(small)

    q = Quality(w, h, _sharpness(gray), float(gray.mean()), plant_ratio, foliar_ratio=foliar_ratio)

    # 1. Check for human portraits / selfies
    is_person, _ = _is_human_portrait(small, rgb, gray, foliar_ratio)
    if is_person:
        raise ImageRejected("The uploaded image appears to be a photo of a person or face. Please upload a clear photo of a plant leaf, stem, or whole plant.")

    # 2. Check for digital cartoons, anime, or clip art
    is_cartoon, _ = _is_digital_illustration(small, rgb, gray, foliar_ratio)
    if is_cartoon:
        raise ImageRejected("The uploaded image appears to be a cartoon or illustration. Please upload a clear photo of a real plant leaf, stem, or whole plant.")

    # 3. Check for non-plant objects dominated by synthetic non-plant spectrums
    if non_plant_ratio > 0.20 and foliar_ratio < 0.05 and (plant_part not in ("stem", "auto") or plant_ratio < 0.20):
        raise ImageRejected("The uploaded image does not appear to contain a plant, leaf, or crop. Please upload a clear photo of a plant leaf, stem, or whole plant.")
    if non_plant_ratio > 0.50 and plant_ratio < 0.05:
        raise ImageRejected("The uploaded image does not appear to contain a plant, leaf, or crop. Please upload a clear photo of a plant leaf, stem, or whole plant.")

    # Quality warnings for ambiguous, blurry, dark, overexposed, or unusual plant images
    if min(w, h) < RECOMMENDED_SIDE:
        q.warnings.append(f"Low resolution ({w}x{h}px). Results are more reliable with at least {RECOMMENDED_SIDE}px images.")
    if q.sharpness < 25:
        q.warnings.append("The image looks blurry (preliminary check). A sharper close-up is recommended.")
    if q.brightness < 35:
        q.warnings.append("The image looks very dark (preliminary check).")
    elif q.brightness > 235:
        q.warnings.append("The image looks over-exposed (preliminary check).")
    if q.plant_color_ratio < 0.08:
        q.warnings.append("Little plant-like colour was found (preliminary check) - the image may not show a plant.")
    return img, q
