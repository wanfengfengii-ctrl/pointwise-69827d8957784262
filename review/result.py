from dataclasses import dataclass

from review.constraints import ConstraintAnalysis
from review.request import ReviewRequest


@dataclass(frozen=True)
class PositionResult:
    position: str
    status: str
    value: int | None = None
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewResult:
    package_id: str
    status: str
    requested_positions: tuple[str, ...]
    positions: tuple[PositionResult, ...]
    report_id: str | None = None


def compatible_result(package_id: str, request: ReviewRequest, analysis: ConstraintAnalysis) -> ReviewResult:
    positions = []
    for position in request.positions:
        witness = analysis.resolve_position(position)
        if witness is None:
            positions.append(PositionResult(position, 'unknown'))
        else:
            positions.append(PositionResult(position, 'confirmed', witness.value, witness.source_ids))
    return ReviewResult(package_id, 'compatible', request.positions, tuple(positions))


def conflict_result(package_id: str, request: ReviewRequest) -> ReviewResult:
    return ReviewResult(package_id, 'conflict', request.positions, ())
