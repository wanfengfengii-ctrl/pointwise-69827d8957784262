import sqlite3

from handoff.codec import EvidencePackage, decode_package, encode_package


class PackageCommitError(RuntimeError):
    pass


class PackageStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('CREATE TABLE IF NOT EXISTS packages (package_id TEXT PRIMARY KEY, recording_id TEXT NOT NULL, payload TEXT NOT NULL)')
        self.connection.commit()

    def commit_package(self, package: EvidencePackage, fail: bool = False):
        payload = encode_package(package)
        try:
            with self.connection:
                if self.connection.execute('SELECT 1 FROM packages WHERE package_id = ?', (package.package_id,)).fetchone():
                    raise ValueError('package id already exists')
                self.connection.execute('INSERT INTO packages(package_id, recording_id, payload) VALUES (?, ?, ?)', (package.package_id, package.recording_id, payload))
                if fail:
                    raise PackageCommitError('injected package commit failure')
        except PackageCommitError:
            raise
        return package.package_id

    def load_payload(self, package_id: str) -> str:
        row = self.connection.execute('SELECT payload FROM packages WHERE package_id = ?', (package_id,)).fetchone()
        if row is None:
            raise KeyError(package_id)
        return row[0]

    def load_package(self, package_id: str) -> EvidencePackage:
        return decode_package(self.load_payload(package_id))

    def list_ids(self):
        return tuple(item[0] for item in self.connection.execute('SELECT package_id FROM packages ORDER BY package_id'))

    def load_parent(self, report_id: str, report_store):
        report = report_store.load_report(report_id)
        return self.load_package(report.package_id)
