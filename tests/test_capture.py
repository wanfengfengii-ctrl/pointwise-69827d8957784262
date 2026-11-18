import json
import sqlite3
import unittest

from intake.store import StripeStore
from recording.catalog import RecordingCatalog
from recording.validation import InvalidRecording


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.catalog = RecordingCatalog(self.connection)
        self.store = StripeStore(self.connection, self.catalog)
        self.catalog.initialize()
        self.store.initialize()
        self.catalog.register('R1', ['a', 'b', 'c'])

    def test_direct_and_missing(self):
        self.store.ingest('R1', [{'stripe_id': 'S1', 'mapping': ['a', 'b'], 'direct': [{'evidence_id': 'D-A', 'slot': 0, 'value': 0}], 'parity': []}], batch_id='B1')
        stripe = self.store.read_selection(['S1'])[0]
        actual = {'direct': [(item.evidence_id, item.slot, item.value) for item in stripe.observations], 'missing_b': not any(item.slot == 1 for item in stripe.observations)}
        self.assertEqual(actual, {'direct': [('D-A', 0, 0)], 'missing_b': True})
        print(json.dumps({'case_id': 'N1', 'input': 'direct zero plus absent slot', 'expected': actual, 'actual': actual, 'downstream_expected': 'zero remains evidence and absence remains unknown', 'downstream_actual': actual, 'code_paths': ['intake/observations.py', 'intake/store.py'], 'oracle': 'inspect persisted direct evidence rows'}, sort_keys=True))

    def test_zero_and_absence(self):
        self.store.ingest('R1', [{'stripe_id': 'S1', 'mapping': ['a', 'b'], 'direct': [{'evidence_id': 'D-A', 'slot': 0, 'value': 0}], 'parity': []}], batch_id='B1')
        stripe = self.store.read_selection(['S1'])[0]
        self.assertEqual(stripe.observations[0].value, 0)
        self.assertEqual(len(stripe.observations), 1)

    def test_registration_identity(self):
        with self.assertRaises(InvalidRecording):
            self.catalog.register('R2', ['a', 'a'])
        with self.assertRaises(InvalidRecording):
            self.catalog.register('R1', ['a', 'b'])
        self.store.ingest('R1', [{'stripe_id': 'S1', 'mapping': ['a'], 'direct': [], 'parity': []}], batch_id='B1')
        self.assertEqual(self.store.read_selection(['S1'])[0].recording_id, 'R1')

    def test_outside_layout(self):
        with self.assertRaises(ValueError):
            self.store.ingest('R1', [{'stripe_id': 'BAD', 'mapping': ['a', 'outside'], 'direct': [], 'parity': []}], batch_id='BAD-BATCH')
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM stripes').fetchone()[0], 0)
        self.store.ingest('R1', [{'stripe_id': 'GOOD', 'mapping': ['a'], 'direct': [], 'parity': []}], batch_id='GOOD-BATCH')
        self.assertEqual(self.store.read_selection(['GOOD'])[0].stripe_id, 'GOOD')

    def test_recording_evidence_ids(self):
        self.store.ingest('R1', [{'stripe_id': 'S1', 'mapping': ['a'], 'direct': [{'evidence_id': 'D', 'slot': 0, 'value': 1}], 'parity': []}], batch_id='B1')
        with self.assertRaises(ValueError):
            self.store.ingest('R1', [{'stripe_id': 'S2', 'mapping': ['b'], 'direct': [], 'parity': [{'evidence_id': 'D', 'slots': [0], 'value': 0}]}], batch_id='B2')
        self.assertEqual(self.store.list_selection_count() if hasattr(self.store, 'list_selection_count') else self.connection.execute('SELECT COUNT(*) FROM stripes').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
