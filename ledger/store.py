import sqlite3
from dataclasses import dataclass

from handoff.codec import EvidencePackage, decode_package, encode_package

from ledger.reports import ShiftReport, decode_report, encode_report


@dataclass(frozen=True)
class CommittedReport:
    report_id: str
    package_id: str


class ReportStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('CREATE TABLE IF NOT EXISTS reports (report_id TEXT PRIMARY KEY, package_id TEXT NOT NULL, payload TEXT NOT NULL)')
        self.connection.execute(
            'CREATE TABLE IF NOT EXISTS report_parents (package_id TEXT PRIMARY KEY, payload TEXT NOT NULL)'
        )
        self.connection.commit()

    def commit_report(self, report: ShiftReport, package: EvidencePackage, fail: bool = False) -> CommittedReport:
        if report.package_id != package.package_id:
            raise ValueError('report parent package does not match')
        payload = encode_package(package)
        with self.connection:
            self.connection.execute(
                'INSERT INTO report_parents (package_id, payload) VALUES (?, ?) '
                'ON CONFLICT (package_id) DO NOTHING',
                (package.package_id, payload),
            )
            stored = self.connection.execute(
                'SELECT payload FROM report_parents WHERE package_id = ?', (package.package_id,)
            ).fetchone()[0]
            if stored != payload:
                raise ValueError('package id is already bound to different frozen evidence')
            if self.connection.execute('SELECT 1 FROM reports WHERE report_id = ?', (report.report_id,)).fetchone():
                raise ValueError('report id already exists')
            self.connection.execute('INSERT INTO reports(report_id, package_id, payload) VALUES (?, ?, ?)', (report.report_id, report.package_id, encode_report(report)))
            if fail:
                raise RuntimeError('injected report commit failure')
        return CommittedReport(report.report_id, report.package_id)

    def load_parent(self, report_id: str) -> EvidencePackage:
        row = self.connection.execute(
            'SELECT report_parents.payload FROM reports JOIN report_parents USING (package_id) '
            'WHERE reports.report_id = ?',
            (report_id,),
        ).fetchone()
        if row is None:
            raise KeyError(report_id)
        return decode_package(row[0])

    def load_report(self, report_id: str) -> ShiftReport:
        row = self.connection.execute('SELECT payload FROM reports WHERE report_id = ?', (report_id,)).fetchone()
        if row is None:
            raise KeyError(report_id)
        return decode_report(row[0])

    def list_ids(self):
        return tuple(item[0] for item in self.connection.execute('SELECT report_id FROM reports ORDER BY report_id'))
