from dataclasses import dataclass

from ledger.store import CommittedReport


@dataclass(frozen=True)
class PublicationReceipt:
    report_id: str
    package_id: str


def receipt_for_commit(report: CommittedReport) -> PublicationReceipt:
    return PublicationReceipt(report.report_id, report.package_id)
