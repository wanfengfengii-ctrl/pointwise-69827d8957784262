import sqlite3
import tempfile
import unittest

from handoff.seal import export_package, seal_package
from handoff.store import PackageStore
from intake.store import StripeStore
from ledger.history import read_report, replay_report_witnesses
from ledger.store import ReportStore
from recording.catalog import RecordingCatalog
from review.decision import review_package


class ReportTests(unittest.TestCase):
    def _create(self, path=':memory:'):
        connection = sqlite3.connect(path)
        catalog = RecordingCatalog(connection); stripes = StripeStore(connection, catalog); packages = PackageStore(connection); reports = ReportStore(connection)
        catalog.initialize(); stripes.initialize(); packages.initialize(); reports.initialize(); catalog.register('R1', ['a', 'b', 'c'])
        stripes.ingest('R1', [
            {'stripe_id': 'P', 'mapping': ['a', 'b', 'c'], 'direct': [], 'parity': [{'evidence_id': 'P', 'slots': [0, 1, 2], 'value': 1}]},
            {'stripe_id': 'Q', 'mapping': ['c', 'b'], 'direct': [], 'parity': [{'evidence_id': 'Q', 'slots': [0, 1], 'value': 0}]},
        ], batch_id='B1')
        seal_package(catalog, stripes, packages, 'R1', ['P', 'Q'], package_id='PKG-1')
        return connection, packages, reports, export_package(packages, 'PKG-1')

    def test_reopen_report(self):
        with tempfile.TemporaryDirectory() as directory:
            connection, packages, reports, package = self._create(directory + '/reports.db')
            result = review_package(package, ['c', 'a', 'b', 'a'], reports)
            report_id = result.report_id
            connection.close()
            reopened = sqlite3.connect(directory + '/reports.db')
            reopened_reports = ReportStore(reopened); reopened_packages = PackageStore(reopened)
            reopened_reports.initialize(); reopened_packages.initialize()
            report = read_report(reopened_reports, report_id)
            parent = reopened_packages.load_package(report.package_id)
            self.assertEqual(report.requested_positions, ('c', 'a', 'b', 'a'))
            self.assertTrue(replay_report_witnesses(report, parent))
            reopened.close()

    def test_ordered_occurrences(self):
        connection, packages, reports, package = self._create()
        result = review_package(package, ['c', 'a', 'b', 'a'], reports)
        report = read_report(reports, result.report_id)
        self.assertEqual(report.requested_positions, ('c', 'a', 'b', 'a'))
        self.assertEqual(tuple(item.position for item in report.positions), ('c', 'a', 'b', 'a'))
        connection.close()

    def test_publish_rollback(self):
        connection, packages, reports, package = self._create()
        first = review_package(package, ['a'], reports)
        with self.assertRaises(RuntimeError):
            review_package(package, ['b'], reports, fail=True)
        self.assertEqual(reports.list_ids(), (first.report_id,))
        self.assertEqual(read_report(reports, first.report_id).package_id, 'PKG-1')
        connection.close()

    def test_reinitialize(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + '/reinitialize.db'
            connection, packages, reports, package = self._create(path)
            result = review_package(package, ['a', 'b'], reports)
            connection.close()
            reopened = sqlite3.connect(path)
            reopened_packages = PackageStore(reopened); reopened_reports = ReportStore(reopened)
            reopened_packages.initialize(); reopened_reports.initialize()
            report = read_report(reopened_reports, result.report_id)
            self.assertEqual(reopened_packages.load_package(report.package_id).package_id, 'PKG-1')
            reopened.close()


if __name__ == '__main__':
    unittest.main()
