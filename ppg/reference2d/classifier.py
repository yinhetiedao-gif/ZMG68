from __future__ import annotations

import numpy as np

from .models import ClassificationResult, DotFeature, PreprocessedImage


def classify_image(preprocessed: PreprocessedImage, features: list[DotFeature]) -> ClassificationResult:
    grayscale = preprocessed.grayscale; mask = preprocessed.binary_mask
    if grayscale.std() < .045 or not np.any(mask):
        return ClassificationResult("UNKNOWN", (), .12)
    dots = [f for f in features if f.element_type == "dot"]
    lines = [f for f in features if f.element_type == "line"]
    dot_ratio = len(dots) / max(1, len(features)); line_ratio = len(lines) / max(1, len(features))
    size_values = np.asarray([f.diameter for f in dots], dtype=float)
    variable_size = float(np.std(size_values) / max(1e-6, np.mean(size_values))) if len(size_values) > 2 else 0.0
    secondaries = []
    if len(dots) >= 8 and dot_ratio >= .45:
        primary = "DOT"; confidence = min(.98, .55 + dot_ratio * .25 + min(.2, len(dots) / 5000))
        if variable_size > .22: secondaries.append("GRADIENT")
        if len(dots) >= 20: secondaries.append("GRID_OR_HALFTONE")
        if max(float(np.mean(mask)), 0.0) < .35: secondaries.append("MASKED")
    elif line_ratio >= .35:
        primary = "LINE"; confidence = min(.9, .45 + line_ratio * .4)
    elif grayscale.std() > .13 and len(features) < 8:
        primary = "GRAYSCALE"; confidence = .58
    else:
        primary = "MIXED"; confidence = .45
    return ClassificationResult(primary, tuple(secondaries), round(confidence, 4))
