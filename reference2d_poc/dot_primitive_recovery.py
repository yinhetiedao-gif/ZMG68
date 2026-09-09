from __future__ import annotations

from dataclasses import dataclass

from .models import DotObject
from .primitive_recognizer import PrimitiveCandidate


@dataclass(frozen=True)
class RejectedPrimitive:
    source_id: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"source_id": self.source_id, "reason": self.reason}


@dataclass(frozen=True)
class DotRecoveryResult:
    dots: tuple[DotObject, ...]
    rejected: tuple[RejectedPrimitive, ...]


class DotPrimitiveRecovery:
    """将被 PrimitiveRecognizer 接受的路径变成真实 DotObject。"""

    def recover(self, candidates: tuple[PrimitiveCandidate, ...]) -> DotRecoveryResult:
        dots: list[DotObject] = []
        rejected: list[RejectedPrimitive] = []
        for candidate in candidates:
            if not candidate.accepted_as_dot:
                rejected.append(RejectedPrimitive(candidate.source_id, candidate.reject_reason or "未通过 DOT 规则"))
                continue
            dots.append(
                DotObject(
                    id=f"dot-{len(dots) + 1:04d}",
                    x=candidate.center_x,
                    y=candidate.center_y,
                    radius_x=candidate.radius_x,
                    radius_y=candidate.radius_y,
                    rotation=candidate.rotation,
                    fill=candidate.fill,
                    source_confidence=candidate.confidence,
                )
            )
        return DotRecoveryResult(tuple(dots), tuple(rejected))
