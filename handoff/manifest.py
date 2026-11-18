from dataclasses import dataclass

from intake.stripes import Stripe
from recording.catalog import Recording
from recording.layout import RecordingLayout


@dataclass(frozen=True)
class PackageManifest:
    recording_id: str
    layout: RecordingLayout
    stripes: tuple[Stripe, ...]


def build_manifest(recording: Recording, stripes) -> PackageManifest:
    selected = tuple(stripes)
    if not selected:
        raise ValueError('a package needs at least one stripe')
    if any(item.recording_id != recording.recording_id for item in selected):
        raise ValueError('all selected stripes must belong to the recording')
    if len({item.stripe_id for item in selected}) != len(selected):
        raise ValueError('selected stripe ids must be unique')
    return PackageManifest(recording.recording_id, recording.layout, selected)
