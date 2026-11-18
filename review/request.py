from dataclasses import dataclass

from recording.layout import RecordingLayout


class InvalidReviewRequest(ValueError):
    pass


@dataclass(frozen=True)
class ReviewRequest:
    positions: tuple[str, ...]


def validate_request(layout: RecordingLayout, positions) -> ReviewRequest:
    if isinstance(positions, (str, bytes)) or positions is None:
        raise InvalidReviewRequest('review positions must be a sequence')
    requested = tuple(positions)
    if any(not layout.contains(position) for position in requested):
        raise InvalidReviewRequest('review request is outside the recording layout')
    return ReviewRequest(requested)
