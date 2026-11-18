import sqlite3
import tempfile
import unittest

from handoff.codec import encode_package
from handoff.seal import export_package, seal_package
from handoff.store import PackageCommitError, PackageStore
from intake.store import StripeStore
from ledger.history import read_report, replay_report_witnesses
from ledger.store import ReportStore
from recording.catalog import RecordingCatalog
from review.decision import review_package
from review.witness import replay_witness
from review.witness import EvidenceWitness


class FreezeSlotMapRegressionTests(unittest.TestCase):
    """Incident root cause 1: frozen evidence must keep each stripe's own
    local-slot meaning instead of indexing the recording layout."""

    def _build(self, specs, positions=('a', 'b', 'c'), stripe_ids=None):
        connection = sqlite3.connect(':memory:')
        catalog = RecordingCatalog(connection)
        stripes = StripeStore(connection, catalog)
        packages = PackageStore(connection)
        catalog.initialize(); stripes.initialize(); packages.initialize()
        catalog.register('R1', list(positions))
        stripes.ingest('R1', specs, batch_id='B1')
        chosen = stripe_ids or [item['stripe_id'] for item in specs]
        seal_package(catalog, stripes, packages, 'R1', chosen, package_id='PKG-1')
        return connection, export_package(packages, 'PKG-1')

    def test_parity_frozen_through_stripe_mapping(self):
        connection, package = self._build([
            {'stripe_id': 'P', 'mapping': ['a', 'b', 'c'], 'direct': [],
             'parity': [{'evidence_id': 'P', 'slots': [0, 1, 2], 'value': 1}]},
            {'stripe_id': 'Q', 'mapping': ['c', 'b'], 'direct': [],
             'parity': [{'evidence_id': 'Q', 'slots': [0, 1], 'value': 0}]},
        ])
        row_q = next(item for item in package.evidence if item.source_id == 'Q')
        self.assertEqual(row_q.local_slots, (0, 1))
        self.assertEqual(row_q.positions, ('c', 'b'))
        row_p = next(item for item in package.evidence if item.source_id == 'P')
        self.assertEqual(row_p.positions, ('a', 'b', 'c'))
        connection.close()

    def test_direct_evidence_frozen_through_stripe_mapping(self):
        connection, package = self._build([
            {'stripe_id': 'D', 'mapping': ['c'],
             'direct': [{'evidence_id': 'D-C', 'slot': 0, 'value': 0}], 'parity': []},
        ])
        row = next(item for item in package.evidence if item.source_id == 'D-C')
        self.assertEqual(row.kind, 'direct')
        self.assertEqual(row.local_slots, (0,))
        self.assertEqual(row.positions, ('c',))
        self.assertEqual(row.value, 0)
        connection.close()

    def test_reordered_full_mapping_keeps_slot_coordinates(self):
        connection, package = self._build([
            {'stripe_id': 'Q', 'mapping': ['a', 'b', 'c'], 'direct': [],
             'parity': [{'evidence_id': 'Q', 'slots': [2, 1], 'value': 0}]},
        ])
        row = next(item for item in package.evidence if item.source_id == 'Q')
        self.assertEqual(row.local_slots, (2, 1))
        self.assertEqual(row.positions, ('c', 'b'))
        connection.close()


class EliminationRegressionTests(unittest.TestCase):
    """Incident root cause 2: review needs full GF(2) elimination, not exact
    mask matching."""

    def _review(self, specs, request, positions=('a', 'b', 'c', 'd')):
        connection = sqlite3.connect(':memory:')
        catalog = RecordingCatalog(connection)
        stripes = StripeStore(connection, catalog)
        packages = PackageStore(connection)
        reports = ReportStore(connection)
        catalog.initialize(); stripes.initialize(); packages.initialize(); reports.initialize()
        catalog.register('R1', list(positions))
        stripes.ingest('R1', specs, batch_id='B1')
        seal_package(catalog, stripes, packages, 'R1',
                     [item['stripe_id'] for item in specs], package_id='PKG-1')
        package = export_package(packages, 'PKG-1')
        result = review_package(package, request, reports)
        return connection, package, reports, result

    def _assert_witness_replays(self, package, item):
        self.assertEqual(item.status, 'confirmed')
        # Independent recomputation: XOR the cited original evidence rows
        # and require the exact unit equation position = value.
        replay_witness(EvidenceWitness((item.position,), item.value, item.source_ids), package)

    def test_incident_joint_determination(self):
        connection, package, reports, result = self._review([
            {'stripe_id': 'P', 'mapping': ['a', 'b', 'c'], 'direct': [],
             'parity': [{'evidence_id': 'P', 'slots': [0, 1, 2], 'value': 1}]},
            {'stripe_id': 'Q', 'mapping': ['c', 'b'], 'direct': [],
             'parity': [{'evidence_id': 'Q', 'slots': [0, 1], 'value': 0}]},
        ], ['c', 'a', 'b', 'a'])
        self.assertEqual(result.status, 'compatible')
        self.assertEqual(
            [(item.position, item.status, item.value, list(item.source_ids)) for item in result.positions],
            [('c', 'unknown', None, []), ('a', 'confirmed', 1, ['P', 'Q']),
             ('b', 'unknown', None, []), ('a', 'confirmed', 1, ['P', 'Q'])],
        )
        confirmed = next(item for item in result.positions if item.position == 'a')
        self._assert_witness_replays(package, confirmed)
        report = read_report(reports, result.report_id)
        self.assertEqual(report.requested_positions, ('c', 'a', 'b', 'a'))
        self.assertTrue(replay_report_witnesses(report, reports.load_parent(result.report_id)))
        connection.close()

    def test_multistep_elimination_witnesses(self):
        # No evidence is a unit equation; the three parity plus one direct
        # equation have rank 3: a, b and c are fixed only after several XOR
        # elimination steps (a needs three), while d remains a free variable.
        specs = [
            {'stripe_id': 'S1', 'mapping': ['a', 'b', 'c'], 'direct': [],
             'parity': [{'evidence_id': 'E1', 'slots': [0, 1, 2], 'value': 0}]},
            {'stripe_id': 'S2', 'mapping': ['b', 'c', 'd'], 'direct': [],
             'parity': [{'evidence_id': 'E2', 'slots': [0, 1, 2], 'value': 1}]},
            {'stripe_id': 'S3', 'mapping': ['c', 'd'], 'direct': [],
             'parity': [{'evidence_id': 'E3', 'slots': [0, 1], 'value': 1}]},
            {'stripe_id': 'S4', 'mapping': ['d'],
             'direct': [{'evidence_id': 'E4', 'slot': 0, 'value': 1}], 'parity': []},
        ]
        connection, package, reports, result = self._review(specs, ['a', 'b', 'c', 'd'])
        expected = {
            'a': (0, ('E1', 'E2', 'E4')),
            'b': (0, ('E2', 'E3')),
            'c': (0, ('E3', 'E4')),
        }
        self.assertEqual(result.status, 'compatible')
        for item in result.positions:
            if item.position == 'd':
                self.assertEqual(item.status, 'unknown')
                self.assertIsNone(item.value)
                self.assertEqual(item.source_ids, ())
                continue
            value, sources = expected[item.position]
            self.assertEqual(item.status, 'confirmed')
            self.assertEqual(item.value, value)
            self.assertEqual(item.source_ids, sources)
            self._assert_witness_replays(package, item)
        connection.close()

    def test_conflict_between_distinct_masks(self):
        # ab=0, abc=1, c=0: elimination yields c=1 against c=0 even though
        # no two raw rows share a mask.
        specs = [
            {'stripe_id': 'S1', 'mapping': ['a', 'b'], 'direct': [],
             'parity': [{'evidence_id': 'E1', 'slots': [0, 1], 'value': 0}]},
            {'stripe_id': 'S2', 'mapping': ['a', 'b', 'c'], 'direct': [],
             'parity': [{'evidence_id': 'E2', 'slots': [0, 1, 2], 'value': 1}]},
            {'stripe_id': 'S3', 'mapping': ['c'],
             'direct': [{'evidence_id': 'E3', 'slot': 0, 'value': 0}], 'parity': []},
        ]
        connection, package, reports, result = self._review(specs, ['a'], positions=('a', 'b', 'c'))
        self.assertEqual(result.status, 'conflict')
        self.assertIsNone(result.report_id)
        self.assertEqual(result.positions, ())
        self.assertEqual(reports.list_ids(), ())
        connection.close()

    def test_free_variable_stays_unknown(self):
        specs = [
            {'stripe_id': 'S1', 'mapping': ['a', 'b'], 'direct': [],
             'parity': [{'evidence_id': 'E1', 'slots': [0, 1], 'value': 1}]},
            {'stripe_id': 'S2', 'mapping': ['b', 'c'], 'direct': [],
             'parity': [{'evidence_id': 'E2', 'slots': [0, 1], 'value': 1}]},
        ]
        connection, package, reports, result = self._review(specs, ['a', 'b', 'c'], positions=('a', 'b', 'c'))
        self.assertTrue(all(item.status == 'unknown' for item in result.positions))
        connection.close()

    def test_redundant_equations_remain_compatible(self):
        specs = [
            {'stripe_id': 'S1', 'mapping': ['a', 'b'], 'direct': [],
             'parity': [{'evidence_id': 'E1', 'slots': [0, 1], 'value': 0}]},
            {'stripe_id': 'S2', 'mapping': ['a', 'b'], 'direct': [],
             'parity': [{'evidence_id': 'E2', 'slots': [0, 1], 'value': 0}]},
        ]
        connection, package, reports, result = self._review(specs, ['a'], positions=('a', 'b'))
        self.assertEqual(result.status, 'compatible')
        self.assertEqual(result.positions[0].status, 'unknown')
        self.assertEqual(len(reports.list_ids()), 1)
        connection.close()


class FrozenHistoryRegressionTests(unittest.TestCase):
    """Re-ingestion, commit failures and reopening must not alter sealed
    packages or published reports."""

    def test_reingest_failures_and_reopen_keep_frozen_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + '/handoff.db'
            connection = sqlite3.connect(path)
            catalog = RecordingCatalog(connection)
            stripes = StripeStore(connection, catalog)
            packages = PackageStore(connection)
            reports = ReportStore(connection)
            catalog.initialize(); stripes.initialize(); packages.initialize(); reports.initialize()
            catalog.register('R1', ['a', 'b', 'c'])
            stripes.ingest('R1', [
                {'stripe_id': 'P', 'mapping': ['a', 'b', 'c'], 'direct': [],
                 'parity': [{'evidence_id': 'P', 'slots': [0, 1, 2], 'value': 1}]},
                {'stripe_id': 'Q', 'mapping': ['c', 'b'], 'direct': [],
                 'parity': [{'evidence_id': 'Q', 'slots': [0, 1], 'value': 0}]},
            ], batch_id='B1')
            seal_package(catalog, stripes, packages, 'R1', ['P', 'Q'], package_id='PKG-1')
            frozen_payload = packages.load_payload('PKG-1')
            package = export_package(packages, 'PKG-1')
            result = review_package(package, ['c', 'a', 'b'], reports)
            report_id = result.report_id
            stored_report = read_report(reports, report_id)

            # Supplementary capture must not touch the sealed package.
            stripes.ingest('R1', [
                {'stripe_id': 'D', 'mapping': ['a'],
                 'direct': [{'evidence_id': 'A0', 'slot': 0, 'value': 0}], 'parity': []},
            ], batch_id='B2')
            with self.assertRaises(PackageCommitError):
                seal_package(catalog, stripes, packages, 'R1', ['D'], package_id='PKG-2', fail=True)
            with self.assertRaises(RuntimeError):
                review_package(package, ['b'], reports, fail=True)
            self.assertEqual(packages.list_ids(), ('PKG-1',))
            self.assertEqual(reports.list_ids(), (report_id,))
            self.assertEqual(packages.load_payload('PKG-1'), frozen_payload)
            self.assertEqual(encode_package(export_package(packages, 'PKG-1')), frozen_payload)
            self.assertEqual(read_report(reports, report_id), stored_report)
            self.assertTrue(replay_report_witnesses(stored_report, reports.load_parent(report_id)))
            connection.close()

            # Reopen: old package and old report still read frozen content.
            reopened = sqlite3.connect(path)
            reopened_packages = PackageStore(reopened)
            reopened_reports = ReportStore(reopened)
            reopened_packages.initialize(); reopened_reports.initialize()
            self.assertEqual(reopened_packages.load_payload('PKG-1'), frozen_payload)
            reopened_report = read_report(reopened_reports, report_id)
            self.assertEqual(reopened_report.requested_positions, ('c', 'a', 'b'))
            self.assertEqual(
                [(item.position, item.status, item.value, list(item.source_ids)) for item in reopened_report.positions],
                [('c', 'unknown', None, []), ('a', 'confirmed', 1, ['P', 'Q']), ('b', 'unknown', None, [])],
            )
            self.assertTrue(replay_report_witnesses(reopened_report, reopened_packages.load_package('PKG-1')))
            reopened.close()


if __name__ == '__main__':
    unittest.main()
