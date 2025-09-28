"""Simulation, apply, and hash impact helpers for the ingestion lab panel."""

from __future__ import annotations

import hashlib
import os
from typing import Dict, Any

try:  # pragma: no cover - optional locator import
    from gui.services.service_locator import services as _services  # type: ignore
except Exception:  # pragma: no cover
    _services = None  # type: ignore

from PyQt6.QtCore import Qt

from .hash_impact import HashImpactResult

__all__ = ["SimulationMixin"]


class SimulationMixin:
    """Provide simulation/apply flows and hash impact utilities."""

    def _on_hash_impact_clicked(self) -> None:
        try:
            res = self.compute_hash_impact()
        except Exception as e:  # pragma: no cover - defensive
            self._append_log(f"Hash Impact ERROR: {e}")
            return
        self._append_log(
            f"Hash Impact: Updated {len(res.updated)} | Unchanged {len(res.unchanged)} | New {len(res.new)} | Missing {len(res.missing)}"
        )

        def _sample(label: str, items: list[str]):  # noqa: ANN001
            if not items:
                return
            preview = ", ".join(os.path.basename(p) for p in items[:5])
            more = "" if len(items) <= 5 else f" (+{len(items)-5} more)"
            self._append_log(f"  {label}: {preview}{more}")

        _sample("Updated", res.updated)
        _sample("New", res.new)
        _sample("Missing", res.missing)

    def compute_hash_impact(self) -> HashImpactResult:
        prov = dict(self._last_provenance)
        current_paths: list[str] = []
        for item in self._all_file_items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and "file" in data:
                current_paths.append(data["file"])  # type: ignore[index]
        current_set = set(current_paths)
        missing = [p for p in prov.keys() if p not in current_set]
        updated: list[str] = []
        unchanged: list[str] = []
        new: list[str] = []
        for path in current_paths:
            try:
                with open(path, "rb") as fh:
                    content = fh.read()
                sha1 = hashlib.sha1(content).hexdigest()
            except Exception:
                if path in prov:
                    missing.append(path)
                continue
            if path in prov:
                old_sha, _ts, _pv = prov[path]
                if old_sha != sha1:
                    updated.append(path)
                else:
                    unchanged.append(path)
            else:
                new.append(path)
        res = HashImpactResult(
            updated=sorted(updated),
            unchanged=sorted(unchanged),
            new=sorted(new),
            missing=sorted(set(missing)),
        )
        self._last_hash_impact = res
        return res

    def hash_impact_snapshot(self) -> Dict[str, Any]:
        if not self._last_hash_impact:
            return {}
        r = self._last_hash_impact
        return {
            "updated": list(r.updated),
            "unchanged": list(r.unchanged),
            "new": list(r.new),
            "missing": list(r.missing),
        }

    def _on_simulate_clicked(self) -> None:
        if not self._safe_guard:
            self._append_log("Simulate: guard unavailable")
            return
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Simulate ERROR (rules): {e}")
            return
        import json as _json

        text = (self.rule_editor.toPlainText() or "").strip()
        try:
            raw_payload = _json.loads(text)
            if not isinstance(raw_payload, dict):
                raw_payload = {}
        except Exception:
            raw_payload = {}
        html_map = self._gather_visible_file_html()
        if not html_map:
            self._append_log("Simulate: no visible files")
            return
        try:
            sim = self._safe_guard.simulate(rs, html_map, raw_payload)
        except Exception as e:  # pragma: no cover
            self._append_log(f"Simulate ERROR: {e}")
            return
        self._last_simulation_id = sim.sim_id
        status = "PASS" if sim.passed else "FAIL"
        self._append_log(
            f"Simulation {sim.sim_id} {status}: rows={sum(sim.adapter_rows.values())} resources={len(sim.adapter_rows)}"
        )
        if sim.reasons:
            for r in sim.reasons[:10]:
                self._append_log(f"  reason: {r}")
            if len(sim.reasons) > 10:
                self._append_log(f"  ... {len(sim.reasons)-10} more")
        self._banner.setVisible(False)

    def _on_apply_clicked(self) -> None:
        if not self._safe_guard:
            self._append_log("Apply: guard unavailable")
            return
        if self._last_simulation_id is None:
            self._append_log("Apply: no prior simulation")
            return
        conn = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")
            except Exception:
                conn = None
        import sqlite3 as _sqlite3

        if conn is None:
            try:
                conn = _sqlite3.connect(":memory:")
            except Exception:
                self._append_log("Apply ERROR: no DB connection available")
                return
        import json as _json

        text = (self.rule_editor.toPlainText() or "").strip()
        try:
            raw_payload = _json.loads(text)
            if not isinstance(raw_payload, dict):
                raw_payload = {}
        except Exception:
            raw_payload = {}
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Apply ERROR (rules): {e}")
            return
        html_map = self._gather_visible_file_html()
        if not html_map:
            self._append_log("Apply: no visible files")
            return
        try:
            result = self._safe_guard.apply(
                self._last_simulation_id, rs, html_map, raw_payload, conn
            )
        except Exception as e:
            self._append_log(f"Apply ERROR: {e}")
            return
        from gui.ingestion.rule_versioning import RuleSetVersionStore

        try:
            store = RuleSetVersionStore(conn)
            self._last_version_num = store.save_version(raw_payload, text or "{}")
        except Exception as ve:  # pragma: no cover
            self._append_log(f"Versioning WARN: {ve}")
        if self._last_version_num:
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS provenance(path TEXT PRIMARY KEY, sha1 TEXT NOT NULL, last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, parser_version INTEGER DEFAULT 1, rule_version INTEGER DEFAULT NULL)"
                )
                try:
                    cur = conn.execute("PRAGMA table_info(provenance)")
                    cols = {r[1] for r in cur.fetchall()}
                    if "rule_version" not in cols:
                        conn.execute(
                            "ALTER TABLE provenance ADD COLUMN rule_version INTEGER DEFAULT NULL"
                        )
                except Exception:
                    pass
                import hashlib as _hl

                for fpath, html in html_map.items():
                    sha1 = _hl.sha1(html.encode("utf-8", "ignore")).hexdigest()
                    conn.execute(
                        "INSERT INTO provenance(path, sha1, last_ingested_at, rule_version) VALUES(?,?,CURRENT_TIMESTAMP, ?) "
                        "ON CONFLICT(path) DO UPDATE SET sha1=excluded.sha1, last_ingested_at=CURRENT_TIMESTAMP, rule_version=excluded.rule_version",
                        (fpath, sha1, self._last_version_num),
                    )
                conn.commit()
            except Exception as pe:  # pragma: no cover
                self._append_log(f"Provenance rule_version WARN: {pe}")
        inserted_total = sum(result.rows_by_resource.values())
        summary_text = f"Apply Summary sim={result.sim_id} inserted_rows={inserted_total} resources={len(result.rows_by_resource)}"
        self._banner.setText(summary_text)
        self._banner.setVisible(True)
        self._last_apply_summary = {
            "sim_id": result.sim_id,
            "inserted_total": inserted_total,
            "rows_by_resource": dict(result.rows_by_resource),
        }
        self._append_log(summary_text)
        if self._last_version_num:
            self._append_log(f"Rule Version: v{self._last_version_num}")
        try:
            from gui.services.telemetry_service import TelemetryService  # type: ignore

            TelemetryService.instance.record_apply()
        except Exception:
            pass
        if _services is not None:
            try:
                from gui.services.event_bus import GUIEvent, EventBus

                bus: EventBus | None = _services.try_get("event_bus")
                if bus:
                    bus.publish(
                        GUIEvent.INGEST_RULES_APPLIED,
                        {
                            "sim_id": result.sim_id,
                            "inserted_total": inserted_total,
                            "rows_by_resource": dict(result.rows_by_resource),
                        },
                    )
            except Exception:  # pragma: no cover
                pass

    def apply_summary_snapshot(self) -> Dict[str, Any]:  # pragma: no cover - test helper
        return dict(self._last_apply_summary)
