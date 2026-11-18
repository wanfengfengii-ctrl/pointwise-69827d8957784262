import json
import sqlite3

from intake.observations import DirectObservation
from intake.parity import ParityEvidence
from intake.slot_map import SlotMap
from intake.stripes import Stripe, build_stripe_batch
from recording.batch import bind_capture_batch
from recording.catalog import RecordingCatalog


class StripeStore:
    def __init__(self, connection: sqlite3.Connection, catalog: RecordingCatalog):
        self.connection = connection
        self.catalog = catalog

    def initialize(self):
        self.connection.executescript('CREATE TABLE IF NOT EXISTS capture_batches (batch_id TEXT PRIMARY KEY, recording_id TEXT NOT NULL); CREATE TABLE IF NOT EXISTS stripes (stripe_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, recording_id TEXT NOT NULL); CREATE TABLE IF NOT EXISTS stripe_slots (stripe_id TEXT NOT NULL, slot INTEGER NOT NULL, position TEXT NOT NULL, PRIMARY KEY(stripe_id, slot)); CREATE TABLE IF NOT EXISTS direct_evidence (recording_id TEXT NOT NULL, evidence_id TEXT NOT NULL, stripe_id TEXT NOT NULL, slot INTEGER NOT NULL, value INTEGER NOT NULL, PRIMARY KEY(recording_id, evidence_id)); CREATE TABLE IF NOT EXISTS parity_evidence (recording_id TEXT NOT NULL, evidence_id TEXT NOT NULL, stripe_id TEXT NOT NULL, slots_json TEXT NOT NULL, value INTEGER NOT NULL, PRIMARY KEY(recording_id, evidence_id))')
        self.connection.commit()

    def ingest(self, recording_id: str, stripe_specs, batch_id: str | None = None):
        recording = self.catalog.get(recording_id)
        batch = bind_capture_batch(recording, batch_id)
        candidate = build_stripe_batch(batch, stripe_specs)
        with self.connection:
            if self.connection.execute('SELECT 1 FROM capture_batches WHERE batch_id = ?', (batch.batch_id,)).fetchone():
                raise ValueError('batch id already exists')
            for stripe in candidate.stripes:
                if self.connection.execute('SELECT 1 FROM stripes WHERE stripe_id = ?', (stripe.stripe_id,)).fetchone():
                    raise ValueError('stripe id already exists')
                self.connection.execute('INSERT INTO stripes(stripe_id, batch_id, recording_id) VALUES (?, ?, ?)', (stripe.stripe_id, stripe.batch_id, stripe.recording_id))
                for slot, position in enumerate(stripe.slot_map.positions):
                    self.connection.execute('INSERT INTO stripe_slots(stripe_id, slot, position) VALUES (?, ?, ?)', (stripe.stripe_id, slot, position))
                for observation in stripe.observations:
                    if self._evidence_exists(recording_id, observation.evidence_id):
                        raise ValueError('recording evidence id already exists')
                    self.connection.execute('INSERT INTO direct_evidence(recording_id, evidence_id, stripe_id, slot, value) VALUES (?, ?, ?, ?, ?)', (recording_id, observation.evidence_id, stripe.stripe_id, observation.slot, observation.value))
                for parity in stripe.parities:
                    if self._evidence_exists(recording_id, parity.evidence_id):
                        raise ValueError('recording evidence id already exists')
                    self.connection.execute('INSERT INTO parity_evidence(recording_id, evidence_id, stripe_id, slots_json, value) VALUES (?, ?, ?, ?, ?)', (recording_id, parity.evidence_id, stripe.stripe_id, json.dumps(list(parity.slots)), parity.value))
            self.connection.execute('INSERT INTO capture_batches(batch_id, recording_id) VALUES (?, ?)', (batch.batch_id, recording_id))
        return tuple(stripe.stripe_id for stripe in candidate.stripes)

    def _evidence_exists(self, recording_id, evidence_id):
        return bool(self.connection.execute('SELECT 1 FROM direct_evidence WHERE recording_id = ? AND evidence_id = ?', (recording_id, evidence_id)).fetchone() or self.connection.execute('SELECT 1 FROM parity_evidence WHERE recording_id = ? AND evidence_id = ?', (recording_id, evidence_id)).fetchone())

    def read_selection(self, stripe_ids):
        result = []
        for stripe_id in stripe_ids:
            row = self.connection.execute('SELECT batch_id, recording_id FROM stripes WHERE stripe_id = ?', (stripe_id,)).fetchone()
            if row is None:
                raise KeyError(stripe_id)
            batch_id, recording_id = row
            mapping = tuple(item[0] for item in self.connection.execute('SELECT position FROM stripe_slots WHERE stripe_id = ? ORDER BY slot', (stripe_id,)))
            slot_map = SlotMap(mapping)
            observations = tuple(DirectObservation(item[0], item[1], item[2]) for item in self.connection.execute('SELECT evidence_id, slot, value FROM direct_evidence WHERE stripe_id = ? ORDER BY evidence_id', (stripe_id,)))
            parities = tuple(ParityEvidence(item[0], tuple(json.loads(item[1])), item[2]) for item in self.connection.execute('SELECT evidence_id, slots_json, value FROM parity_evidence WHERE stripe_id = ? ORDER BY evidence_id', (stripe_id,)))
            result.append(Stripe(stripe_id, batch_id, recording_id, slot_map, observations, parities))
        return tuple(result)
