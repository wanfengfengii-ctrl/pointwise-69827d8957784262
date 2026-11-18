from recording.layout import RecordingLayout


class InvalidRecording(ValueError):
    pass


def validate_registration(recording_id: str, positions) -> RecordingLayout:
    if not isinstance(recording_id, str) or not recording_id.strip():
        raise InvalidRecording('recording id must be a non-empty string')
    if isinstance(positions, (str, bytes)) or not positions:
        raise InvalidRecording('recording positions are required')
    try:
        normalized = tuple(positions)
        return RecordingLayout(normalized)
    except (TypeError, ValueError) as exc:
        raise InvalidRecording(str(exc)) from exc
