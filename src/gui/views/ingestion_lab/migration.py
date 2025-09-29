"""Migration assistant handlers for the ingestion lab panel."""

from __future__ import annotations

from collections import defaultdict
import json
from typing import Dict, Mapping, Tuple

try:  # pragma: no cover - optional import guard for test environments
    from gui.services.service_locator import services as _services  # type: ignore
except Exception:  # pragma: no cover
    _services = None  # type: ignore

__all__ = ["MigrationAssistantMixin"]


class MigrationAssistantMixin:
    """Provide schema diff + mapping suggestion helpers."""

    def _migration_extract_mapping(self) -> Dict[str, Dict[str, str]]:
        text = (self.rule_editor.toPlainText() or "").strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
        except Exception:
            return {}
        if not isinstance(payload, Mapping):
            return {}
        raw_mapping = payload.get("mapping")
        if not isinstance(raw_mapping, Mapping):
            return {}
        normalized: Dict[str, Dict[str, str]] = {}
        for resource, fields in raw_mapping.items():
            if not isinstance(resource, str) or not isinstance(fields, Mapping):
                continue
            cleaned: Dict[str, str] = {}
            for fname, target in fields.items():
                if isinstance(fname, str) and isinstance(target, str):
                    cleaned[fname] = target
            if cleaned:
                normalized[resource] = cleaned
        return normalized

    def migration_assistant_snapshot(self) -> Dict[str, object]:
        snapshot: Dict[str, object] = {}
        preview = getattr(self, "_last_migration_preview", None)
        if preview is not None:
            try:
                snapshot["actions"] = [a.to_mapping() for a in preview.actions]
            except Exception:  # pragma: no cover - defensive
                pass
        suggestions = getattr(self, "_last_migration_suggestions", None)
        if suggestions:
            try:
                snapshot["suggestions"] = {res: dict(cols) for res, cols in suggestions.items()}
            except Exception:  # pragma: no cover - defensive
                pass
        return snapshot

    def _on_migration_assistant_clicked(self) -> None:
        try:
            rule_set = self._parse_ruleset_from_editor()
        except Exception as exc:
            self._append_log(f"Migration Assistant: rule parse error: {exc}")
            return

        conn = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")
            except Exception:  # pragma: no cover - defensive
                conn = None
        if conn is None:
            self._append_log("Migration Assistant: database connection unavailable")
            return

        try:
            from gui.ingestion.rule_migration import generate_migration_preview
            from gui.ingestion.rule_mapping import build_mapping_entries, group_by_resource
        except Exception as exc:  # pragma: no cover
            self._append_log(f"Migration Assistant unavailable: {exc}")
            return

        try:
            preview = generate_migration_preview(rule_set, conn)
        except Exception as exc:  # pragma: no cover - sqlite/introspection errors
            self._append_log(f"Migration Assistant: failed to build preview: {exc}")
            return

        entries = build_mapping_entries(rule_set)
        grouped = group_by_resource(entries)
        entry_lookup: Dict[Tuple[str, str], list] = defaultdict(list)
        for entry in entries:
            entry_lookup[(entry.resource, entry.target_column)].append(entry)

        self._last_migration_preview = preview
        suggestions_map: Dict[str, Dict[str, str]] = {}
        unmapped: set[str] = set()
        existing_mapping = self._migration_extract_mapping()

        create_count = 0
        add_count = 0
        type_count = 0
        action_lines = []

        for action in preview.actions:
            if action.kind == "create_table":
                create_count += 1
                action_lines.append(f"[CREATE TABLE] {action.table}")
                for entry in grouped.get(action.table, []):
                    mapped = existing_mapping.get(entry.resource, {}).get(entry.source_name)
                    if mapped:
                        continue
                    suggestions_map.setdefault(entry.resource, {})[
                        entry.source_name
                    ] = entry.target_column
                    unmapped.add(f"{entry.resource}.{entry.source_name}")
            elif action.kind == "add_column":
                add_count += 1
                column = action.column or "<unknown>"
                action_lines.append(
                    f"[ADD COLUMN] {action.table}.{column} ({action.sqlite_type or 'TEXT'})"
                )
                for entry in entry_lookup.get((action.table, column), []):
                    mapped = existing_mapping.get(entry.resource, {}).get(entry.source_name)
                    if mapped:
                        continue
                    suggestions_map.setdefault(entry.resource, {})[
                        entry.source_name
                    ] = entry.target_column
                    unmapped.add(f"{entry.resource}.{entry.source_name}")
            else:
                type_count += 1
                column = action.column or "<unknown>"
                note = action.note or "type mismatch"
                action_lines.append(f"[TYPE NOTE] {action.table}.{column} -> {note}")

        self._last_migration_suggestions = suggestions_map

        self._append_log(
            "Migration Assistant: actions={total} create={create} add={add} type_notes={type}".format(
                total=len(preview.actions), create=create_count, add=add_count, type=type_count
            )
        )
        if unmapped:
            listed = ", ".join(sorted(unmapped))
            self._append_log(f"Migration Assistant ⚠ unmapped columns: {listed}")
        else:
            self._append_log("Migration Assistant: no unmapped columns detected")

        lines = [
            "Migration Assistant",
            "===================",
            f"Actions detected: {len(preview.actions)}",
            f"  create_table: {create_count}",
            f"  add_column:   {add_count}",
            f"  type_notes:  {type_count}",
            "",
        ]

        if action_lines:
            lines.append("Schema changes:")
            for entry in action_lines[:50]:
                lines.append(f"  {entry}")
            if len(action_lines) > 50:
                lines.append(f"  ... {len(action_lines) - 50} more")
            lines.append("")
        else:
            lines.append("Schema already matches the inferred target columns.")
            lines.append("")

        if suggestions_map:
            lines.append("Suggested mapping entries for new columns:")
            for resource in sorted(suggestions_map):
                lines.append(f"- {resource}:")
                for field, target in sorted(suggestions_map[resource].items()):
                    lines.append(f"    {field} -> {target}")
            lines.append("")
            structured = {
                "mapping": {
                    res: dict(sorted(cols.items())) for res, cols in sorted(suggestions_map.items())
                }
            }
            lines.append("JSON snippet to merge:")
            lines.append(json.dumps(structured, indent=2, ensure_ascii=False))
        else:
            lines.append("No additional mapping entries required.")

        output = "\n".join(lines)
        try:
            self.preview_area.setPlainText(output)
        except Exception:  # pragma: no cover - UI guard
            pass
        self._last_preview_plain = output
        self._last_preview_html = ""
