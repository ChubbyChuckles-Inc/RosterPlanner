"""Sandbox parse helpers for the ingestion lab panel."""

from __future__ import annotations

__all__ = ["SandboxMixin"]


class SandboxMixin:
    """Provide sandbox handlers for parsing HTML fragments."""

    def _on_sandbox_clear_clicked(self) -> None:
        try:
            self.sandbox_input.clear()
            self.sandbox_output.clear()
        except Exception as e:  # pragma: no cover - defensive
            self._append_log(f"Sandbox clear failed: {e}")

    def _on_sandbox_parse_clicked(self) -> None:
        frag = self.sandbox_input.toPlainText().strip()
        if not frag:
            self.sandbox_output.setPlainText("(No fragment provided)")
            return
        try:
            rule_set = self._parse_ruleset_from_editor()
        except Exception as e:
            self.sandbox_output.setPlainText(f"Rule parse error: {e}")
            self._append_log(f"Sandbox rule parse error: {e}")
            return
        try:
            from gui.ingestion.rule_parse_preview import generate_parse_preview  # type: ignore

            preview = generate_parse_preview(
                rule_set,
                frag,
                apply_transforms=self.chk_sandbox_transforms.isChecked(),
                capture_performance=False,
            )
        except Exception as e:  # pragma: no cover - unexpected failure path
            self.sandbox_output.setPlainText(f"Sandbox parse failed: {e}")
            self._append_log(f"Sandbox parse failed: {e}")
            return

        lines: list[str] = []
        lines.append(
            f"Resources: {len(preview.summaries)} | Nodes: {preview.node_count} | Time: {preview.parse_time_ms:.1f} ms"
        )
        for summ in preview.summaries:
            warn_count = len(summ.warnings)
            lines.append(
                f"- {summ.resource} ({summ.kind}) records={summ.record_count} warnings={warn_count}"
            )
            recs = preview.extracted_records.get(summ.resource, [])
            for ridx, rec in enumerate(recs[:2]):
                lines.append(f"  rec[{ridx}]: {rec}")
            if warn_count:
                for w in summ.warnings[:3]:
                    lines.append(f"  warn: {w}")
        if preview.errors:
            lines.append("Errors/Warns:")
            for err in preview.errors[:5]:
                lines.append(
                    f"  {err.get('severity','info')}: {err.get('resource')} -> {err.get('message')}"
                )
        self.sandbox_output.setPlainText("\n".join(lines))
        self._append_log(
            f"Sandbox parsed fragment (resources={len(preview.summaries)} total_records={sum(s.record_count for s in preview.summaries)})"
        )
