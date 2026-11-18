import json
import sqlite3
import tempfile
import unittest

from handoff.seal import export_package, seal_package
from handoff.store import PackageCommitError, PackageStore
from handoff.codec import encode_package
from intake.store import StripeStore
from ledger.store import ReportStore
from recording.catalog import RecordingCatalog


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.catalog = RecordingCatalog(self.connection)
        self.stripes = StripeStore(self.connection, self.catalog)
        self.packages = PackageStore(self.connection)
        self.reports = ReportStore(self.connection)
        self.catalog.initialize()
        self.stripes.initialize()
        self.packages.initialize()
        self.reports.initialize()
        self.catalog.register('R1', ['a', 'b', 'c'])

    def _seed(self):
        return self.stripes.ingest('R1', [{'stripe_id': 'S1', 'mapping': ['a', 'b'], 'direct': [{'evidence_id': 'A', 'slot': 0, 'value': 1}], 'parity': [{'evidence_id': 'P', 'slots': [0, 1], 'value': 1}]}], batch_id='B1')

    def test_frozen_export(self):
        self._seed()
        seal_package(self.catalog, self.stripes, self.packages, 'R1', ['S1'], package_id='PKG-1')
        first = encode_package(export_package(self.packages, 'PKG-1'))
        self.stripes.ingest('R1', [{'stripe_id': 'S2', 'mapping': ['c'], 'direct': [{'evidence_id': 'C', 'slot': 0, 'value': 0}], 'parity': []}], batch_id='B2')
        second = encode_package(export_package(self.packages, 'PKG-1'))
        self.assertEqual(first, second)

    def test_source_coordinates(self):
        self._seed()
        package = export_package(self.packages) if False else None
        seal_package(self.catalog, self.stripes, self.packages, 'R1', ['S1'], package_id='PKG-1')
        package = export_package(self.packages, 'PKG-1')
        parity = next(item for item in package.evidence if item.source_id == 'P')
        self.assertEqual(parity.positions, ('a', 'b'))
        self.assertEqual(parity.local_slots, (0, 1))
        self.assertEqual(parity.stripe_id, 'S1')

    def test_selected_snapshot(self):
        self._seed()
        self.stripes.ingest('R1', [{'stripe_id': 'S2', 'mapping': ['c'], 'direct': [{'evidence_id': 'C', 'slot': 0, 'value': 0}], 'parity': []}], batch_id='B2')
        seal_package(self.catalog, self.stripes, self.packages, 'R1', ['S1'], package_id='PKG-1')
        package = export_package(self.packages, 'PKG-1')
        self.assertEqual(package.stripe_ids, ('S1',))
        self.assertNotIn('C', {item.source_id for item in package.evidence})

    def test_foreign_stripe(self):
        self._seed()
        self.catalog.register('R2', ['a', 'b', 'c'])
        self.stripes.ingest('R2', [{'stripe_id': 'S2', 'mapping': ['a'], 'direct': [], 'parity': []}], batch_id='B2')
        with self.assertRaises(ValueError):
            seal_package(self.catalog, self.stripes, self.packages, 'R1', ['S1', 'S2'], package_id='BAD')
        self.assertEqual(self.packages.list_ids(), ())

    def test_failed_seal(self):
        self._seed()
        seal_package(self.catalog, self.stripes, self.packages, 'R1', ['S1'], package_id='PKG-1')
        self.stripes.ingest('R1', [{'stripe_id': 'S2', 'mapping': ['c'], 'direct': [], 'parity': []}], batch_id='B2')
        with self.assertRaises(PackageCommitError):
            seal_package(self.catalog, self.stripes, self.packages, 'R1', ['S2'], package_id='PKG-2', fail=True)
        self.assertEqual(self.packages.list_ids(), ('PKG-1',))
        self.assertEqual(export_package(self.packages, 'PKG-1').package_id, 'PKG-1')

    def test_reopen_after_reinitialize(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + '/handoff.db'
            connection = sqlite3.connect(path)
            catalog = RecordingCatalog(connection)
            stripes = StripeStore(connection, catalog)
            packages = PackageStore(connection)
            catalog.initialize(); stripes.initialize(); packages.initialize()
            catalog.register('R1', ['a'])
            stripes.ingest('R1', [{'stripe_id': 'S1', 'mapping': ['a'], 'direct': [{'evidence_id': 'A', 'slot': 0, 'value': 1}], 'parity': []}], batch_id='B1')
            seal_package(catalog, stripes, packages, 'R1', ['S1'], package_id='PKG-1')
            connection.close()
            reopened = sqlite3.connect(path)
            reopened_catalog = RecordingCatalog(reopened)
            reopened_stripes = StripeStore(reopened, reopened_catalog)
            reopened_packages = PackageStore(reopened)
            reopened_catalog.initialize(); reopened_stripes.initialize(); reopened_packages.initialize()
            self.assertEqual(export_package(reopened_packages, 'PKG-1').package_id, 'PKG-1')
            reopened.close()


if __name__ == '__main__':
    unittest.main()
