import json
from dataclasses import dataclass

from handoff.codec import EvidencePackage
from review.result import PositionResult, ReviewResult


@dataclass(frozen=True)
class ShiftReport:
    report_id: str
    package_id: str
    requested_positions: tuple[str, ...]
    positions: tuple[PositionResult, ...]


def build_report(report_id: str, package: EvidencePackage, result: ReviewResult) -> ShiftReport:
    if result.status != 'compatible' or result.package_id != package.package_id:
        raise ValueError('only a compatible result for the same package can be published')
    return ShiftReport(report_id, package.package_id, result.requested_positions, result.positions)


def encode_report(report: ShiftReport) -> str:
    return json.dumps({'report_id': report.report_id, 'package_id': report.package_id, 'requested_positions': list(report.requested_positions), 'positions': [{'position': item.position, 'status': item.status, 'value': item.value, 'source_ids': list(item.source_ids)} for item in report.positions]}, sort_keys=True, separators=(',', ':'))


def decode_report(payload: str) -> ShiftReport:
    data = json.loads(payload)
    positions = tuple(PositionResult(item['position'], item['status'], item.get('value'), tuple(item.get('source_ids', ()))) for item in data['positions'])
    if any(item.status not in ('confirmed', 'unknown') for item in positions):
        raise ValueError('invalid report position status')
    return ShiftReport(data['report_id'], data['package_id'], tuple(data['requested_positions']), positions)
