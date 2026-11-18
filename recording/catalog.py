import json
import sqlite3
from dataclasses import dataclass

from recording.layout import RecordingLayout
from recording.validation import InvalidRecording, validate_registration


@dataclass(frozen=True)
class Recording:
    recording_id: str
    layout: RecordingLayout


class RecordingCatalog:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('CREATE TABLE IF NOT EXISTS recordings (recording_id TEXT PRIMARY KEY, positions_json TEXT NOT NULL)')
        self.connection.commit()

    def register(self, recording_id: str, positions) -> Recording:
        layout = validate_registration(recording_id, positions)
        with self.connection:
            if self.connection.execute('SELECT 1 FROM recordings WHERE recording_id = ?', (recording_id,)).fetchone():
                raise InvalidRecording('recording id already exists')
            self.connection.execute(
                'INSERT INTO recordings(recording_id, positions_json) VALUES (?, ?)',
                (recording_id, json.dumps(list(layout.positions))),
            )
        return Recording(recording_id, layout)

    def get(self, recording_id: str) -> Recording:
        row = self.connection.execute('SELECT positions_json FROM recordings WHERE recording_id = ?', (recording_id,)).fetchone()
        if row is None:
            raise KeyError(recording_id)
        return Recording(recording_id, RecordingLayout(tuple(json.loads(row[0]))))
