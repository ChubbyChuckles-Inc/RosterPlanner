"""Export Service (Milestone 5.6)

Provides lightweight CSV / JSON export utilities for current view data.

Design goals:
 - No direct widget traversal in service (views expose structured data)
 - Pure functions where possible for easy unit testing
 - Minimal dependencies (use stdlib csv / json only)

Views participating in export should implement one (or both) of:
 - get_export_rows(): returns tuple (headers: list[str], rows: list[list[str]]) suitable for tabular export
 - get_export_payload(): returns any JSON-serializable structure

The MainWindow will detect the currently focused central widget (tab) and
call the appropriate method via this service.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Sequence, Any, Protocol, runtime_checkable, Iterable
import json
import csv
from io import StringIO

__all__ = [
    "ExportFormat",
    "ExportResult",
    "ExportService",
]


class ExportFormat:
    CSV = "csv"
    JSON = "json"


@dataclass
class ExportResult:
    format: str
    content: str
    suggested_extension: str


@runtime_checkable
class TabularExportable(Protocol):  # pragma: no cover - structural
    def get_export_rows(self) -> tuple[Sequence[str], Sequence[Sequence[str]]]: ...


@runtime_checkable
class JsonExportable(Protocol):  # pragma: no cover - structural
    def get_export_payload(self) -> Any: ...


class ExportService:
    """Facade for converting view data to serialized text.

    Usage:
        result = ExportService().export(widget, ExportFormat.CSV)
        path.write_text(result.content, encoding='utf-8')
    """

    def export(
        self,
        widget: Any,
        fmt: str,
        *,
        included_columns: Sequence[str] | None = None,
    ) -> ExportResult:
        """Export a widget's data.

        Parameters
        ----------
        widget: Any
            View implementing TabularExportable and/or JsonExportable.
        fmt: str
            ExportFormat.CSV or ExportFormat.JSON
        included_columns: Sequence[str] | None
            Optional subset of column header names to include (order respected).
            Only applies when exporting tabular data (or JSON fallback from tabular).
        """
        if fmt == ExportFormat.CSV:
            return self._export_csv(widget, included_columns=included_columns)
        if fmt == ExportFormat.JSON:
            return self._export_json(widget, included_columns=included_columns)
        raise ValueError(f"Unsupported export format: {fmt}")

    # CSV -----------------------------------------------------------------
    def _export_csv(
        self, widget: Any, *, included_columns: Sequence[str] | None = None
    ) -> ExportResult:
        if not isinstance(widget, TabularExportable):
            raise TypeError("Widget does not provide tabular export interface")
        headers, rows = widget.get_export_rows()
        if included_columns:
            # Build index map based on header names
            idxs = [headers.index(h) for h in included_columns if h in headers]
            headers = [h for h in headers if h in included_columns]
            # Filter rows
            rows = [[str(row[i]) for i in idxs] for row in rows]
        sio = StringIO()
        writer = csv.writer(sio)
        if headers:
            writer.writerow(list(headers))
        for row in rows:
            writer.writerow(list(row))
        return ExportResult(
            format=ExportFormat.CSV, content=sio.getvalue(), suggested_extension=".csv"
        )

    # JSON ----------------------------------------------------------------
    def _export_json(
        self, widget: Any, *, included_columns: Sequence[str] | None = None
    ) -> ExportResult:
        # Prefer JSON payload if available; fall back to tabular rows
        if isinstance(widget, JsonExportable):
            payload = widget.get_export_payload()
        elif isinstance(widget, TabularExportable):
            headers, rows = widget.get_export_rows()
            if included_columns:
                idxs = [headers.index(h) for h in included_columns if h in headers]
                headers = [h for h in headers if h in included_columns]
                rows = [[str(row[i]) for i in idxs] for row in rows]
            # Turn into list of dicts for readability
            payload = [dict(zip(headers, map(str, row))) for row in rows]
        else:
            raise TypeError("Widget does not provide export interface")
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        return ExportResult(format=ExportFormat.JSON, content=content, suggested_extension=".json")
