from dataclasses import dataclass

from handoff.codec import EvidencePackage


@dataclass(frozen=True)
class EvidenceWitness:
    positions: tuple[str, ...]
    value: int
    source_ids: tuple[str, ...]


def combine_sources(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(left) ^ set(right)))


def combine_witnesses(left: EvidenceWitness, right: EvidenceWitness) -> EvidenceWitness:
    positions = tuple(sorted(set(left.positions) ^ set(right.positions)))
    return EvidenceWitness(positions, left.value ^ right.value, combine_sources(left.source_ids, right.source_ids))


def replay_witness(witness: EvidenceWitness, package: EvidencePackage):
    by_id = {row.source_id: row for row in package.evidence}
    positions = []
    value = 0
    for source_id in witness.source_ids:
        if source_id not in by_id:
            raise ValueError('witness source is absent from package')
        row = by_id[source_id]
        value ^= row.value
        for position in row.positions:
            if position in positions:
                positions.remove(position)
            else:
                positions.append(position)
    ordered = tuple(sorted(positions, key=package.layout.order_key))
    if ordered != witness.positions or value != witness.value:
        raise ValueError('witness does not replay to its claimed equation')
    return True
