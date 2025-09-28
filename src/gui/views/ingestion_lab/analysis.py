"""Data analysis actions for the ingestion lab panel."""

from __future__ import annotations

import json
from typing import Dict

from PyQt6.QtCore import Qt

from gui.ingestion.rule_example_sampler import generate_example_rows

# Optional backends mirror the defensive imports from the original module.
try:  # pragma: no cover - import guard if module missing in earlier migrations
    from gui.ingestion.rule_field_coverage import compute_field_coverage
except Exception:  # pragma: no cover
    compute_field_coverage = None  # type: ignore

try:  # pragma: no cover
    from gui.ingestion.rule_field_coverage import FieldCoverageReport  # noqa: F401 - re-export
except Exception:  # pragma: no cover
    FieldCoverageReport = None  # type: ignore

try:  # pragma: no cover
    from gui.ingestion.rule_orphan import compute_orphan_fields
except Exception:  # pragma: no cover
    compute_orphan_fields = None  # type: ignore

try:  # pragma: no cover
    from gui.ingestion.rule_quality_gates import evaluate_quality_gates
except Exception:  # pragma: no cover
    evaluate_quality_gates = None  # type: ignore

__all__ = ["AnalysisMixin"]


class AnalysisMixin:
    """Encapsulate example rows, coverage, and related analytics."""

    def _on_example_rows_clicked(self) -> None:
        """Generate synthetic example rows for current rules and show them."""

        try:
            rule_set = self._parse_ruleset_from_editor()
        except Exception as exc:
            message = f"Example rows unavailable: {exc}"
            self.preview_area.setPlainText(message)
            self._last_preview_plain = message
            self._append_log(f"Example rows ERROR: {exc}")
            return

        samples = generate_example_rows(rule_set)
        if not samples:
            message = "Example rows: no eligible resources with fields or columns."
            self.preview_area.setPlainText(message)
            self._last_preview_plain = message
            self._append_log("Example rows: no resources")
            return

        lines: list[str] = ["Example Data Rows (synthetic sampler)"]
        total = 0
        for resource, rows in samples.items():
            lines.append("")
            lines.append(f"Resource: {resource}")
            lines.append("  Field | Raw -> Normalized")
            for row in rows:
                flag = "⚠ " if row.is_outlier else ""
                note = f" [{row.note}]" if row.note else ""
                lines.append(f"  {flag}{row.field}: {row.raw!r} -> {row.normalized!r}{note}")
                total += 1
        output = "\n".join(lines)
        self.preview_area.setPlainText(output)
        self._last_preview_plain = output
        self._append_log(
            f"Example rows generated ({total} samples across {len(samples)} resources)"
        )

    def _on_field_coverage_clicked(self) -> None:
        if compute_field_coverage is None:  # pragma: no cover
            self._append_log("Field Coverage backend unavailable")
            return
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Coverage ERROR (rules): {e}")
            return
        html_map = self._gather_visible_file_html()
        if not html_map:
            self._append_log("Coverage: No visible files to analyze")
            return
        try:
            report = compute_field_coverage(rs, html_map)
        except Exception as e:  # pragma: no cover - defensive
            self._append_log(f"Coverage ERROR (compute): {e}")
            return
        self._last_field_coverage = report
        self._append_log(
            f"Field Coverage Overall: {report.overall_ratio:.2%} across {report.total_target_columns} columns"
        )
        for res in report.resources:
            miss = res.missing_columns()
            miss_txt = f" missing={','.join(miss)}" if miss else ""
            self._append_log(
                f"  {res.resource}: avg={res.average_coverage:.2%} fields={len(res.fields)}{miss_txt}"
            )
        self._append_log("— end coverage —")

    def _on_field_coverage_radar_clicked(self) -> None:  # pragma: no cover - UI heavy
        try:
            from gui.ingestion.field_coverage_radar import (
                categorize_coverage,
                FieldCoverageRadarWidget,
            )
        except Exception as e:
            self._append_log(f"Radar unavailable: import error {e}")
            return
        if not getattr(self, "_last_field_coverage", None):
            self._on_field_coverage_clicked()
        if not getattr(self, "_last_field_coverage", None):
            return
        report = self._last_field_coverage
        try:
            categories = categorize_coverage(report)
        except Exception as e:
            self._append_log(f"Radar categorization error: {e}")
            return
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

        dlg = QDialog(self)
        dlg.setWindowTitle("Field Coverage Radar")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Semantic Category Coverage"))
        radar = FieldCoverageRadarWidget(categories)
        lay.addWidget(radar, 1)
        dlg.resize(480, 360)
        dlg.exec()

    def field_coverage_snapshot(self) -> Dict[str, object]:
        if not self._last_field_coverage:
            return {}
        return self._last_field_coverage.to_mapping()  # type: ignore[no-any-return]

    def _on_orphan_fields_clicked(self) -> None:
        if compute_orphan_fields is None:  # pragma: no cover
            self._append_log("Orphan field backend unavailable")
            return
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Orphan ERROR (rules): {e}")
            return
        raw_text = (self.rule_editor.toPlainText() or "").strip()
        mapping_block = None
        try:
            js = json.loads(raw_text)
            mapping_block = js.get("mapping") if isinstance(js, dict) else None
            if mapping_block is not None and not isinstance(mapping_block, dict):
                mapping_block = None
        except Exception:
            mapping_block = None
        try:
            orphans = compute_orphan_fields(rs, mapping_block)
        except Exception as e:  # pragma: no cover
            self._append_log(f"Orphan ERROR (compute): {e}")
            return
        if not orphans:
            self._append_log("Orphans: none")
            return
        self._append_log(f"Orphans ({len(orphans)}):")
        for o in orphans[:25]:  # cap log spam
            self._append_log(f"  {o.resource}.{o.field} -> {o.suggestion}")
        if len(orphans) > 25:
            self._append_log(f"  ... {len(orphans)-25} more")

    def _on_quality_gates_clicked(self) -> None:
        if evaluate_quality_gates is None:  # pragma: no cover
            self._append_log("Quality Gates backend unavailable")
            return
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Quality Gates ERROR (rules): {e}")
            return
        text = (self.rule_editor.toPlainText() or "").strip()
        gates_cfg = {}
        try:
            js = json.loads(text)
            gates_cfg = js.get("quality_gates", {}) if isinstance(js, dict) else {}
            if not isinstance(gates_cfg, dict):
                gates_cfg = {}
        except Exception:
            gates_cfg = {}
        if not gates_cfg:
            self._append_log("Quality Gates: no 'quality_gates' config block present")
            return
        html_map = self._gather_visible_file_html()
        if not html_map:
            self._append_log("Quality Gates: no visible files")
            return
        try:
            report = evaluate_quality_gates(rs, html_map, gates_cfg)
        except Exception as e:  # pragma: no cover
            self._append_log(f"Quality Gates ERROR (compute): {e}")
            return
        status = "PASS" if report.passed else f"FAIL ({report.failed_count} failing)"
        self._append_log(f"Quality Gates Result: {status}")
        for r in report.results[:50]:
            mark = "✅" if r.passed else "❌"
            self._append_log(
                f"  {mark} {r.resource}.{r.field} ratio={r.ratio:.2%} threshold={r.threshold:.2%}"
            )
        if len(report.results) > 50:
            self._append_log(f"  ... {len(report.results)-50} more")

    def _on_overlap_clicked(self) -> None:
        try:
            from gui.ingestion.rule_overlap import detect_overlaps  # type: ignore
        except Exception as e:  # pragma: no cover - import robustness
            self._append_log(f"Conflicts unavailable: import error {e}")
            return
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Conflicts ERROR (rules): {e}")
            return
        html_map = self._gather_visible_file_html()
        if not html_map:
            self._append_log("Conflicts: no visible HTML files")
            return
        sample_html = None
        try:
            sel_items = [
                it
                for it in self.file_tree.selectedItems()
                if isinstance(it.data(0, Qt.ItemDataRole.UserRole), dict)
                and "file" in it.data(0, Qt.ItemDataRole.UserRole)
            ]
            if sel_items:
                fpath = sel_items[0].data(0, Qt.ItemDataRole.UserRole).get("file")  # type: ignore[index]
                sample_html = html_map.get(fpath)
        except Exception:
            sample_html = None
        if not sample_html:
            sample_html = next(iter(html_map.values()))
        try:
            overlaps = detect_overlaps(rs, sample_html, min_jaccard=0.0)
        except Exception as e:  # pragma: no cover
            self._append_log(f"Conflicts ERROR (compute): {e}")
            return
        if not overlaps:
            self._append_log("Conflicts: none")
            return
        self._append_log(f"Conflicts ({len(overlaps)}) – top {min(len(overlaps), 30)} shown:")
        for rec in overlaps[:30]:
            self._append_log(
                f"  {rec.resource_a} vs {rec.resource_b} overlap={rec.overlap} jaccard={rec.jaccard:.3f} (|A|={rec.count_a} |B|={rec.count_b})"
            )
        if len(overlaps) > 30:
            self._append_log(f"  ... {len(overlaps)-30} more")
        self._append_log("— end conflicts —")
