"""Parse Benchmarking (Milestone 7.10.39)

Provides a minimal facility to run A/B rule set variants over a selected batch
of HTML files and compare aggregate performance + record deltas. This first
implementation focuses on simplicity and synchronous execution ("parallel" in
the milestone title will be introduced in a later enhancement—here we prepare
the structure so an executor pool can be plugged in without changing public
APIs).

Core Concepts:
 - BenchmarkVariant: name + raw rules JSON text (parsed into RuleSet)
 - run_benchmark(variants, html_by_file) -> list of BenchmarkResult with timing
   stats (wall time, avg per file, records extracted) and basic diff vs first
   variant (A) for subsequent variants (B, C...).
 - BenchmarkDialog: simple ChromeDialog UI to paste two rule JSON blobs (A & B),
   pick a file sample size (first N HTML files), run, and display results.

Diff Strategy:
 - For each resource present in both variant outputs we compare row counts.
 - Row-level deep diffs are deferred; this stage is concerned with macro metrics.

Extensibility:
 - Future parallelism: accept an optional executor (ThreadPoolExecutor) in
   run_benchmark.
 - Future metrics: memory delta averages, transform error counts, warning deltas.

Security / Validation:
 - Relies on existing rule_schema validation via RuleSet.from_mapping.
 - Any parse errors encapsulated per-variant; a failing variant does not abort others.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Mapping, Any, Optional, Iterable
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .rule_schema import RuleSet, RuleError
from .rule_parse_preview import generate_parse_preview

try:  # pragma: no cover
    from gui.components.chrome_dialog import ChromeDialog
except Exception:  # pragma: no cover
    ChromeDialog = object  # type: ignore[misc]

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QListWidget,
    QListWidgetItem,
)

__all__ = [
    "BenchmarkVariant",
    "BenchmarkResult",
    "run_benchmark",
    "BenchmarkDialog",
]


@dataclass
class BenchmarkVariant:
    name: str
    raw_rules: str


@dataclass
class BenchmarkResult:
    variant: str
    total_ms: float
    avg_ms_per_file: float
    total_records: int
    resource_row_counts: Dict[str, int]
    error: Optional[str] = None
    diff_vs_base: Dict[str, int] | None = None  # resource -> (row_count_delta)

    def summary_line(self) -> str:  # pragma: no cover - trivial formatting
        if self.error:
            return f"{self.variant}: ERROR {self.error}"
        return (
            f"{self.variant}: total={self.total_ms:.1f}ms avg={self.avg_ms_per_file:.2f}ms "
            f"records={self.total_records} resources={len(self.resource_row_counts)}"
        )


def _parse_rules(raw: str) -> RuleSet:
    payload = json.loads(raw or "{}")
    return RuleSet.from_mapping(payload)


def _extract_with_rules(rs: RuleSet, item: tuple[str, str]) -> Dict[str, int]:
    """Extract a single (file, html) pair returning resource -> row count.

    Kept small to enable future richer metrics (per-file timing, errors) without
    touching the core parallel orchestration logic.
    """
    _fpath, html = item
    counts: Dict[str, int] = {}
    preview = generate_parse_preview(rs, html, apply_transforms=True, capture_performance=False)
    for rname, rows in preview.extracted_records.items():
        counts[rname] = counts.get(rname, 0) + len(rows)
    return counts


def run_benchmark(
    variants: List[BenchmarkVariant],
    html_by_file: Mapping[str, str],
    *,
    max_workers: int | None = None,
) -> List[BenchmarkResult]:
    """Run benchmark across variants.

    Parameters
    ----------
    variants: list[BenchmarkVariant]
        Rule set variants (first treated as baseline for diff computation).
    html_by_file: Mapping[str, str]
        Mapping of filename -> raw HTML content to parse.
    max_workers: int | None, keyword-only
        If >1 enables parallel extraction across files using a ThreadPoolExecutor.
        The rule set is shared (read-only) across tasks; results are merged after.

    Returns
    -------
    list[BenchmarkResult]
        Timing + aggregate metrics for each variant with diff vs baseline.
    """
    results: List[BenchmarkResult] = []
    base_counts: Dict[str, int] | None = None
    items: Iterable[tuple[str, str]] = list(html_by_file.items())
    for idx, var in enumerate(variants):
        t0 = time.perf_counter()
        try:
            rs = _parse_rules(var.raw_rules)
        except (RuleError, json.JSONDecodeError) as e:
            results.append(
                BenchmarkResult(
                    variant=var.name,
                    total_ms=0.0,
                    avg_ms_per_file=0.0,
                    total_records=0,
                    resource_row_counts={},
                    error=str(e),
                )
            )
            continue
        resource_row_counts: Dict[str, int] = {}
        if max_workers and max_workers > 1 and len(items) > 1:
            # Parallel fan-out
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                fut_map = {ex.submit(_extract_with_rules, rs, it): it for it in items}
                for fut in as_completed(fut_map):  # noqa: B007 - map needed for future extension
                    counts = fut.result()
                    for rname, cnt in counts.items():
                        resource_row_counts[rname] = resource_row_counts.get(rname, 0) + cnt
        else:
            # Sequential fallback
            for it in items:
                counts = _extract_with_rules(rs, it)
                for rname, cnt in counts.items():
                    resource_row_counts[rname] = resource_row_counts.get(rname, 0) + cnt
        total_records = sum(resource_row_counts.values())
        total_ms = (time.perf_counter() - t0) * 1000.0
        avg_ms = total_ms / max(1, len(items))
        br = BenchmarkResult(
            variant=var.name,
            total_ms=total_ms,
            avg_ms_per_file=avg_ms,
            total_records=total_records,
            resource_row_counts=resource_row_counts,
        )
        if idx == 0:
            base_counts = resource_row_counts
        else:
            if base_counts is not None:
                diff: Dict[str, int] = {}
                keys = set(base_counts.keys()) | set(resource_row_counts.keys())
                for k in keys:
                    diff[k] = resource_row_counts.get(k, 0) - base_counts.get(k, 0)
                br.diff_vs_base = diff
        results.append(br)
    return results


class BenchmarkDialog(ChromeDialog):  # type: ignore[misc]
    def __init__(self, parent=None, sample_files: Mapping[str, str] | None = None):  # noqa: D401
        super().__init__(parent, title="Parse Benchmark")
        self.setObjectName("ParseBenchmarkDialog")
        try:
            self.resize(880, 600)
        except Exception:  # pragma: no cover
            pass
        lay = self.content_layout() if hasattr(self, "content_layout") else QVBoxLayout(self)
        # Variant editors
        row = QHBoxLayout()
        self.rules_a = QPlainTextEdit()
        self.rules_a.setPlaceholderText("Variant A rules JSON")
        self.rules_b = QPlainTextEdit()
        self.rules_b.setPlaceholderText("Variant B rules JSON (optional)")
        row.addWidget(self.rules_a, 1)
        row.addWidget(self.rules_b, 1)
        lay.addLayout(row, 1)
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Sample N:"))
        self.sample_spin = QSpinBox()
        self.sample_spin.setRange(1, 500)
        self.sample_spin.setValue(5)
        ctrl.addWidget(self.sample_spin)
        self.btn_run = QPushButton("Run Benchmark")
        ctrl.addWidget(self.btn_run)
        ctrl.addStretch(1)
        lay.addLayout(ctrl)
        self.results_list = QListWidget()
        lay.addWidget(self.results_list, 2)
        self.close_btn = QPushButton("Close")
        cbar = QHBoxLayout()
        cbar.addStretch(1)
        cbar.addWidget(self.close_btn)
        lay.addLayout(cbar)
        try:  # pragma: no cover
            self.close_btn.clicked.connect(self.close)  # type: ignore[attr-defined]
            self.btn_run.clicked.connect(self._on_run_clicked)  # type: ignore[attr-defined]
        except Exception:
            pass
        self._html_source = dict(sample_files or {})

    def set_sample_files(self, html_by_file: Mapping[str, str]) -> None:  # noqa: D401
        self._html_source = dict(html_by_file)

    def _gather_sample(self) -> Dict[str, str]:  # noqa: D401
        n = self.sample_spin.value()
        items = list(self._html_source.items())[:n]
        return {k: v for k, v in items}

    def _on_run_clicked(self) -> None:  # noqa: D401
        self.results_list.clear()
        raw_a = self.rules_a.toPlainText().strip()
        raw_b = self.rules_b.toPlainText().strip()
        variants = []
        if raw_a:
            variants.append(BenchmarkVariant("A", raw_a))
        if raw_b:
            variants.append(BenchmarkVariant("B", raw_b))
        if not variants:
            QListWidgetItem("No variants provided", self.results_list)
            return
        sample = self._gather_sample()
        results = run_benchmark(variants, sample)
        for res in results:
            QListWidgetItem(res.summary_line(), self.results_list)
            if res.diff_vs_base:
                for rname, delta in sorted(res.diff_vs_base.items()):
                    if delta:
                        QListWidgetItem(f"  {rname}: Δ{delta}", self.results_list)
