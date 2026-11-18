from dataclasses import dataclass

from handoff.codec import EvidencePackage
from review.witness import EvidenceWitness, combine_sources


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


def _to_row(evidence, index):
    # XOR-build the mask so a position appearing more than once cancels,
    # matching the GF(2) reading of the frozen evidence.
    mask = 0
    for position in evidence.positions:
        mask ^= 1 << index[position]
    return _Row(mask, evidence.value, (evidence.source_id,))


def analyze_constraints(package: EvidencePackage) -> ConstraintAnalysis:
    """Full binary (GF(2)) Gauss-Jordan elimination over the whole package.

    Only positions that end up as a unit pivot row are fixed in every
    compatible solution; every other position stays unknown. Each reduced
    row keeps the XOR of its contributing source ids, so every confirmed
    value carries a witness list that independently replays from the
    frozen package.
    """
    index = {position: number for number, position in enumerate(package.layout.positions)}
    pivots = {}
    conflict = False
    for evidence in package.evidence:
        row = _to_row(evidence, index)
        # Forward-reduce the incoming row against the current basis.
        while row.mask:
            pivot = row.mask.bit_length() - 1
            basis = pivots.get(pivot)
            if basis is None:
                break
            row = _Row(
                row.mask ^ basis.mask,
                row.value ^ basis.value,
                combine_sources(row.source_ids, basis.source_ids),
            )
        if not row.mask:
            # 0 = 1 contradicts the whole package; 0 = 0 is a redundant
            # duplicate of an existing equation and simply drops out.
            conflict = conflict or bool(row.value)
            continue
        pivot = row.mask.bit_length() - 1
        # Keep the basis in reduced row echelon form: clear the new pivot
        # bit from every previously stored basis row.
        for other_pivot, basis in tuple(pivots.items()):
            if basis.mask & (1 << pivot):
                pivots[other_pivot] = _Row(
                    basis.mask ^ row.mask,
                    basis.value ^ row.value,
                    combine_sources(basis.source_ids, row.source_ids),
                )
        pivots[pivot] = row
    rows = tuple(pivots[number] for number in sorted(pivots))
    return ConstraintAnalysis(package.layout.positions, rows, conflict)
