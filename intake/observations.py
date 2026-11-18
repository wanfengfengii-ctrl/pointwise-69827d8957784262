from dataclasses import dataclass

from intake.slot_map import SlotMap


@dataclass(frozen=True)
class DirectObservation:
    evidence_id: str
    slot: int
    value: int


def _coerce(item) -> DirectObservation:
    if isinstance(item, DirectObservation):
        return item
    return DirectObservation(item['evidence_id'], item['slot'], item['value'])


def validate_observations(observations, slot_map: SlotMap, used_ids=()):
    result = []
    seen = set(used_ids)
    for item in observations or ():
        observation = _coerce(item)
        if not isinstance(observation.evidence_id, str) or not observation.evidence_id.strip():
            raise ValueError('direct evidence id must be non-empty')
        if observation.evidence_id in seen:
            raise ValueError('duplicate evidence id')
        slot_map.resolve(observation.slot)
        if isinstance(observation.value, bool) or observation.value not in (0, 1):
            raise ValueError('direct evidence value must be 0 or 1')
        seen.add(observation.evidence_id)
        result.append(observation)
    return tuple(result)
