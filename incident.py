import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from handoff.codec import decode_package, encode_package
from handoff.seal import export_package, seal_package
from handoff.store import PackageStore
from intake.store import StripeStore
from ledger.history import read_report, replay_report_witnesses
from ledger.store import ReportStore
from recording.catalog import RecordingCatalog
from review.decision import review_package


def issue_package(sample, specs):
    with closing(sqlite3.connect(":memory:")) as connection:
        catalog = RecordingCatalog(connection)
        stripes = StripeStore(connection, catalog)
        packages = PackageStore(connection)
        catalog.initialize()
        stripes.initialize()
        packages.initialize()
        recording_id = sample["recording_id"]
        catalog.register(recording_id, sample["positions"])
        chosen = stripes.ingest(recording_id, specs, batch_id="INCIDENT-BATCH")
        package_id = seal_package(catalog, stripes, packages, recording_id, chosen, package_id="INCIDENT-PACKAGE")
        return encode_package(export_package(packages, package_id))


def report_matches(store, package, result):
    if result.report_id is None:
        return False
    report = read_report(store, result.report_id)
    parent = store.load_parent(result.report_id)
    if (parent != package or report.package_id != package.package_id
            or report.requested_positions != result.requested_positions
            or report.positions != result.positions):
        return False
    try:
        return replay_report_witnesses(report, parent)
    except ValueError:
        return False


def observe(sample, case):
    p, q = sample["stripes"]
    specs = [p, q]
    expected_evidence = {
        "P": ["P", "parity", [0, 1, 2], ["a", "b", "c"], 1],
        "Q": ["Q", "parity", [0, 1], ["c", "b"], 0],
    }
    if case == "coordinates":
        specs.append({"stripe_id": "D", "mapping": ["c"],
                      "direct": [{"evidence_id": "D-C", "slot": 0, "value": 0}], "parity": []})
        expected_evidence["D-C"] = ["D", "direct", [0], ["c"], 0]
    elif case == "review":
        specs[1] = {**q, "mapping": sample["positions"],
                    "parity": [{"evidence_id": "Q", "slots": [2, 1], "value": 0}]}
        expected_evidence["Q"][2] = [2, 1]

    package = decode_package(issue_package(sample, specs))
    expected = {"evidence": expected_evidence}
    actual = {"evidence": {
        row.source_id: [row.stripe_id, row.kind, list(row.local_slots), list(row.positions), row.value]
        for row in package.evidence
    }}
    if case == "coordinates":
        return expected, actual

    with closing(sqlite3.connect(":memory:")) as connection:
        sink = ReportStore(connection)
        sink.initialize()
        review = review_package(package, sample["request"], sink)
        actual.update(
            status=review.status,
            positions=[[item.position, item.status, item.value, list(item.source_ids)] for item in review.positions],
            report_matches=report_matches(sink, package, review),
        )
    expected.update(
        status="compatible",
        positions=[["c", "unknown", None, []], ["a", "confirmed", 1, ["P", "Q"]], ["b", "unknown", None, []]],
        report_matches=True,
    )
    return expected, actual


def main():
    parser = argparse.ArgumentParser(description="Check the bridge recording handoff against the incident ledger.")
    parser.add_argument("--case", choices=("combined", "coordinates", "review"), default="combined")
    args = parser.parse_args()
    sample = json.loads(Path(__file__).with_name("sample.json").read_text(encoding="utf-8"))
    expected, actual = observe(sample, args.case)
    print(json.dumps({"case": args.case, "expected": expected, "actual": actual}, sort_keys=True))
    if actual != expected:
        print("BIT_EVIDENCE_MISMATCH")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
