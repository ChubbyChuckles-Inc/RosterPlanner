"""Foreign key orphan detector service (Milestone 7.11.16).

Provides a reusable utility that scans the active SQLite database for
rows whose foreign key relationships reference missing parent rows. The
class relies on :class:`SchemaIntrospectionService` metadata to inspect
all declared foreign keys and generates a human-friendly report that can
be surfaced in the Database panel or exported for auditing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Iterable, List, Sequence, Tuple
import sqlite3

from .schema_introspection_service import (
    ForeignKeyInfo,
    SchemaIntrospectionService,
    TableInfo,
)

__all__ = [
    "ForeignKeyOrphanFinding",
    "ForeignKeyOrphanReport",
    "ForeignKeyOrphanDetector",
]


@dataclass(frozen=True)
class ForeignKeyOrphanFinding:
    """Represents orphaned rows for a specific foreign key constraint."""

    table: str
    columns: Tuple[str, ...]
    ref_table: str
    ref_columns: Tuple[str, ...]
    orphan_count: int
    sample_rows: Tuple[str, ...]

    @property
    def descriptor(self) -> str:
        """Return a concise string describing the foreign key relationship."""

        source = ", ".join(self.columns)
        target = ", ".join(self.ref_columns)
        return f"{self.table}({source}) -> {self.ref_table}({target})"


@dataclass(frozen=True)
class ForeignKeyOrphanReport:
    """Aggregated findings for a complete orphan scan."""

    findings: Tuple[ForeignKeyOrphanFinding, ...]
    scanned_at: datetime
    duration_s: float

    def total_orphans(self) -> int:
        """Return the sum of all orphaned rows across findings."""

        return sum(finding.orphan_count for finding in self.findings)


class ForeignKeyOrphanDetector:
    """Detect orphaned foreign key references within an SQLite database."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        schema: SchemaIntrospectionService,
    ) -> None:
        self._conn = conn
        self._schema = schema

    # ------------------------------------------------------------------
    def scan(self, *, sample_limit: int = 10) -> ForeignKeyOrphanReport:
        """Scan all foreign keys and return a report of orphaned rows."""

        if self._conn is None or self._schema is None:
            return ForeignKeyOrphanReport((), datetime.utcnow(), 0.0)
        start = perf_counter()
        tables = self._safe_describe_all()
        findings: List[ForeignKeyOrphanFinding] = []
        for table_name, info in tables.items():
            for constraint in self._group_foreign_keys(info.foreign_keys):
                finding = self._inspect_constraint(table_name, constraint, sample_limit)
                if finding is not None and finding.orphan_count > 0:
                    findings.append(finding)
        findings.sort(key=lambda f: (f.table.lower(), f.ref_table.lower(), f.columns))
        duration = perf_counter() - start
        return ForeignKeyOrphanReport(tuple(findings), datetime.utcnow(), duration)

    # ------------------------------------------------------------------
    def format_report(self, report: ForeignKeyOrphanReport) -> str:
        """Return a multi-line text representation of *report*."""

        timestamp = report.scanned_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            "Foreign key orphan report",
            f"Generated: {timestamp}",
            f"Findings: {len(report.findings)}",
            f"Total orphaned rows: {report.total_orphans()}",
            f"Scan duration: {report.duration_s * 1000:.1f} ms",
            "",
        ]
        if not report.findings:
            lines.append("No orphaned foreign key references detected.")
            return "\n".join(lines)
        for finding in report.findings:
            lines.append(f"- {finding.descriptor}: {finding.orphan_count} orphan row(s)")
            if finding.sample_rows:
                lines.append("  Samples:")
                for sample in finding.sample_rows:
                    lines.append(f"    • {sample}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def _safe_describe_all(self) -> dict[str, TableInfo]:
        try:
            return self._schema.describe_all()
        except Exception:
            return {}

    def _group_foreign_keys(
        self, foreign_keys: Sequence[ForeignKeyInfo]
    ) -> Iterable[List[ForeignKeyInfo]]:
        grouped: dict[int, List[ForeignKeyInfo]] = {}
        for fk in foreign_keys:
            key = fk.constraint_id
            grouped.setdefault(key, []).append(fk)
        for group in grouped.values():
            group.sort(key=lambda info: info.sequence)
            yield group

    def _inspect_constraint(
        self,
        table: str,
        constraint: Sequence[ForeignKeyInfo],
        sample_limit: int,
    ) -> ForeignKeyOrphanFinding | None:
        if not constraint:
            return None
        ref_table = constraint[0].ref_table
        columns = tuple(fk.column for fk in constraint)
        ref_columns = tuple(fk.ref_column for fk in constraint)
        nonnull_clause = " OR ".join(
            f"t.{self._quote_ident(column)} IS NOT NULL" for column in columns
        )
        if not nonnull_clause:
            nonnull_clause = "1=1"
        exists_conditions = " AND ".join(
            f"ref.{self._quote_ident(ref_col)} = t.{self._quote_ident(col)}"
            for col, ref_col in zip(columns, ref_columns)
        )
        try:
            count_sql = (
                f"SELECT COUNT(*) FROM {self._quote_ident(table)} AS t "
                f"WHERE ({nonnull_clause}) AND NOT EXISTS ("
                f"SELECT 1 FROM {self._quote_ident(ref_table)} AS ref WHERE {exists_conditions}"
                ")"
            )
            cursor = self._conn.execute(count_sql)
            row = cursor.fetchone()
            if row is None or row[0] is None:
                return None
            orphan_count = int(row[0])
        except Exception:
            return None
        if orphan_count <= 0:
            return ForeignKeyOrphanFinding(
                table=table,
                columns=columns,
                ref_table=ref_table,
                ref_columns=ref_columns,
                orphan_count=0,
                sample_rows=(),
            )
        samples: List[str] = []
        select_columns = ", ".join(f"t.{self._quote_ident(col)}" for col in columns)
        sample_sql = (
            f"SELECT {select_columns} FROM {self._quote_ident(table)} AS t "
            f"WHERE ({nonnull_clause}) AND NOT EXISTS ("
            f"SELECT 1 FROM {self._quote_ident(ref_table)} AS ref WHERE {exists_conditions}"
            ") LIMIT ?"
        )
        try:
            cur = self._conn.execute(sample_sql, (max(1, sample_limit),))
            for row in cur.fetchall():
                samples.append(self._format_sample(columns, row))
        except Exception:
            samples = []
        return ForeignKeyOrphanFinding(
            table=table,
            columns=columns,
            ref_table=ref_table,
            ref_columns=ref_columns,
            orphan_count=orphan_count,
            sample_rows=tuple(samples),
        )

    @staticmethod
    def _quote_ident(name: str) -> str:
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    @staticmethod
    def _format_sample(columns: Sequence[str], values: Sequence[object]) -> str:
        parts = []
        for column, value in zip(columns, values):
            parts.append(f"{column}={ForeignKeyOrphanDetector._stringify(value)}")
        return ", ".join(parts) if parts else "(no columns)"

    @staticmethod
    def _stringify(value: object) -> str:
        if value is None:
            return "NULL"
        text = str(value)
        text = text.replace("\n", " ").replace("\r", " ")
        if len(text) > 60:
            return f"{text[:57]}…"
        return text
