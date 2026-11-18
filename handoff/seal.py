import uuid

from handoff.codec import EvidencePackage, decode_package
from handoff.evidence import freeze_evidence
from handoff.manifest import build_manifest
from handoff.store import PackageStore
from intake.store import StripeStore
from recording.catalog import RecordingCatalog


def seal_package(catalog: RecordingCatalog, stripe_store: StripeStore, package_store: PackageStore, recording_id: str, stripe_ids, package_id: str | None = None, fail: bool = False):
    recording = catalog.get(recording_id)
    stripes = stripe_store.read_selection(stripe_ids)
    manifest = build_manifest(recording, stripes)
    package = EvidencePackage(package_id or uuid.uuid4().hex, recording_id, manifest.layout, tuple(item.stripe_id for item in manifest.stripes), freeze_evidence(manifest))
    return package_store.commit_package(package, fail=fail)


def export_package(package_store: PackageStore, package_id: str):
    return decode_package(package_store.load_payload(package_id))
