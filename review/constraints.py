from dataclasses import dataclass

from handoff.codec import EvidencePackage
from review.witness import EvidenceWitness


@dataclass(frozen=True)
class _Row:
    mask: int
    value: int
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class ConstraintAnalysis:
    positions: tuple[str, ...]
    rows: tuple[_Row, ...]
    conflict: bool

    def resolve_position(self, position: str):
        if self.conflict:
            return None
        target = 1 << self.positions.index(position)
        for row in self.rows:
            if row.mask == target:
                return EvidenceWitness((position,), row.value, row.source_ids)
        return None


def analyze_constraints(package: EvidencePackage) -> ConstraintAnalysis:
    index = {position: number for number, position in enumerate(package.layout.positions)}
    rows_by_mask = {}
    conflict = False
    for evidence in package.evidence:
        mask = 0
        for position in evidence.positions:
            mask ^= 1 << index[position]
        previous = rows_by_mask.get(mask)
        if not mask:
            conflict = conflict or bool(evidence.value)
        elif previous is None:
            rows_by_mask[mask] = _Row(mask, evidence.value, (evidence.source_id,))
        elif previous.value != evidence.value:
            conflict = True
    return ConstraintAnalysis(package.layout.positions, tuple(rows_by_mask.values()), conflict)
