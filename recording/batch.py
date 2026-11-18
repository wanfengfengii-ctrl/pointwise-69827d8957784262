import uuid
from dataclasses import dataclass

from recording.catalog import Recording
from recording.layout import RecordingLayout


@dataclass(frozen=True)
class CaptureBatch:
    batch_id: str
    recording_id: str
    layout: RecordingLayout


def bind_capture_batch(recording: Recording, batch_id: str | None = None) -> CaptureBatch:
    chosen_id = batch_id or uuid.uuid4().hex
    if not isinstance(chosen_id, str) or not chosen_id.strip():
        raise ValueError('batch id must be a non-empty string')
    return CaptureBatch(chosen_id, recording.recording_id, recording.layout)
