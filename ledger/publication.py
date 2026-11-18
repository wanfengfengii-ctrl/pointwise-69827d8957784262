import uuid

from handoff.codec import EvidencePackage
from ledger.receipts import PublicationReceipt, receipt_for_commit
from ledger.reports import build_report
from ledger.store import ReportStore
from review.result import ReviewResult


def publish_report(package: EvidencePackage, result: ReviewResult, report_store: ReportStore, report_id: str | None = None, fail: bool = False) -> PublicationReceipt:
    report = build_report(report_id or uuid.uuid4().hex, package, result)
    committed = report_store.commit_report(report, package, fail=fail)
    return receipt_for_commit(committed)
