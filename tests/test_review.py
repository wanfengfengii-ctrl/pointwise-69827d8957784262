import json
import sqlite3
import unittest

from handoff.seal import export_package, seal_package
from handoff.store import PackageStore
from intake.store import StripeStore
from ledger.store import ReportStore
from recording.catalog import RecordingCatalog
from review.decision import review_package
from review.request import InvalidReviewRequest


class ReviewTests(unittest.TestCase):
    def _setup(self, reordered=False, extra=None):
        connection = sqlite3.connect(':memory:')
        catalog = RecordingCatalog(connection)
        stripes = StripeStore(connection, catalog)
        packages = PackageStore(connection)
        reports = ReportStore(connection)
        catalog.initialize(); stripes.initialize(); packages.initialize(); reports.initialize()
        catalog.register('R1', ['a', 'b', 'c'])
        q_mapping = ['b', 'c'] if reordered else ['c', 'b']
        q_slots = [1, 0] if reordered else [0, 1]
        specs = [
            {'stripe_id': 'P', 'mapping': ['a', 'b', 'c'], 'direct': [], 'parity': [{'evidence_id': 'P', 'slots': [0, 1, 2], 'value': 1}]},
            {'stripe_id': 'Q', 'mapping': q_mapping, 'direct': [], 'parity': [{'evidence_id': 'Q', 'slots': q_slots, 'value': 0}]},
        ]
        if extra:
            specs.append(extra)
        stripes.ingest('R1', specs, batch_id='B1')
        seal_package(catalog, stripes, packages, 'R1', [item['stripe_id'] for item in specs], package_id='PKG-1')
        return connection, packages, reports, export_package(packages, 'PKG-1')

    def test_overlapping_stripes(self):
        connection, packages, reports, package = self._setup()
        result = review_package(package, ['c', 'a', 'b'], reports)
        actual = [(item.position, item.status, item.value, list(item.source_ids)) for item in result.positions]
        expected = [('c', 'unknown', None, []), ('a', 'confirmed', 1, ['P', 'Q']), ('b', 'unknown', None, [])]
        self.assertEqual(actual, expected)
        self.assertTrue(result.report_id)
        print(json.dumps({'case_id': 'N6', 'input': 'P=a xor b xor c=1 and Q=c xor b=0', 'expected': expected, 'actual': actual, 'downstream_expected': 'report with replayable P,Q witness', 'downstream_actual': {'report_id': result.report_id}, 'code_paths': ['handoff/evidence.py', 'review/constraints.py', 'review/witness.py', 'ledger/publication.py'], 'oracle': 'independently xor the frozen source rows'}, sort_keys=True))
        connection.close()

    def test_offline_reordered(self):
        connection, packages, reports, package = self._setup(reordered=True)
        result = review_package(package, ['c', 'a', 'b'], reports)
        self.assertEqual([item.status for item in result.positions], ['unknown', 'confirmed', 'unknown'])
        self.assertEqual(next(item for item in result.positions if item.position == 'a').value, 1)
        connection.close()

    def test_witness_cancellation(self):
        connection = sqlite3.connect(':memory:')
        catalog = RecordingCatalog(connection); stripes = StripeStore(connection, catalog); packages = PackageStore(connection); reports = ReportStore(connection)
        catalog.initialize(); stripes.initialize(); packages.initialize(); reports.initialize(); catalog.register('R1', ['a', 'b', 'c'])
        specs = [
            {'stripe_id': 'S1', 'mapping': ['a', 'b'], 'direct': [], 'parity': [{'evidence_id': 'E1', 'slots': [0, 1], 'value': 0}]},
            {'stripe_id': 'S2', 'mapping': ['a', 'c'], 'direct': [], 'parity': [{'evidence_id': 'E2', 'slots': [0, 1], 'value': 0}]},
            {'stripe_id': 'S3', 'mapping': ['a', 'b', 'c'], 'direct': [], 'parity': [{'evidence_id': 'E3', 'slots': [0, 1, 2], 'value': 1}]},
        ]
        stripes.ingest('R1', specs, batch_id='B1'); seal_package(catalog, stripes, packages, 'R1', ['S1', 'S2', 'S3'], package_id='PKG-1')
        result = review_package(export_package(packages, 'PKG-1'), ['b'], reports)
        self.assertEqual(result.positions[0].value, 1)
        self.assertEqual(result.positions[0].source_ids, ('E2', 'E3'))
        connection.close()

    def test_inconsistent_evidence(self):
        connection, packages, reports, package = self._setup()
        good = review_package(package, ['a'], reports)
        self.assertTrue(good.report_id)
        before = reports.list_ids()
        extra = {'stripe_id': 'D', 'mapping': ['a'], 'direct': [{'evidence_id': 'A0', 'slot': 0, 'value': 0}], 'parity': []}
        connection.close()
        connection, packages, reports, package = self._setup(extra=extra)
        result = review_package(package, ['b'], reports)
        self.assertEqual(result.status, 'conflict')
        self.assertIsNone(result.report_id)
        self.assertEqual(reports.list_ids(), ())

    def test_unrequested_conflict(self):
        connection, packages, reports, package = self._setup(extra={'stripe_id': 'D', 'mapping': ['a'], 'direct': [{'evidence_id': 'A0', 'slot': 0, 'value': 0}], 'parity': []})
        result = review_package(package, ['b'], reports)
        self.assertEqual(result.status, 'conflict')
        self.assertEqual(result.positions, ())
        self.assertEqual(reports.list_ids(), ())
        connection.close()

    def test_invalid_input(self):
        connection, packages, reports, package = self._setup()
        with self.assertRaises(InvalidReviewRequest):
            review_package(package, ['outside'], reports)
        self.assertEqual(reports.list_ids(), ())
        connection.close()


if __name__ == '__main__':
    unittest.main()
