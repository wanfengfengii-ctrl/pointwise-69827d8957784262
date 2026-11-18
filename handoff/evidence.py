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
    for stripe in manifest.stripes:
        # Each stripe interprets its own local slots through its private
        # slot map. Indexing the recording layout here would misplace
        # evidence whenever a stripe reorders or subsets the layout.
        for observation in stripe.observations:
            slot = observation.slot
            position = stripe.slot_map.resolve(slot)
            rows.append(EvidenceRow(
                observation.evidence_id, stripe.stripe_id, "direct",
                (slot,), (position,), observation.value,
            ))
        for parity in stripe.parities:
            slots = tuple(parity.slots)
            positions = tuple(stripe.slot_map.resolve(slot) for slot in slots)
            rows.append(EvidenceRow(
                parity.evidence_id, stripe.stripe_id, "parity",
                slots, positions, parity.value,
            ))
    return tuple(rows)
