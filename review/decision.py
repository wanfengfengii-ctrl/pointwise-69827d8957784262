from dataclasses import replace

from handoff.codec import EvidencePackage
from ledger.publication import publish_report
from ledger.store import ReportStore
from review.constraints import analyze_constraints
from review.request import validate_request
from review.result import ReviewResult, compatible_result, conflict_result


def review_package(package: EvidencePackage, requested_positions, report_store: ReportStore, fail: bool = False) -> ReviewResult:
    request = validate_request(package.layout, requested_positions)
    analysis = analyze_constraints(package)
    if analysis.conflict:
        return conflict_result(package.package_id, request)
    result = compatible_result(package.package_id, request, analysis)
    receipt = publish_report(package, result, report_store, fail=fail)
    return replace(result, report_id=receipt.report_id)
