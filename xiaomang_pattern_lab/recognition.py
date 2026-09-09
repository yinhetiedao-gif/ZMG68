"""Multi-scale dot recovery for semantic Pattern Lab imports.

The vector engine remains the authoritative Raster -> SVG implementation.  This
module is a narrow post-normalization recognizer used only to recover editable
dot primitives from a prepared binary image when a tracer emits a cubic path
instead of a ``<circle>``.  It deliberately works through PatternDocument and
does not depend on fixture names or preset data.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
from pathlib import Path
from statistics import median
from typing import Iterable

from PIL import Image

from ppg.foundation.models import CircleElement, EllipseElement, FilledRegionElement, PathElement, PatternDocument, new_element_id


@dataclass(frozen=True)
class DotCandidate:
    x: float
    y: float
    width: float
    height: float
    area: int
    perimeter: int
    circularity: float
    confidence: float
    scale: str

    @property
    def radius(self) -> float:
        return (self.width + self.height) / 4.0


@dataclass
class DotRecognitionReport:
    detected_count: int = 0
    matched_count: int = 0
    converted_path_count: int = 0
    annotated_region_count: int = 0
    materialized_count: int = 0
    rejected_count: int = 0
    scale_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "detected_count": self.detected_count,
            "matched_count": self.matched_count,
            "converted_path_count": self.converted_path_count,
            "annotated_region_count": self.annotated_region_count,
            "materialized_count": self.materialized_count,
            "rejected_count": self.rejected_count,
            "scale_counts": dict(self.scale_counts),
            "engine": "pattern-lab-multi-scale-dot-recognizer",
        }


class MultiScaleDotRecognizer:
    """Recognise separated black dots at small, medium and large scales.

    Components are collected once from the binary mask, classified in adaptive
    scale bands and merged by centre/bounds.  The scale bands avoid the old
    single global min-area rule: tiny dots are judged with a lower absolute
    area requirement while large dots are held to stronger roundness checks.
    """

    def __init__(self, foreground_threshold: int = 127):
        self.foreground_threshold = int(foreground_threshold)

    def detect(self, image_path: str) -> tuple[list[DotCandidate], DotRecognitionReport]:
        with Image.open(image_path) as image:
            grayscale = image.convert("L")
            width, height = grayscale.size
            pixels = list(grayscale.getdata())
        foreground = [value <= self.foreground_threshold for value in pixels]
        components = self._components(foreground, width, height)
        raw = [self._candidate(component, width, height) for component in components]
        raw = [candidate for candidate in raw if candidate is not None]
        report = DotRecognitionReport()
        if not raw:
            return [], report

        radii = [candidate.radius for candidate in raw]
        pivot_small = max(2.5, median(radii) * 0.78)
        pivot_large = max(pivot_small + 0.5, median(radii) * 1.35)
        by_scale: dict[str, list[DotCandidate]] = {"small": [], "medium": [], "large": []}
        for candidate in raw:
            scale = "small" if candidate.radius <= pivot_small else "large" if candidate.radius >= pivot_large else "medium"
            adjusted = DotCandidate(
                candidate.x, candidate.y, candidate.width, candidate.height,
                candidate.area, candidate.perimeter, candidate.circularity,
                candidate.confidence, scale,
            )
            if self._accept(adjusted):
                by_scale[scale].append(adjusted)
            else:
                report.rejected_count += 1
        merged = self._dedupe(item for values in by_scale.values() for item in values)
        report.detected_count = len(merged)
        report.scale_counts = {name: len(values) for name, values in by_scale.items()}
        return merged, report

    def enrich_document(self, document: PatternDocument, binary_image_path: str, *, materialize_missing: bool) -> DotRecognitionReport:
        candidates, report = self.detect(binary_image_path)
        unmatched = set(range(len(candidates)))
        replacements = []
        for element in document.elements:
            candidate_index = self._best_match(element, candidates, unmatched)
            if candidate_index is None:
                replacements.append(element)
                continue
            candidate = candidates[candidate_index]
            unmatched.remove(candidate_index)
            report.matched_count += 1
            hint = {
                "primitive_hint": "dot",
                "recognized_width": candidate.width,
                "recognized_height": candidate.height,
                "recognized_radius": candidate.radius,
                "source": "multi_scale_dot_recognizer",
                "source_confidence": round(candidate.confidence, 6),
                "recognition_scale": candidate.scale,
            }
            metadata = dict(element.metadata)
            metadata.update(hint)
            if isinstance(element, PathElement) and not isinstance(element, FilledRegionElement):
                cls = CircleElement if math.isclose(candidate.width, candidate.height, rel_tol=0.12, abs_tol=0.5) else EllipseElement
                replacements.append(cls(
                    id=element.id, x=candidate.x, y=candidate.y,
                    width=max(candidate.width, 0.01), height=max(candidate.height, 0.01),
                    rotation=element.rotation, visible=element.visible, style=dict(element.style),
                    group_id=element.group_id, metadata=metadata,
                ))
                report.converted_path_count += 1
            else:
                element.metadata = metadata
                replacements.append(element)
                if isinstance(element, FilledRegionElement):
                    report.annotated_region_count += 1

        if materialize_missing:
            for index in sorted(unmatched):
                candidate = candidates[index]
                cls = CircleElement if math.isclose(candidate.width, candidate.height, rel_tol=0.12, abs_tol=0.5) else EllipseElement
                replacements.append(cls(
                    id=new_element_id("detected-dot"), x=candidate.x, y=candidate.y,
                    width=max(candidate.width, 0.01), height=max(candidate.height, 0.01),
                    style={"fill": "#000000", "stroke": "none"},
                    metadata={
                        "primitive_hint": "dot", "source": "multi_scale_dot_recognizer",
                        "source_confidence": round(candidate.confidence, 6),
                        "recognition_scale": candidate.scale, "materialized_from_binary": True,
                    },
                ))
                report.materialized_count += 1
        document.elements = replacements
        document._sync_transforms()
        document.validate()
        document.metadata["dot_recognition"] = report.to_dict()
        return report

    @staticmethod
    def _components(foreground: list[bool], width: int, height: int) -> list[list[tuple[int, int]]]:
        visited = bytearray(width * height)
        components: list[list[tuple[int, int]]] = []
        for start in range(width * height):
            if visited[start] or not foreground[start]:
                continue
            visited[start] = 1
            queue = deque([start])
            points: list[tuple[int, int]] = []
            while queue:
                item = queue.popleft()
                x, y = item % width, item // width
                points.append((x, y))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            neighbour = ny * width + nx
                            if foreground[neighbour] and not visited[neighbour]:
                                visited[neighbour] = 1
                                queue.append(neighbour)
            components.append(points)
        return components

    @staticmethod
    def _candidate(points: list[tuple[int, int]], width: int, height: int) -> DotCandidate | None:
        area = len(points)
        if area < 3:
            return None
        xs, ys = zip(*points)
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        box_width, box_height = xmax - xmin + 1, ymax - ymin + 1
        aspect = min(box_width, box_height) / max(box_width, box_height)
        occupied = set(points)
        perimeter = sum(
            1
            for x, y in points
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (x + dx, y + dy) not in occupied
        )
        circularity = 4.0 * math.pi * area / max(perimeter * perimeter, 1)
        fill_ratio = area / float(box_width * box_height)
        roundness = min(1.0, circularity / 0.88)
        compactness = min(1.0, fill_ratio / (math.pi / 4.0))
        confidence = max(0.0, min(1.0, 0.44 * aspect + 0.36 * roundness + 0.20 * compactness))
        return DotCandidate(
            x=(xmin + xmax) / 2.0, y=(ymin + ymax) / 2.0,
            width=float(box_width), height=float(box_height), area=area,
            perimeter=perimeter, circularity=circularity, confidence=confidence, scale="",
        )

    @staticmethod
    def _accept(candidate: DotCandidate) -> bool:
        aspect = min(candidate.width, candidate.height) / max(candidate.width, candidate.height)
        if candidate.scale == "small":
            return candidate.area >= 3 and aspect >= 0.42 and candidate.confidence >= 0.42
        if candidate.scale == "medium":
            return candidate.area >= 6 and aspect >= 0.52 and candidate.confidence >= 0.50
        return candidate.area >= 12 and aspect >= 0.58 and candidate.confidence >= 0.56

    @staticmethod
    def _dedupe(candidates: Iterable[DotCandidate]) -> list[DotCandidate]:
        result: list[DotCandidate] = []
        for candidate in sorted(candidates, key=lambda item: (-item.confidence, item.x, item.y)):
            if any(math.hypot(candidate.x - existing.x, candidate.y - existing.y) <= max(1.0, 0.35 * (candidate.radius + existing.radius)) for existing in result):
                continue
            result.append(candidate)
        return sorted(result, key=lambda item: (item.y, item.x))

    @staticmethod
    def _best_match(element, candidates: list[DotCandidate], unmatched: set[int]) -> int | None:
        if not unmatched or not element.visible:
            return None
        best: tuple[float, int] | None = None
        element_size = max(element.width, element.height, 1.0)
        for index in unmatched:
            candidate = candidates[index]
            distance = math.hypot(element.x - candidate.x, element.y - candidate.y)
            tolerance = max(2.5, 0.65 * max(element_size, candidate.width, candidate.height))
            if distance > tolerance:
                continue
            size_error = abs(max(element.width, element.height) - max(candidate.width, candidate.height)) / max(element_size, candidate.width, candidate.height, 1.0)
            score = distance + size_error * tolerance * 0.5
            if best is None or score < best[0]:
                best = (score, index)
        return best[1] if best else None
