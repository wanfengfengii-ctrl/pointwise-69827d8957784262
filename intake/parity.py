from dataclasses import dataclass

from intake.slot_map import SlotMap


@dataclass(frozen=True)
class ParityEvidence:
    evidence_id: str
    slots: tuple[int, ...]
    value: int


def _coerce(item) -> ParityEvidence:
    if isinstance(item, ParityEvidence):
        return item
    return ParityEvidence(item['evidence_id'], tuple(item['slots']), item['value'])


def validate_parities(parities, slot_map: SlotMap, used_ids=()):
    result = []
    seen = set(used_ids)
    for item in parities or ():
        parity = _coerce(item)
        if not isinstance(parity.evidence_id, str) or not parity.evidence_id.strip():
            raise ValueError('parity evidence id must be non-empty')
        if parity.evidence_id in seen:
            raise ValueError('duplicate evidence id')
        if not parity.slots:
            raise ValueError('parity must contain at least one slot')
        if len(set(parity.slots)) != len(parity.slots):
            raise ValueError('parity slots must be unique')
        for slot in parity.slots:
            slot_map.resolve(slot)
        if isinstance(parity.value, bool) or parity.value not in (0, 1):
            raise ValueError('parity value must be 0 or 1')
        seen.add(parity.evidence_id)
        result.append(parity)
    return tuple(result)
