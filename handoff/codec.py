import json
from dataclasses import dataclass

from handoff.evidence import EvidenceRow
from recording.layout import RecordingLayout


class InvalidPackage(ValueError):
    pass


@dataclass(frozen=True)
class EvidencePackage:
    package_id: str
    recording_id: str
    layout: RecordingLayout
    stripe_ids: tuple[str, ...]
    evidence: tuple[EvidenceRow, ...]


def encode_package(package: EvidencePackage) -> str:
    payload = {
        'package_id': package.package_id,
        'recording_id': package.recording_id,
        'positions': list(package.layout.positions),
        'stripe_ids': list(package.stripe_ids),
        'evidence': [
            {'source_id': row.source_id, 'stripe_id': row.stripe_id, 'kind': row.kind, 'local_slots': list(row.local_slots), 'positions': list(row.positions), 'value': row.value}
            for row in package.evidence
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(',', ':'))


def decode_package(payload: str) -> EvidencePackage:
    try:
        data = json.loads(payload)
        layout = RecordingLayout(tuple(data['positions']))
        package_id = data['package_id']
        recording_id = data['recording_id']
        stripe_ids = tuple(data['stripe_ids'])
        raw_rows = data['evidence']
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidPackage('invalid package structure') from exc
    if not isinstance(package_id, str) or not package_id.strip() or not isinstance(recording_id, str) or not recording_id.strip():
        raise InvalidPackage('package identities are required')
    if len(set(stripe_ids)) != len(stripe_ids) or any(not isinstance(item, str) or not item.strip() for item in stripe_ids):
        raise InvalidPackage('package stripe ids are invalid')
    rows = []
    source_ids = set()
    for raw in raw_rows:
        try:
            row = EvidenceRow(raw['source_id'], raw['stripe_id'], raw['kind'], tuple(raw['local_slots']), tuple(raw['positions']), raw['value'])
        except (KeyError, TypeError) as exc:
            raise InvalidPackage('invalid evidence row') from exc
        if row.source_id in source_ids or row.stripe_id not in stripe_ids or row.kind not in ('direct', 'parity'):
            raise InvalidPackage('evidence identity is invalid')
        if row.kind == 'direct' and len(row.positions) != 1:
            raise InvalidPackage('direct evidence must target one position')
        if not row.positions or any(not layout.contains(position) for position in row.positions):
            raise InvalidPackage('evidence position is outside the package layout')
        if isinstance(row.value, bool) or row.value not in (0, 1):
            raise InvalidPackage('evidence value is invalid')
        source_ids.add(row.source_id)
        rows.append(row)
    return EvidencePackage(package_id, recording_id, layout, stripe_ids, tuple(rows))
