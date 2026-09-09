from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .dot_primitive_recovery import DotPrimitiveRecovery, DotRecoveryResult
from .models import Document2D
from .primitive_recognizer import PrimitiveCandidate, PrimitiveRecognizer
from .scene_graph_builder import SceneGraphBuilder
from .svg_parser import ParsedSVG, SVGParser
from .vectorizer_adapter import VTracerResult, VectorizerAdapter


@dataclass(frozen=True)
class ReconstructionResult:
    vectorization: VTracerResult
    svg: ParsedSVG
    candidates: tuple[PrimitiveCandidate, ...]
    recovery: DotRecoveryResult
    document: Document2D

    def report(self) -> dict[str, object]:
        return {
            "stage": "A: Geometry Reconstruction",
            "source_path": self.vectorization.source_path,
            "svg_path": self.vectorization.svg_path,
            "vtracer_version": self.vectorization.package_version,
            "vtracer_options": self.vectorization.options,
            "svg_path_count": len(self.svg.paths),
            "dot_count": len(self.recovery.dots),
            "rejected_count": len(self.recovery.rejected),
            "rejected": [item.to_dict() for item in self.recovery.rejected],
        }


class Reference2DService:
    """Stage A 完整链路：PNG/JPG → SVG → SVGParser → DotObject[] → Document2D。"""

    def __init__(self) -> None:
        self.vectorizer = VectorizerAdapter()
        self.parser = SVGParser()
        self.recognizer = PrimitiveRecognizer()
        self.recovery = DotPrimitiveRecovery()
        self.scene_graph = SceneGraphBuilder()

    def reconstruct(self, image_path: str | Path, svg_path: str | Path) -> ReconstructionResult:
        vectorization = self.vectorizer.vectorize(image_path, svg_path)
        parsed = self.parser.parse_file(vectorization.svg_path)
        candidates = self.recognizer.recognize(parsed.paths)
        recovery = self.recovery.recover(candidates)
        document = self.scene_graph.build(vectorization.source_path, parsed, recovery)
        return ReconstructionResult(vectorization, parsed, candidates, recovery, document)
