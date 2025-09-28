"""Selector drift watchlist logic extracted from the ingestion lab panel."""

from __future__ import annotations

from typing import List

from gui.ingestion.selector_watchlist_store import (
    SelectorWatchEntry,
    SelectorWatchResult,
    compute_watchlist_drift,
)

__all__ = ["WatchlistMixin"]


class WatchlistMixin:
    """Encapsulate watchlist specific handlers and helpers."""

    def _show_watchlist_tab(self) -> None:
        try:
            idx = self._side_tabs.indexOf(self._watchlist_panel)
            if idx >= 0:
                self._side_tabs.setCurrentIndex(idx)
        except Exception:
            pass

    def _update_watchlist_panel_entries(self) -> None:
        try:
            self._watchlist_panel.set_entries(self._watchlist_store.entries())
        except Exception:
            pass

    def _persist_watchlist_store(self) -> None:
        try:
            self._watchlist_store.save()
        except Exception as exc:  # pragma: no cover - IO failure is unlikely
            self._append_log(f"Watchlist save failed: {exc}")

    def _on_watchlist_run_clicked(self) -> None:
        self._show_watchlist_tab()
        self._run_watchlist_check()

    def _run_watchlist_check(self) -> None:
        entries = self._watchlist_store.entries()
        if not entries:
            self._append_log("Watchlist: no selectors pinned")
            self._watchlist_panel.set_status("No selectors pinned")
            self._last_watchlist_results = {}
            return
        if not self._current_ruleset:
            self._append_log("Watchlist ERROR: current rule set invalid")
            self._watchlist_panel.set_status("Fix rule parse errors before running watchlist.")
            return
        html_map = self._gather_visible_file_html()
        if not html_map:
            self._append_log("Watchlist: no visible HTML files to analyze")
            self._watchlist_panel.set_status("No HTML files visible under current filters.")
            return
        try:
            results = compute_watchlist_drift(self._current_ruleset, entries, html_map)
        except Exception as exc:  # pragma: no cover - defensive
            self._append_log(f"Watchlist ERROR: {exc}")
            self._watchlist_panel.set_status(f"Watchlist error: {exc}")
            return
        self._last_watchlist_results = results
        for ident, res in results.items():
            entry = self._watchlist_store.get(ident)
            if entry:
                entry.last_count = res.current_count
        alerts = [res for res in results.values() if res.alert]
        self._persist_watchlist_store()
        self._watchlist_panel.update_results(results)
        self._append_log(f"Watchlist run: {len(results)} entries, alerts={len(alerts)}")
        for res in alerts[:15]:
            target = res.target_name if res.target_name else res.target_type
            detail = res.reason or res.status_text()
            self._append_log(
                f"  ALERT {res.resource} -> {target}: {detail} (baseline={res.baseline_count} current={res.current_count})"
            )
        if not alerts:
            self._append_log("  All selectors within thresholds")

    def _on_watchlist_add_requested(
        self,
        resource: str,
        target_type: str,
        target_name: object,
        threshold: int,
    ) -> None:
        self._show_watchlist_tab()
        if not self._current_ruleset:
            self._append_log("Watchlist add skipped: invalid rule set")
            self._watchlist_panel.set_status("Cannot add – fix rule errors first.")
            return
        name = target_name if isinstance(target_name, str) and target_name else None
        try:
            candidate = SelectorWatchEntry(
                resource=resource,
                target_type=target_type,
                target_name=name,
                threshold_percent=threshold,
            )
        except ValueError as exc:
            self._append_log(f"Watchlist add failed: {exc}")
            self._watchlist_panel.set_status(str(exc))
            return
        existing = self._watchlist_store.get(candidate.identifier())
        if existing:
            existing.threshold_percent = candidate.threshold_percent
            entry = existing
            action = "updated"
        else:
            entry = candidate
            self._watchlist_store.upsert(entry)
            action = "added"
        html_map = self._gather_visible_file_html()
        baseline_note = ""
        if html_map:
            try:
                results = compute_watchlist_drift(self._current_ruleset, [entry], html_map)
                snap = results.get(entry.identifier())
                if snap:
                    if action == "added" or entry.baseline_count == 0:
                        entry.baseline_count = snap.current_count
                    entry.last_count = snap.current_count
                    baseline_note = f" baseline={snap.current_count}"
            except Exception as exc:
                self._append_log(f"Watchlist baseline error: {exc}")
        else:
            if action == "added" and entry.baseline_count == 0:
                self._watchlist_panel.set_status(
                    "Baseline not captured – refresh files or run watchlist after loading HTML."
                )
        self._persist_watchlist_store()
        self._update_watchlist_panel_entries()
        self._append_log(f"Watchlist {action}: {resource} [{entry.target_label()}]{baseline_note}")

    def _on_watchlist_remove_requested(self, identifiers: List[str]) -> None:
        if not identifiers:
            return
        self._show_watchlist_tab()
        removed = 0
        for ident in identifiers:
            if self._watchlist_store.get(ident):
                self._watchlist_store.remove(ident)
                removed += 1
        if removed:
            self._persist_watchlist_store()
            self._update_watchlist_panel_entries()
            self._watchlist_panel.update_results({})
            self._last_watchlist_results = {}
            label = "entry" if removed == 1 else "entries"
            self._append_log(f"Watchlist removed {removed} {label}")

    def _on_watchlist_set_baseline_requested(self, identifiers: List[str]) -> None:
        if not identifiers:
            return
        self._show_watchlist_tab()
        updated = 0
        for ident in identifiers:
            entry = self._watchlist_store.get(ident)
            if entry and entry.last_count is not None:
                entry.baseline_count = entry.last_count
                updated += 1
        if updated:
            self._persist_watchlist_store()
            self._update_watchlist_panel_entries()
            label = "entry" if updated == 1 else "entries"
            self._append_log(f"Watchlist baseline updated for {updated} {label}")
        else:
            self._watchlist_panel.set_status("Run the watchlist before setting a baseline.")

    def watchlist_snapshot(self) -> dict[str, object]:
        entries = [
            {
                "id": entry.identifier(),
                "resource": entry.resource,
                "target_type": entry.target_type,
                "target_name": entry.target_name,
                "baseline": entry.baseline_count,
                "last": entry.last_count,
                "threshold": entry.threshold_percent,
            }
            for entry in self._watchlist_store.entries()
        ]
        alerts = [
            {
                "id": ident,
                "resource": res.resource,
                "target_type": res.target_type,
                "target_name": res.target_name,
                "baseline": res.baseline_count,
                "current": res.current_count,
                "drop_percent": res.drop_percent,
                "alert": res.alert,
                "reason": res.reason,
            }
            for ident, res in self._last_watchlist_results.items()
        ]
        return {"entries": entries, "results": alerts}
