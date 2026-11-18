from dataclasses import dataclass

from handoff.manifest import PackageManifest


@dataclass(frozen=True)
class EvidenceRow:
    source_id: str
    stripe_id: str
    kind: str
    local_slots: tuple[int, ...]
    positions: tuple[str, ...]
    value: int


def freeze_evidence(manifest: PackageManifest):
    rows = []
    positions = manifest.layout.positions
    for stripe in manifest.stripes:
        for observation in stripe.observations:
            slot = observation.slot
            rows.append(EvidenceRow(
                observation.evidence_id, stripe.stripe_id, "direct",
                (slot,), (positions[slot],), observation.value,
            ))
        for parity in stripe.parities:
            slots = tuple(parity.slots)
            rows.append(EvidenceRow(
                parity.evidence_id, stripe.stripe_id, "parity",
                slots, tuple(positions[slot] for slot in slots), parity.value,
            ))
    return tuple(rows)
