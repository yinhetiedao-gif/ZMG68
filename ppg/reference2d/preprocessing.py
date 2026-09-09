from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .models import PreprocessConfig, PreprocessedImage, ReferenceImage


def _otsu(values: np.ndarray) -> float:
    histogram, _ = np.histogram(values, bins=256, range=(0.0, 1.0))
    total = values.size
    cumulative = np.cumsum(histogram)
    means = np.cumsum(histogram * np.arange(256))
    whole = means[-1]
    denominator = cumulative * (total - cumulative)
    score = np.divide((means * total - whole * cumulative) ** 2, denominator, out=np.zeros(256, float), where=denominator > 0)
    return float((int(np.argmax(score)) + 0.5) / 256.0)


def _morphology(mask: np.ndarray, config: PreprocessConfig) -> np.ndarray:
    size = int(config.morphology_kernel)
    if size <= 0 or config.morphology == "none":
        return mask
    size = max(3, size | 1)
    image = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    iterations = max(1, int(config.morphology_iterations))
    for _ in range(iterations):
        if config.morphology in ("erosion", "opening"):
            image = image.filter(ImageFilter.MinFilter(size))
        if config.morphology in ("dilation", "closing"):
            image = image.filter(ImageFilter.MaxFilter(size))
    if config.morphology == "opening":
        image = image.filter(ImageFilter.MaxFilter(size))
    elif config.morphology == "closing":
        image = image.filter(ImageFilter.MinFilter(size))
    return np.asarray(image, dtype=np.uint8) > 127


def preprocess_reference(reference: ReferenceImage, config: PreprocessConfig | None = None) -> PreprocessedImage:
    config = config or PreprocessConfig()
    image = reference.image.convert("L")
    if config.gamma > 0 and abs(config.gamma - 1.0) > 1e-3:
        image = image.point(lambda value: int(max(0, min(255, (value / 255.0) ** (1.0 / config.gamma) * 255.0))))
    if config.contrast > 0 and abs(config.contrast - 1.0) > 1e-3:
        image = ImageEnhance.Contrast(image).enhance(config.contrast)
    if config.blur > 0:
        image = image.filter(ImageFilter.GaussianBlur(float(config.blur)))
    if config.median_size and config.median_size >= 3:
        image = image.filter(ImageFilter.MedianFilter(max(3, int(config.median_size) | 1)))
    image = ImageOps.autocontrast(image)
    grayscale = np.asarray(image, dtype=np.float32) / 255.0
    if config.threshold_method == "global":
        threshold = max(0.0, min(1.0, float(config.threshold)))
        binary = grayscale < threshold
    elif config.threshold_method.startswith("adaptive"):
        block = max(3, int(config.adaptive_block_size) | 1)
        local = Image.fromarray((grayscale * 255).astype(np.uint8), mode="L").filter(ImageFilter.BoxBlur(block // 2))
        local_array = np.asarray(local, dtype=np.float32) / 255.0
        binary = grayscale < (local_array - float(config.adaptive_c))
        threshold = float(np.mean(local_array))
    else:
        threshold = _otsu(grayscale)
        binary = grayscale < threshold
    if config.invert:
        binary = ~binary
    binary = _morphology(binary, config)
    if config.min_area > 1:
        # 小组件过滤在检测器中按连通域执行；这里保留 mask 原貌，避免破坏空间场。
        binary = np.asarray(binary, dtype=bool)
    return PreprocessedImage(grayscale, binary, threshold, config)
