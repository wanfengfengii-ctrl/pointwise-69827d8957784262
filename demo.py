import json
import sqlite3
from pathlib import Path

from handoff.seal import export_package, seal_package
from handoff.store import PackageStore
from intake.store import StripeStore
from ledger.history import read_report, replay_report_witnesses
from ledger.store import ReportStore
from recording.catalog import RecordingCatalog
from review.decision import review_package


def main():
    sample = json.loads(Path(__file__).with_name('sample.json').read_text())
    connection = sqlite3.connect(':memory:')
    catalog = RecordingCatalog(connection)
    stripe_store = StripeStore(connection, catalog)
    package_store = PackageStore(connection)
    report_store = ReportStore(connection)
    catalog.initialize()
    stripe_store.initialize()
    package_store.initialize()
    report_store.initialize()
    catalog.register(sample['recording_id'], sample['positions'])
    stripe_store.ingest(sample['recording_id'], sample['stripes'], batch_id='BATCH-DEMO')
    package_id = seal_package(catalog, stripe_store, package_store, sample['recording_id'], ['P', 'Q'], package_id='PKG-DEMO')
    package = export_package(package_store, package_id)
    result = review_package(package, sample['request'], report_store)
    report = read_report(report_store, result.report_id)
    parent = report_store.load_parent(result.report_id)
    replayed = replay_report_witnesses(report, parent)
    output = {
        'package_id': package_id,
        'status': result.status,
        'positions': [
            {'position': item.position, 'status': item.status, 'value': item.value, 'source_ids': list(item.source_ids)}
            for item in result.positions
        ],
        'report_id': result.report_id,
        'witnesses_replayed': replayed,
    }
    print(json.dumps(output, sort_keys=True))


if __name__ == '__main__':
    main()
