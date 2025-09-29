"""Dialog launching helpers for secondary tools within the ingestion lab."""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

try:  # pragma: no cover
    from gui.services.service_locator import services as _services  # type: ignore
except Exception:  # pragma: no cover
    _services = None  # type: ignore

__all__ = ["ToolDialogsMixin"]


class ToolDialogsMixin:
    """Bundle dialog entrypoints for selector picker, regex tester, etc."""

    def _on_selector_picker_clicked(self) -> None:
        target_file = None
        items = self.file_tree.selectedItems()
        if items:
            data = items[0].data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and data.get("file"):
                target_file = data.get("file")
        if not target_file:
            for it in self._all_file_items:
                if not it.isHidden():
                    d = it.data(0, Qt.ItemDataRole.UserRole)
                    if isinstance(d, dict) and d.get("file"):
                        target_file = d.get("file")
                        break
        if not target_file:
            self._append_log("Selector Picker: no file available")
            return
        try:
            with open(target_file, "r", encoding="utf-8", errors="replace") as fh:
                html = fh.read()
        except Exception as e:  # pragma: no cover
            self._append_log(f"Selector Picker ERROR: {e}")
            return
        try:
            from gui.ingestion.selector_picker import SelectorPickerDialog
        except Exception as e:  # pragma: no cover
            self._append_log(f"Selector Picker import failed: {e}")
            return
        dlg = SelectorPickerDialog(html, self)
        if dlg.exec() == int(QDialog.DialogCode.Accepted):
            sel = dlg.selected_selector()
            if not sel:
                self._append_log("Selector Picker: no selection made")
                return
            cursor = self.rule_editor.textCursor()
            insertion = f"\n# selector-picked\nselector: '{sel}'\n"
            cursor.insertText(insertion)
            self._append_log(f"Selector Picker inserted: {sel}")

    def _on_regex_tester_clicked(self) -> None:
        sample = self.preview_area.toPlainText() or ""
        if not sample:
            for it in self._all_file_items:
                if it.isHidden():
                    continue
                data = it.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(data, dict) and data.get("file"):
                    try:
                        with open(data.get("file"), "r", encoding="utf-8", errors="replace") as fh:
                            sample = fh.read(1200)
                    except Exception:
                        sample = ""
                    break
        try:
            from gui.ingestion.regex_tester import RegexTesterDialog
        except Exception as e:  # pragma: no cover
            self._append_log(f"Regex Tester import failed: {e}")
            return
        dlg = RegexTesterDialog(sample_text=sample, parent=self)
        dlg.exec()

    def _on_expression_playground_clicked(self) -> None:
        try:
            from gui.ingestion.safe_expression_playground import SafeExpressionPlaygroundDialog
        except Exception as exc:  # pragma: no cover
            self._append_log(f"Expression Playground import failed: {exc}")
            return
        cursor = self.rule_editor.textCursor()
        selected_expr = cursor.selectedText().strip()
        sample_text = getattr(self, "_last_preview_plain", "") or ""
        if not sample_text:
            try:
                sample_text = self.sandbox_output.toPlainText().strip()
            except Exception:
                sample_text = ""
        if not sample_text:
            try:
                sample_text = self.preview_area.toPlainText().strip()
            except Exception:
                sample_text = ""
        try:
            dlg = SafeExpressionPlaygroundDialog(
                sample_text=sample_text,
                initial_expression=selected_expr,
                parent=self,
            )
        except RuntimeError as exc:
            self._append_log(f"Expression Playground unavailable: {exc}")
            return
        if dlg.exec() != int(QDialog.DialogCode.Accepted):
            self._append_log("Expression Playground: cancelled")
            return
        snippet = dlg.selected_snippet()
        if not snippet:
            self._append_log("Expression Playground: no snippet produced")
            return
        cursor.insertText(snippet)
        self._append_log("Expression Playground: inserted expr transform")

    def _on_import_html_fixture_clicked(self) -> None:
        try:
            from gui.ingestion.fixture_importer import HtmlFixtureImportDialog, save_html_fixture
        except Exception as exc:  # pragma: no cover
            self._append_log(f"Fixture importer unavailable: {exc}")
            return
        initial_snippet = ""
        try:
            initial_snippet = self.sandbox_output.toPlainText().strip()
        except Exception:
            initial_snippet = ""
        if not initial_snippet:
            try:
                initial_snippet = self.preview_area.toPlainText().strip()
            except Exception:
                initial_snippet = ""
        dialog = None
        if HtmlFixtureImportDialog is not None:
            dialog = HtmlFixtureImportDialog(self._base_dir, initial_snippet, self)
            if dialog.exec() == int(QDialog.DialogCode.Accepted):
                result = dialog.last_result()
                if result is not None:
                    rel_path = result.path.relative_to(self._base_dir)
                    self._append_log(f"Fixture saved -> {rel_path}")
                else:
                    self._append_log("Fixture import: no result returned")
            else:
                self._append_log("Fixture import: cancelled")
            return
        # Headless fallback: save immediately using helper
        try:
            result = save_html_fixture(self._base_dir, initial_snippet or "<html></html>")
        except Exception as exc:  # pragma: no cover
            self._append_log(f"Fixture import failed: {exc}")
            return
        rel_path = result.path.relative_to(self._base_dir)
        self._append_log(f"Fixture saved (headless) -> {rel_path}")

    def _on_inline_yaml_editor_clicked(self) -> None:
        rules_text = self.rule_editor.toPlainText()
        if not rules_text.strip():
            self._append_log("Inline YAML: rule editor is empty")
            return
        try:
            from gui.ingestion.inline_yaml_editor import InlineYamlFragmentDialog
            from gui.ingestion.rule_yaml_fragment import FragmentError
        except Exception as e:  # pragma: no cover
            self._append_log(f"Inline YAML import failed: {e}")
            return
        try:
            dlg = InlineYamlFragmentDialog(rules_text, self)
        except FragmentError as exc:
            self._append_log(f"Inline YAML: {exc}")
            return
        if dlg.exec() != int(QDialog.DialogCode.Accepted):
            self._append_log("Inline YAML: cancelled")
            return
        new_text = dlg.updated_rules_text()
        if not new_text:
            self._append_log("Inline YAML: no changes")
            return
        if new_text == rules_text:
            self._append_log("Inline YAML: no changes applied")
            return
        self.rule_editor.setPlainText(new_text)
        self._append_log("Inline YAML: fragment merged into rules editor")

    def _on_derived_fields_clicked(self) -> None:
        try:
            from gui.ingestion.derived_field_composer import (
                DerivedFieldComposerDialog,
                update_ruleset_with_derived,
            )
        except Exception as e:  # pragma: no cover
            self._append_log(f"Derived Fields import failed: {e}")
            return
        rules_txt = self.rule_editor.toPlainText()
        dlg = DerivedFieldComposerDialog(rules_txt, self)
        if dlg.exec() != int(QDialog.DialogCode.Accepted):
            self._append_log("Derived Fields: cancelled")
            return
        derived_map = dlg.derived_fields()
        if not derived_map:
            self._append_log("Derived Fields: none added")
            return
        try:
            new_text = update_ruleset_with_derived(rules_txt, derived_map)
        except Exception as e:  # pragma: no cover
            self._append_log(f"Derived Fields update failed: {e}")
            return
        self.rule_editor.setPlainText(new_text)
        self._append_log("Derived Fields added: " + ", ".join(sorted(derived_map.keys())))

    def _on_dependency_graph_clicked(self) -> None:
        try:
            from gui.ingestion.dependency_graph import DependencyGraphDialog
        except Exception as e:  # pragma: no cover
            self._append_log(f"Dep Graph import failed: {e}")
            return
        dlg = DependencyGraphDialog(self.rule_editor.toPlainText(), self)
        dlg.exec()

    def _on_benchmark_clicked(self) -> None:
        try:
            from gui.ingestion.parse_benchmark import BenchmarkDialog
        except Exception as e:  # pragma: no cover
            self._append_log(f"Benchmark import failed: {e}")
            return
        sample_map: dict[str, str] = {}
        max_files = 50
        for it in self._all_file_items:
            if it.isHidden():
                continue
            if len(sample_map) >= max_files:
                break
            data = it.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(data, dict) or "file" not in data:
                continue
            fpath = data.get("file")
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    sample_map[fpath] = fh.read()
            except Exception:
                continue
        dlg = BenchmarkDialog(self, sample_files=sample_map)
        dlg.exec()
        self._append_log(
            f"Benchmark run ready with {len(sample_map)} sample files (provide A/B rules in dialog)."
        )

    def _on_cache_inspector_clicked(self) -> None:
        try:
            from gui.ingestion.caching_inspector import (
                diff_provenance,
                CachingInspectorDialog,
            )
        except Exception as e:  # pragma: no cover
            self._append_log(f"Caching Inspector import failed: {e}")
            return
        current_map: dict[str, str] = {}
        for item in self._all_file_items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(data, dict) or "file" not in data:
                continue
            fpath = data["file"]
            try:
                with open(fpath, "rb") as fh:
                    import hashlib as _hl

                    current_map[fpath] = _hl.sha1(fh.read()).hexdigest()
            except Exception:
                continue
        prov_map = {p: sha for p, (sha, _ts, _ver) in self._last_provenance.items()}
        diff = diff_provenance(current_map, prov_map)
        dlg = CachingInspectorDialog(diff, self)
        dlg.exec()
        self._append_log("Caching Inspector: " + diff.summary())

    def _on_security_scan_clicked(self) -> None:
        try:
            from gui.ingestion.security_sandbox import scan_rules_text
        except Exception as e:  # pragma: no cover
            self._append_log(f"Security sandbox import failed: {e}")
            return
        raw = self.rule_editor.toPlainText()
        report = scan_rules_text(raw)
        if report.ok:
            self._append_log(report.summary())
            return
        lines = [report.summary(), "-- Issues --"]
        for i in report.issues[:100]:
            loc = f" (line {i.lineno}, col {i.col})" if i.lineno is not None else ""
            field = f" [{i.source}:{i.field}]" if i.field else ""
            lines.append(f"- {i.category}{field}{loc}: {i.message}")
        if len(report.issues) > 100:
            lines.append("(truncated; showing first 100)")
        self._append_log("\n".join(lines))

    def _on_export_rules_clicked(self) -> None:  # pragma: no cover - UI path
        try:
            from gui.ingestion.rule_export import export_rules
        except Exception as e:
            self._append_log(f"Export module import failed: {e}")
            return
        out_path = os.path.join(self._base_dir, "ingestion_rules_export.json")
        try:
            export_rules(self.rule_editor.toPlainText(), out_path)
        except Exception as e:
            self._append_log(f"Export failed: {e}")
            return
        self._append_log(f"Rules exported -> {out_path}")

    def _on_import_rules_clicked(self) -> None:  # pragma: no cover - UI path
        try:
            from gui.ingestion.rule_export import import_rules
        except Exception as e:
            self._append_log(f"Import module import failed: {e}")
            return
        in_path = os.path.join(self._base_dir, "ingestion_rules_export.json")
        try:
            text = import_rules(in_path)
        except Exception as e:
            self._append_log(f"Import failed: {e}")
            return
        self.rule_editor.setPlainText(text)
        self._append_log(f"Rules imported from {in_path}")

    def _on_versions_clicked(self) -> None:
        conn = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")
            except Exception:
                conn = None
        if conn is None:
            self._append_log("Versions: no DB connection")
            return
        try:
            from gui.ingestion.rule_versioning import RuleSetVersionStore

            store = RuleSetVersionStore(conn)
            versions = store.list_versions()
            if not versions:
                self._append_log("Versions: none stored")
                return
            self._append_log(
                f"Versions ({len(versions)}): "
                + ", ".join(f"v{v.version_num}" for v in versions[:15])
            )
            if len(versions) > 15:
                self._append_log(f"  ... {len(versions)-15} more")
        except Exception as e:  # pragma: no cover
            self._append_log(f"Versions ERROR: {e}")

    def _on_rollback_clicked(self) -> None:
        conn = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")
            except Exception:
                conn = None
        if conn is None:
            self._append_log("Rollback: no DB connection")
            return
        try:
            from gui.ingestion.rule_versioning import RuleSetVersionStore

            store = RuleSetVersionStore(conn)
            prev_json = store.rollback_to_previous()
            if not prev_json:
                self._append_log("Rollback: no previous version")
                return
            self.rule_editor.setPlainText(prev_json)
            self._append_log("Rollback loaded previous version into editor (not applied)")
        except Exception as e:  # pragma: no cover
            self._append_log(f"Rollback ERROR: {e}")

    def _on_macro_shortcuts_clicked(self) -> None:
        try:
            from gui.ingestion import macro_shortcuts as _macro
        except Exception as exc:
            self._append_log(f"Macro shortcuts unavailable: {exc}")
            return

        if getattr(_macro, "MacroShortcutDialog", None) is None:
            self._append_log("Macro shortcuts dialog cannot be loaded in this environment")
            return

        stored_templates = _macro.load_templates()
        rule_templates: list[_macro.MacroShortcutTemplate] = []
        parse_warning = ""
        try:
            ruleset = self._parse_ruleset_from_editor()
        except Exception as exc:
            parse_warning = f"Rule set parse failed; showing saved templates only ({exc})"
            ruleset = None
        if ruleset is not None:
            try:
                rule_templates = _macro.extract_templates_from_ruleset(ruleset)
            except Exception as exc:  # pragma: no cover - defensive
                parse_warning = f"Could not extract macros from ruleset: {exc}"
                rule_templates = []

        dialog = _macro.MacroShortcutDialog(stored_templates, rule_templates, parent=self)
        if parse_warning:
            dialog.set_warning(parse_warning)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            self._append_log("Macro shortcuts: cancelled")
            return

        updated = dialog.persisted_templates()
        try:
            _macro.save_templates(updated)
        except Exception as exc:
            self._append_log(f"Macro shortcuts save failed: {exc}")
            return

        summary = ", ".join(f"{tpl.name} -> {tpl.sequence}" for tpl in updated if tpl.sequence)
        if summary:
            self._append_log(f"Macro shortcuts updated: {summary}")
        else:
            self._append_log("Macro shortcuts cleared")
        if hasattr(self, "_refresh_macro_shortcuts"):
            try:
                self._refresh_macro_shortcuts(updated)  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover - defensive
                self._append_log(f"Macro shortcuts refresh failed: {exc}")
