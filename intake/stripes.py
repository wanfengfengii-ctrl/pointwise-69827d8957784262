from dataclasses import dataclass

from intake.observations import DirectObservation, validate_observations
from intake.parity import ParityEvidence, validate_parities
from intake.slot_map import SlotMap, build_slot_map
from recording.batch import CaptureBatch


@dataclass(frozen=True)
class Stripe:
    stripe_id: str
    batch_id: str
    recording_id: str
    slot_map: SlotMap
    observations: tuple[DirectObservation, ...]
    parities: tuple[ParityEvidence, ...]


@dataclass(frozen=True)
class StripeBatch:
    batch_id: str
    recording_id: str
    stripes: tuple[Stripe, ...]


def build_stripe_batch(batch: CaptureBatch, stripe_specs) -> StripeBatch:
    stripes = []
    stripe_ids = set()
    evidence_ids = set()
    for spec in stripe_specs:
        stripe_id = spec['stripe_id']
        if not isinstance(stripe_id, str) or not stripe_id.strip() or stripe_id in stripe_ids:
            raise ValueError('stripe ids must be unique non-empty strings')
        slot_map = build_slot_map(batch.layout, spec['mapping'])
        observations = validate_observations(spec.get('direct', ()), slot_map, evidence_ids)
        evidence_ids.update(item.evidence_id for item in observations)
        parities = validate_parities(spec.get('parity', ()), slot_map, evidence_ids)
        evidence_ids.update(item.evidence_id for item in parities)
        stripes.append(Stripe(stripe_id, batch.batch_id, batch.recording_id, slot_map, observations, parities))
        stripe_ids.add(stripe_id)
    if not stripes:
        raise ValueError('at least one stripe is required')
    return StripeBatch(batch.batch_id, batch.recording_id, tuple(stripes))
