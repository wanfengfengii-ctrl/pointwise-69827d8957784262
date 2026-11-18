from handoff.codec import EvidencePackage
from ledger.reports import ShiftReport
from ledger.store import ReportStore
from review.witness import EvidenceWitness, replay_witness


def read_report(report_store: ReportStore, report_id: str) -> ShiftReport:
    return report_store.load_report(report_id)


def replay_report_witnesses(report: ShiftReport, package: EvidencePackage):
    if report.package_id != package.package_id:
        raise ValueError('report parent package does not match')
    for item in report.positions:
        if item.status == 'confirmed':
            replay_witness(EvidenceWitness((item.position,), item.value, item.source_ids), package)
    return True
