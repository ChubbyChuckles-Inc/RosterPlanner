"""Theme service (Milestone 1.6 initial implementation).

Bridges the headless `ThemeManager` (design tokens + accent derivation) with the
runtime application via the `EventBus`. Provides:

 - Light/Dark (default/high-contrast already handled by ThemeManager variants)
 - Accent color mutation
 - Emission of GUIEvent.THEME_CHANGED with a diff summary

The service keeps a cached active map for cheap access. Future expansion can
compute and apply QSS strings; for now it exposes the semantic color mapping
for consumers (e.g., style builders) and publishes theme change events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Iterable, List
from pathlib import Path
import os, json

from gui.design import ThemeManager, ThemeDiff, load_tokens
from gui.design.contrast import contrast_ratio
from gui.design.theme_presets import get_overlay, available_variant_overlays
from gui.design.adaptive_contrast import ensure_accent_on_color
from gui.design.color_vision_simulation import apply_color_vision_filter_if_active
from .custom_theme import load_custom_theme, CustomThemeError
from .event_bus import EventBus, GUIEvent
from .service_locator import services
from time import perf_counter
import logging

_logger = logging.getLogger(__name__)
STYLE_RECALC_WARN_THRESHOLD_MS = 50.0  # Threshold for slow style recalculation logging

__all__ = [
    "ThemeService",
    "get_theme_service",
    "validate_theme_keys",
    "ThemeValidationError",
    "load_custom_theme",
    "CustomThemeError",
    "export_theme_snapshot",
]


REQUIRED_COLOR_KEYS: tuple[str, ...] = (
    # Core surface/text roles (kept intentionally small so user can experiment freely)
    "background.primary",
    "background.secondary",
    "surface.card",
    "text.primary",
    "accent.base",
)


class ThemeValidationError(RuntimeError):
    """Raised when required theme keys are missing."""


def validate_theme_keys(
    mapping: Mapping[str, str], required: Iterable[str] = REQUIRED_COLOR_KEYS
) -> List[str]:
    """Return list of missing keys from mapping.

    Parameters
    ----------
    mapping : Mapping[str, str]
        Flattened theme semantic -> hex color map.
    required : Iterable[str]
        Collection of required keys to validate.
    """
    missing = [k for k in required if k not in mapping or not mapping[k]]
    return missing


@dataclass
class ThemeService:
    manager: ThemeManager
    _cached_map: dict[str, str]

    @classmethod
    def create_default(cls) -> "ThemeService":
        tokens = load_tokens()  # relies on design tokens module already supplying defaults
        # If AppConfig is registered, honor persisted theme_variant
        from gui.services.service_locator import services as _services  # local import

        cfg = _services.try_get("app_config")
        initial_variant = "default"
        persisted = getattr(cfg, "theme_variant", None) if cfg else None
        base_variants = {"default", "brand-neutral", "high-contrast"}
        overlay_variants = set(available_variant_overlays())
        if persisted in base_variants | overlay_variants:
            initial_variant = persisted  # type: ignore
        mgr = ThemeManager(tokens, variant=initial_variant)  # type: ignore[arg-type]
        base_map = dict(mgr.active_map())
        cls._augment_semantics(base_map)
        # Apply overlay if persisted is an overlay variant
        if initial_variant in overlay_variants:
            ov = get_overlay(initial_variant)
            if ov:
                base_map.update(ov)
        cls._normalize_contrast(base_map)
        ensure_accent_on_color(base_map)
        # Apply color vision simulation if service registered already
        try:
            from gui.services.service_locator import services as _services

            cb = _services.try_get("color_blind_mode")
            mode = getattr(cb, "mode", None)
            if mode:
                apply_color_vision_filter_if_active(base_map, mode)
        except Exception:
            pass
        svc = cls(manager=mgr, _cached_map=base_map)
        # Initialize cache for filesystem overlays
        svc._cached_filesystem_overlays = {}
        try:
            svc.load_filesystem_themes()
        except Exception:
            pass
        # Write built-in overlays to assets/themes if not present
        try:
            theme_dir = Path(os.getcwd()) / "assets" / "themes"
            theme_dir.mkdir(parents=True, exist_ok=True)
            # Export default snapshot
            if not (theme_dir / "default.json").exists():
                payload = {"color": {}}
                for k, v in base_map.items():
                    if "." in k:
                        g, r = k.split(".", 1)
                        payload["color"].setdefault(g, {})[r] = v
                with (theme_dir / "default.json").open("w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2)
            # Overlay presets
            for ov_name in available_variant_overlays():
                ov = get_overlay(ov_name)
                if not ov:
                    continue
                path = theme_dir / f"{ov_name}.json"
                if path.exists():
                    continue
                payload = {"color": {}}
                for k, v in ov.items():
                    if "." in k:
                        g, r = k.split(".", 1)
                        payload["color"].setdefault(g, {})[r] = v
                with path.open("w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2)
            # Reload to include these
            svc.load_filesystem_themes()
        except Exception:
            pass
        # --- Filesystem theme persistence fix (Regression 7.10.69) ---------------------
        # If user previously selected a filesystem theme (exported / custom) its name
        # would have been persisted to AppConfig.theme_variant, but on startup we only
        # honored built-in base + overlay variants above. After loading filesystem
        # themes we now check if the persisted value matches one of the discovered
        # filesystem overlays; if so we apply it so the UI reflects the user's last
        # choice. (Low risk: apply_custom already performs diff + event emission.)
        try:
            if (
                persisted
                and persisted not in (base_variants | overlay_variants)
                and persisted in getattr(svc, "_cached_filesystem_overlays", {})
            ):
                # Apply the filesystem theme overlay
                svc.apply_filesystem_theme(persisted)  # type: ignore[arg-type]
                # Record logical variant identity so future persistence keeps the same name
                try:
                    svc.manager.variant = persisted  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception:
            pass
        return svc

    # Accessors ---------------------------------------------------------
    def colors(self) -> Mapping[str, str]:
        return self._cached_map

    # Snapshot / Export -------------------------------------------------
    def snapshot(self) -> dict[str, object]:
        """Return a structured snapshot of the current theme state.

        The snapshot is intentionally deterministic (sorted keys) so that
        successive exports can be diffed cleanly in version control or
        design review tooling.

        Returns
        -------
        dict[str, object]
            A mapping with keys:
              - variant: active variant string (may include overlay id)
              - accent_base: current accent seed color
              - color_count: number of color keys exported
              - colors: ordered list of {'key','value'} pairs (preserves
                         stable ordering for diff friendliness)
              - missing_required: list of any missing REQUIRED_COLOR_KEYS
              - metadata: auxiliary info (exported_at epoch seconds)
        """
        import time

        colors_map = self._cached_map.copy()
        # Provide stable ordering.
        ordered = [{"key": k, "value": colors_map[k]} for k in sorted(colors_map.keys())]
        missing = validate_theme_keys(colors_map)
        return {
            "variant": self.manager.variant,
            "accent_base": self.manager.accent_base,
            "color_count": len(colors_map),
            "colors": ordered,
            "missing_required": missing,
            "metadata": {"exported_at": time.time()},
        }

    def export_snapshot_to_file(self, path: str) -> str:
        """Serialize current snapshot to JSON file.

        Parameters
        ----------
        path : str
            Destination filesystem path (will overwrite if exists).

        Returns
        -------
        str
            The path written (for chaining / logging convenience).
        """
        import json, os

        snap = self.snapshot()
        # Ensure directory exists
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, sort_keys=False)
        return path

    # Mutations ---------------------------------------------------------
    def set_variant(self, variant: str) -> ThemeDiff:
        start_t = perf_counter()
        overlay = get_overlay(variant)
        if overlay:
            # Treat as extension of default (or high-contrast? keep default for consistency)
            old = self._cached_map.copy()
            # Set underlying manager variant to the literal overlay string so that
            # subsequent accent mutations retain chosen variant identity.
            self.manager.set_variant(variant)  # will resolve base 'default' token map
            self._cached_map = dict(self.manager.active_map())
            self._augment_semantics(self._cached_map)
            # Apply overlay
            self._cached_map.update(overlay)
            # Contrast normalization post overlay
            self._normalize_contrast(self._cached_map)
            ensure_accent_on_color(self._cached_map)
            diff = self._build_diff(old, self._cached_map)
            if not diff.no_changes:
                self._publish_theme_changed(diff)
                self._persist_variant(variant)
            elapsed_ms = (perf_counter() - start_t) * 1000.0
            self._maybe_log_slow("variant", variant, elapsed_ms, diff)
            return diff
        # Base variant path
        diff = self.manager.set_variant(variant)  # type: ignore[arg-type]
        if not diff.no_changes:
            self._cached_map = dict(self.manager.active_map())
            self._augment_semantics(self._cached_map)
            self._normalize_contrast(self._cached_map)
            ensure_accent_on_color(self._cached_map)
            # Re-apply simulation if active
            try:
                cb = services.try_get("color_blind_mode")
                if cb and getattr(cb, "mode", None):
                    apply_color_vision_filter_if_active(self._cached_map, cb.mode)
            except Exception:
                pass
            self._publish_theme_changed(diff)
            self._persist_variant(variant)
        elapsed_ms = (perf_counter() - start_t) * 1000.0
        self._maybe_log_slow("variant", variant, elapsed_ms, diff)
        return diff

    def set_accent(self, base_hex: str) -> ThemeDiff:
        start_t = perf_counter()
        diff = self.manager.set_accent_base(base_hex)
        if not diff.no_changes:
            self._cached_map = dict(self.manager.active_map())
            self._augment_semantics(self._cached_map)
            self._normalize_contrast(self._cached_map)
            ensure_accent_on_color(self._cached_map)
            try:
                cb = services.try_get("color_blind_mode")
                if cb and getattr(cb, "mode", None):
                    apply_color_vision_filter_if_active(self._cached_map, cb.mode)
            except Exception:
                pass
            self._publish_theme_changed(diff)
        elapsed_ms = (perf_counter() - start_t) * 1000.0
        self._maybe_log_slow("accent", base_hex, elapsed_ms, diff)
        return diff

    # QSS Generation ---------------------------------------------------
    def generate_qss(self) -> str:
        """Generate a small QSS snippet reflecting current theme colors.

        This focuses on a few common widget roles; future expansion can add
        more granular selectors or derive from token-driven templates.
        """
        c = self._cached_map
        # Defensive lookups with fallbacks
        bg = c.get("background.primary", c.get("background.base", "#202020"))
        bg2 = c.get("background.secondary", c.get("background.elevated", bg))
        surf = c.get("surface.card", c.get("surface.primary", bg2))
        txt = c.get("text.primary", "#FFFFFF")
        txt_muted = c.get("text.muted", txt)
        accent = c.get("accent.base", c.get("accent.primary", "#3D8BFD"))
        border = c.get("border.medium", c.get("border.light", accent))
        return f"""
/* THEME (auto-generated runtime) */
QMainWindow {{ background: {bg}; color: {txt}; }}
QMenuBar {{ background: {bg2}; color:{txt}; }}
QMenu {{ background: {bg2}; color:{txt}; }}
QMenu::item:selected {{ background: {accent}; color: {bg}; }}
QDockWidget::title {{ background: {surf}; color:{txt}; }}
QLabel {{ color:{txt}; }}
 QTableWidget {{ background:{surf}; color:{txt}; gridline-color:{border}; }}
 /* Simplified header styling to avoid deferred paint issues */
 QHeaderView::section {{ background:{bg2}; color:{txt}; padding:3px 6px; border:none; }}
 QTableCornerButton::section {{ background:{bg2}; border:none; }}
 QTableWidget::item:selected {{ background:{accent}; color:{bg}; }}
 /* Ensure vertical header (row numbers) inherits same palette */
 QTableView QHeaderView::section {{ background:{bg2}; color:{txt_muted}; }}
QLineEdit, QPlainTextEdit {{ background:{bg2}; color:{txt}; border:1px solid {border}; }}
QPushButton {{ background:{surf}; color:{txt}; border:1px solid {border}; padding:4px 8px; }}
QPushButton:hover {{ background:{accent}; color:{bg}; }}
QStatusBar {{ background:{bg2}; color:{txt_muted}; }}
 QTabWidget::pane {{ border:1px solid {border}; background:{surf}; }}
 QTabBar::tab {{ background:{bg2}; color:{txt}; padding:4px 10px; border:1px solid {border}; border-bottom:none; }}
 QTabBar::tab:selected {{ background:{accent}; color:{bg}; }}
 QListWidget, QTreeView {{ background:{surf}; color:{txt}; border:1px solid {border}; }}
 QTreeView::item:selected, QListWidget::item:selected {{ background:{accent}; color:{bg}; }}
 QToolTip {{ background:{bg2}; color:{txt}; border:1px solid {border}; }}
 QScrollBar:vertical {{ background:{bg2}; width:12px; }}
 QScrollBar::handle:vertical {{ background:{accent}; border-radius:5px; min-height:20px; }}
 QScrollBar:horizontal {{ background:{bg2}; height:12px; }}
 QScrollBar::handle:horizontal {{ background:{accent}; border-radius:5px; min-width:20px; }}
 /* Command Palette Dialog */
 QDialog#CommandPaletteDialog {{ background:{surf}; border:1px solid {border}; border-radius:6px; }}
 QLineEdit#commandPaletteSearch {{ background:{bg2}; color:{txt}; border:1px solid {border}; padding:4px 6px; border-radius:4px; }}
 QListWidget#commandPaletteList {{ background:{surf}; color:{txt}; border:1px solid {border}; }}
 QListWidget#commandPaletteList::item:selected {{ background:{accent}; color:{bg}; }}
 QListWidget#commandPaletteList::item {{ padding:3px 6px; }}
 /* Highlight span inside HTML text (using <span data-role=hl>) -> emulate via CSS-like selector mapping to QListView not possible; rely on rich text default + accent color fallback. */
 /* Shortcut Cheat Sheet Dialog */
 QDialog#ShortcutCheatSheetDialog {{ background:{surf}; border:1px solid {border}; border-radius:6px; }}
 QLineEdit#shortcutFilterEdit {{ background:{bg2}; color:{txt}; border:1px solid {border}; padding:4px 6px; border-radius:4px; }}
 QTreeWidget#shortcutTree {{ background:{surf}; color:{txt}; border:1px solid {border}; }}
 QTreeWidget#shortcutTree::item:selected {{ background:{accent}; color:{bg}; }}
 QPushButton#shortcutCloseButton {{ background:{bg2}; color:{txt}; border:1px solid {border}; padding:4px 10px; border-radius:4px; }}
 QPushButton#shortcutCloseButton:hover {{ background:{accent}; color:{bg}; }}
 /* Theme JSON Editor Dialog */
 QDialog#ThemeJsonEditorDialog {{ background:{surf}; border:1px solid {border}; border-radius:6px; }}
 QPlainTextEdit#themeJsonEditor {{ background:{bg2}; color:{txt}; border:1px solid {border}; font-family: Consolas, 'Courier New', monospace; }}
 QLabel#themeJsonStatus {{ color:{txt_muted}; }}
 QListWidget {{ background:{bg2}; color:{txt}; border:1px solid {border}; }}
 QPushButton {{ background:{bg2}; color:{txt}; border:1px solid {border}; }}
 QPushButton:hover {{ background:{accent}; color:{bg}; }}
 /* Calendar Widget */
 QCalendarWidget#matchCalendar QWidget {{ background:{surf}; }}
 QCalendarWidget#matchCalendar QAbstractItemView {{ selection-background-color:{accent}; selection-color:{bg}; outline:0; }}
 QCalendarWidget#matchCalendar QToolButton {{ background:{bg2}; color:{txt}; border:1px solid {border}; border-radius:4px; padding:2px 6px; }}
 QCalendarWidget#matchCalendar QToolButton:hover {{ background:{accent}; color:{bg}; }}
 QCalendarWidget#matchCalendar QTableView {{ background:{surf}; alternate-background-color:{bg2}; }}
 /* Glass surface subtle fix: remove dark border artifacts when nested */
 /* AvailabilityPanel border now handled by glass surface generator; keep minimal fallback when glass disabled */
 QWidget#AvailabilityPanel[glassDisabled='true'] {{ border:1px solid {border}; }}
 /* When docked widget is floating, suppress dark border override (Qt sets a frame). */
 QDockWidget[floating="true"] QWidget#AvailabilityPanel {{ border:1px solid rgba(0,0,0,0); }}
 /* View Titles & Breadcrumb */
 QLabel#viewTitleLabel, QLabel#teamTitleLabel {{ font-weight:600; font-size:14px; color:{txt}; }}
 QLabel#breadcrumbLabel {{ color:{txt_muted}; font-size:11px; }}
 /* Custom Chrome Window Integration */
 QWidget#chromeTitleBar {{ background:{bg2}; border-bottom:1px solid {border}; }}
 QLabel#chromeTitleLabel {{ color:{txt}; font-weight:600; padding-left:4px; }}
 QLabel#chromeWindowIcon {{ padding-left:6px; }}
 QToolButton#chromeBtnClose {{ color:{txt}; border:none; background:transparent; }}
 QToolButton#chromeBtnClose:hover {{ background:rgba(255,0,0,0.35); color:#FFFFFF; }}
 QToolButton#chromeBtnClose:focus {{ background:rgba(255,0,0,0.55); color:#FFFFFF; outline:2px solid rgba(255,255,255,0.6); }}
 QToolButton#chromeBtnMin, QToolButton#chromeBtnMax {{ color:{txt_muted}; border:none; background:transparent; }}
 QToolButton#chromeBtnMin:hover, QToolButton#chromeBtnMax:hover {{ background:{accent}; color:{bg}; }}
 /* Dialog content host made transparent so only outer frame draws rounded border */
 QWidget#chromeContentHost {{ background:transparent; border:none; }}
 /* ChromeDialog now paints its own rounded border; keep content host transparent */
 QDialog#ThemeJsonEditorDialog QWidget#chromeContentHost QWidget {{ background:transparent; }}
 /* Monospace editors */
 QPlainTextEdit#monospaceEditor {{ font-family: Consolas, 'Courier New', monospace; font-size:12px; }}
 /* Focus Ring Unification */
 QPushButton:focus, QToolButton:focus, QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
 QListWidget:focus, QTreeView:focus, QTableWidget:focus, QCheckBox:focus, QRadioButton:focus,
 QTabBar::tab:focus {{
     outline: 2px solid {c.get('border.focus', accent)};
     outline-offset: 0px;
 }}
 /* Empty State Component */
 QLabel#emptyStateTitle {{ font-weight:600; font-size:14px; color:{txt}; }}
 QLabel#emptyStateDesc {{ color:{txt_muted}; font-size:12px; }}
 QPushButton#emptyStateAction {{ background:{accent}; color:{bg}; border:1px solid {accent}; padding:4px 10px; }}
 QPushButton#emptyStateAction:hover {{ background:{c.get('accent.hover', accent)}; }}
 /* Toast / Notification Widgets */
 QWidget#toastHost {{ background:transparent; }}
 QWidget#toastHost > QWidget#toastWidget {{
     border:1px solid {border};
     border-radius:6px;
     background:{surf};
     color:{txt};
 }}
 QPushButton#toastCloseButton {{
     border:none; background:transparent; color:{txt_muted};
 }}
 QPushButton#toastCloseButton:hover {{ color:{txt}; }}
 QLabel#toastMessage {{ color:{txt}; }}
 /* Dock Title Bar Styling (Milestone 5.10.14) */
 QDockWidget > QWidget#DockTitleBar {{
     background:{bg2};
     border-bottom:1px solid {border};
 }}
 QDockWidget > QWidget#DockTitleBar QLabel#DockTitleLabel {{
     color:{txt_muted}; font-weight:600; padding:0px 4px;
 }}
 QDockWidget > QWidget#DockTitleBar[dockHover='true'] QLabel#DockTitleLabel {{
     color:{txt};
 }}
 QDockWidget > QWidget#DockTitleBar[dockActive='true'] {{
     background:{surf};
     border-bottom:2px solid {accent};
 }}
 QDockWidget > QWidget#DockTitleBar[dockActive='true'] QLabel#DockTitleLabel {{
     color:{accent};
 }}
 /* Ingestion Lab Panel (Milestone 7.10.67) */
 QWidget#ingestionLabPanel {{ background:{bg2}; }}
 QTreeWidget#ingestionLabFileTree {{ background:{surf}; color:{txt}; border:1px solid {border}; }}
 QTreeWidget#ingestionLabFileTree::item:selected {{ background:{accent}; color:{bg}; }}
 QPlainTextEdit#ingestionLabRuleEditor {{ background:{bg2}; color:{txt}; border:1px solid {border}; font-family: Consolas, 'Courier New', monospace; font-size:12px; }}
 QTextEdit#ingestionLabPreview {{ background:{surf}; color:{txt}; border:1px solid {border}; font-family: Consolas, 'Courier New', monospace; font-size:12px; }}
 QPlainTextEdit#ingestionLabLog {{ background:{bg2}; color:{txt_muted}; border:1px solid {border}; font-family: Consolas, 'Courier New', monospace; font-size:12px; }}
 QLabel#ingestionLabBanner {{ background:rgba(0,0,0,0.08); color:{txt}; border:1px solid {border}; border-radius:4px; padding:4px 6px; }}
 QLabel#ingestionLabPerfBadge {{ background:rgba(200,40,40,0.15); color:{c.get('state.error.fg', accent)}; border:1px solid {c.get('state.error.border', border)}; border-radius:4px; padding:2px 6px; font-size:11px; }}
 /* Selector Picker Dialog */
 QDialog#SelectorPickerDialog {{ background:{surf}; border:1px solid {border}; border-radius:6px; }}
 QDialog#SelectorPickerDialog QTreeWidget {{ background:{bg2}; color:{txt}; border:1px solid {border}; }}
 QDialog#SelectorPickerDialog QTreeWidget::item:selected {{ background:{accent}; color:{bg}; }}
 QDialog#SelectorPickerDialog QLineEdit {{ background:{bg2}; color:{txt}; border:1px solid {border}; padding:2px 4px; }}
 QDialog#SelectorPickerDialog QPushButton {{ background:{bg2}; color:{txt}; border:1px solid {border}; padding:4px 8px; }}
 QDialog#SelectorPickerDialog QPushButton:hover {{ background:{accent}; color:{bg}; }}
 /* High contrast variant adjustments */
 /* Rely on presence of high-contrast token differences (e.g., border.medium) */
{self._notification_dynamic_qss(c)}
        """.strip()

    # Dynamic segment for notification color roles -----------------
    def _notification_dynamic_qss(self, colors: Mapping[str, str]) -> str:
        try:
            from gui.design.notifications import list_notification_styles
        except Exception:
            return ""  # pragma: no cover
        lines: List[str] = []
        for style in list_notification_styles():  # type: ignore
            role = style.color_role
            bg = colors.get(role, colors.get("accent.base", "#3D8BFD"))
            # Use text.primary for readability; could derive contrast in future
            fg = colors.get("text.primary", "#FFFFFF")
            lines.append(
                f"QWidget#toastHost > QWidget#toastWidget[style_id='{style.id}'] {{ background:{bg}; color:{fg}; }}"
            )
        return "\n" + "\n".join(lines) if lines else ""

    def apply_custom(self, mapping: Mapping[str, str]) -> int:
        """Overlay a flattened color mapping onto current theme.

        Returns number of keys changed. Emits THEME_CHANGED if >0.
        """
        if not mapping:
            return 0
        old = self._cached_map.copy()
        changed = 0
        for k, v in mapping.items():
            # Accept any flattened color semantic (group.role) where value looks like a hex string
            if "." in k and isinstance(v, str) and v.startswith("#") and len(v) >= 4:
                if old.get(k) != v:
                    self._cached_map[k] = v
                    changed += 1
        if changed:
            # publish synthetic diff
            diff = ThemeDiff(
                {
                    k: (old.get(k), self._cached_map.get(k))
                    for k in mapping.keys()
                    if old.get(k) != self._cached_map.get(k)
                }
            )
            try:
                cb = services.try_get("color_blind_mode")
                if cb and getattr(cb, "mode", None):
                    apply_color_vision_filter_if_active(self._cached_map, cb.mode)
            except Exception:
                pass
            # IMPORTANT: Avoid re-normalizing contrast for direct user overrides of text.* colors
            # to prevent a user-specified text.primary (#222222) from being pushed back to a
            # higher-contrast fallback (#FFFFFF). We only augment missing aliases; skip contrast
            # normalization pass here to keep explicit overrides authoritative.
            try:
                self._augment_semantics(self._cached_map)
            except Exception:
                pass
            self._publish_theme_changed(diff)
        return changed

    # Filesystem theme integration ----------------------------------
    def load_filesystem_themes(self, directory: str | None = None) -> List[str]:
        """Discover JSON theme files in assets/themes and cache overlays.

        Returns list of loaded theme names (filename stems).
        """
        if directory is None:
            directory = os.path.join(os.getcwd(), "assets", "themes")
        loaded: List[str] = []
        try:
            p = Path(directory)
            if not p.exists():
                return loaded
            for file in p.glob("*.json"):
                try:
                    with file.open("r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    if not isinstance(data, dict):
                        continue
                    color = data.get("color")
                    if not isinstance(color, dict):
                        continue
                    flat: dict[str, str] = {}
                    for group, gv in color.items():
                        if not isinstance(gv, dict):
                            continue
                        for k, v in gv.items():
                            if isinstance(v, str) and v.startswith("#"):
                                flat[f"{group}.{k}"] = v
                    if flat:
                        name = file.stem
                        self._cached_filesystem_overlays[name] = flat
                        loaded.append(name)
                except Exception:
                    continue
        except Exception:
            return loaded
        return loaded

    def apply_filesystem_theme(self, name: str) -> bool:
        """Apply a discovered filesystem theme by name.

        Behavior change (Persistence Fix 7.10.69): Previously this only overlaid
        colors and did NOT persist the chosen theme name. As a result, selecting
        a custom/exported theme (e.g. via Theme JSON Editor) reverted to the
        prior built-in variant on next launch. Now we:
          - Apply the overlay (via existing apply_custom path for diff + event)
          - Set manager.variant to the filesystem theme name (logical identity)
          - Persist AppConfig.theme_variant so it is honored on restart
        """
        flat = getattr(self, "_cached_filesystem_overlays", {}).get(name)
        if not flat:
            return False
        # Apply overlay (publishes diff if any changes)
        self.apply_custom(flat)
        # Record variant identity & persist
        try:
            self.manager.variant = name  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            self._persist_variant(name)
        except Exception:
            pass
        return True

    def export_current_theme(self, name: str) -> Path | None:
        try:
            directory = Path(os.getcwd()) / "assets" / "themes"
            directory.mkdir(parents=True, exist_ok=True)
            payload: dict[str, dict[str, dict[str, str]]] = {"color": {}}
            for k, v in self._cached_map.items():
                if "." not in k:
                    continue
                group, role = k.split(".", 1)
                payload["color"].setdefault(group, {})[role] = v
            out = directory / f"{name}.json"
            with out.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            return out
        except Exception:
            return None

    # Instrumentation -------------------------------------------------
    def _maybe_log_slow(self, kind: str, value: str, elapsed_ms: float, diff: ThemeDiff) -> None:
        """Log and emit event if a style recalculation exceeded threshold.

        Always emits a debug log entry; warns and publishes 'style_recalc_slow' when
        elapsed_ms >= STYLE_RECALC_WARN_THRESHOLD_MS and diff contains changes.
        """
        try:
            changed_count = len(diff.changed)
            if elapsed_ms >= STYLE_RECALC_WARN_THRESHOLD_MS and not diff.no_changes:
                _logger.warning(
                    "style recalculation slow: kind=%s value=%s time=%.2fms changed=%d",
                    kind,
                    value,
                    elapsed_ms,
                    changed_count,
                )
                try:
                    bus = services.get_typed("event_bus", EventBus)
                    bus.publish(
                        "style_recalc_slow",
                        {
                            "kind": kind,
                            "value": value,
                            "elapsed_ms": elapsed_ms,
                            "changed": list(diff.changed.keys()),
                        },
                    )
                except Exception:
                    pass
            else:
                _logger.debug(
                    "style recalculation: kind=%s value=%s time=%.2fms changes=%d",
                    kind,
                    value,
                    elapsed_ms,
                    changed_count,
                )
        except Exception:
            pass

    # Internal helpers -------------------------------------------------
    @staticmethod
    def _augment_semantics(mapping: dict[str, str]) -> None:
        """Insert semantic alias keys expected by higher-level styling.

        This bridges design-token-level keys (base/elevated) to semantic
        roles (primary/secondary) without mutating original token names.
        """
        from gui.design.contrast import contrast_ratio as _cr  # local import for lazy usage

        # Background
        if "background.base" in mapping and "background.primary" not in mapping:
            mapping["background.primary"] = mapping["background.base"]
        if "background.elevated" in mapping and "background.secondary" not in mapping:
            mapping["background.secondary"] = mapping["background.elevated"]
        # Surface
        if "surface.primary" in mapping and "surface.card" not in mapping:
            mapping["surface.card"] = mapping["surface.primary"]
        # Accent
        if "accent.primary" in mapping and "accent.base" not in mapping:
            mapping["accent.base"] = mapping["accent.primary"]
        if "accent.primaryHover" in mapping and "accent.hover" not in mapping:
            mapping["accent.hover"] = mapping["accent.primaryHover"]
        if "accent.primaryActive" in mapping and "accent.active" not in mapping:
            mapping["accent.active"] = mapping["accent.primaryActive"]
        # Derive a default border.medium if accent present but border missing
        if "border.medium" not in mapping and "accent.base" in mapping:
            mapping["border.medium"] = mapping["accent.base"]
        # Derive focus border (slightly brighter than accent or fallback to border.medium)
        if "border.focus" not in mapping:
            base = mapping.get("accent.base") or mapping.get("border.medium")
            if base:
                try:
                    # Simple lighten by mixing with white
                    r = int(base[1:3], 16)
                    g = int(base[3:5], 16)
                    b = int(base[5:7], 16)
                    lr = min(255, int(r + (255 - r) * 0.35))
                    lg = min(255, int(g + (255 - g) * 0.35))
                    lb = min(255, int(b + (255 - b) * 0.35))
                    mapping["border.focus"] = f"#{lr:02X}{lg:02X}{lb:02X}"
                except Exception:
                    pass
        # Accent foreground (text placed on accent surfaces) ensure contrast >= 4.5 else invert heuristic
        if "accent.foreground" not in mapping and "accent.base" in mapping:
            accent = mapping["accent.base"]
            bg_candidates = ["#FFFFFF", "#000000", mapping.get("text.primary", "#FFFFFF")]
            chosen = "#FFFFFF"
            best = 0.0
            for cand in bg_candidates:
                try:
                    cr = _cr(cand, accent)
                    if cr > best:
                        best = cr
                        chosen = cand
                except Exception:
                    continue
            mapping["accent.foreground"] = chosen
        # Provide text.muted if missing
        if "text.muted" not in mapping and "text.primary" in mapping:
            p = mapping["text.primary"]
            try:
                r = int(p[1:3], 16)
                g = int(p[3:5], 16)
                b = int(p[5:7], 16)
                # Blend towards background for a subtle muted tone
                bg = mapping.get("background.primary", "#202020")
                br = int(bg[1:3], 16)
                bg_ = int(bg[3:5], 16)
                bb = int(bg[5:7], 16)
                mr = int((r * 0.65) + (br * 0.35))
                mg = int((g * 0.65) + (bg_ * 0.35))
                mb = int((b * 0.65) + (bb * 0.35))
                mapping["text.muted"] = f"#{mr:02X}{mg:02X}{mb:02X}"
            except Exception:
                pass

    # Contrast normalization ------------------------------------------
    @staticmethod
    def _normalize_contrast(mapping: dict[str, str]) -> None:
        bg = mapping.get("background.primary") or mapping.get("background.base")
        if not bg:
            return
        txt = mapping.get("text.primary")
        if txt:
            if contrast_ratio(txt, bg) < 4.5:
                # Choose fallback (white or black) with better contrast
                white_c = contrast_ratio("#FFFFFF", bg)
                black_c = contrast_ratio("#000000", bg)
                mapping["text.primary"] = "#FFFFFF" if white_c >= black_c else "#000000"
        muted = mapping.get("text.muted")
        if muted:
            if contrast_ratio(muted, bg) < 3.0:
                # Slightly blend towards primary or pick fallback
                primary = mapping.get("text.primary", "#FFFFFF")
                if contrast_ratio(primary, bg) >= 4.5:
                    mapping["text.muted"] = primary
                else:
                    mapping["text.muted"] = "#FFFFFF"

    # Variant enumeration ---------------------------------------------
    def available_variants(self) -> List[str]:
        base = ["default", "brand-neutral", "high-contrast"]
        overlays_all = available_variant_overlays()
        # Deduplicate overlays while preserving original order
        seen: set[str] = set()
        overlays: List[str] = []
        for ov in overlays_all:
            if ov not in seen:
                overlays.append(ov)
                seen.add(ov)
        # Filesystem themes (exclude any that collide with base/overlays case-insensitively)
        try:
            fs_all = list(getattr(self, "_cached_filesystem_overlays", {}).keys())
        except Exception:
            fs_all = []
        known_ci = {v.lower() for v in base + overlays}
        fs_filtered: List[str] = []
        for name in fs_all:
            if name.lower() in known_ci:
                continue  # skip duplicates (built-in exported copies)
            if name not in fs_filtered:
                fs_filtered.append(name)
        fs_filtered.sort()
        return base + overlays + fs_filtered

    # Diff helper -----------------------------------------------------
    @staticmethod
    def _build_diff(old: Mapping[str, str], new: Mapping[str, str]) -> ThemeDiff:
        changed: dict[str, tuple[str | None, str | None]] = {}
        keys = set(old.keys()) | set(new.keys())
        for k in keys:
            ov = old.get(k)
            nv = new.get(k)
            if ov != nv:
                changed[k] = (ov, nv)
        return ThemeDiff(changed)

    # Persistence helper ----------------------------------------------
    @staticmethod
    def _persist_variant(variant: str) -> None:
        try:
            cfg = services.try_get("app_config")
            if cfg and getattr(cfg, "theme_variant", None) != variant:
                cfg.theme_variant = variant  # type: ignore[attr-defined]
                from gui.app.config_store import save_config

                save_config(cfg)
        except Exception:  # pragma: no cover
            pass

    # Validation --------------------------------------------------------
    def validate(self, *, raise_on_error: bool = False) -> List[str]:
        missing = validate_theme_keys(self._cached_map)
        if missing and raise_on_error:
            raise ThemeValidationError(
                f"Missing required theme keys: {', '.join(missing)}"  # noqa: EM101
            )
        return missing

    # Internal ----------------------------------------------------------
    def _publish_theme_changed(self, diff: ThemeDiff) -> None:
        try:
            bus = services.get_typed("event_bus", EventBus)
        except Exception:  # pragma: no cover - if bus not yet registered
            return
        # Summarize changed keys (limit length to keep traces small)
        changed_keys = list(diff.changed.keys())
        summary = {"changed": changed_keys[:15], "count": len(changed_keys)}
        bus.publish(GUIEvent.THEME_CHANGED, summary)


def get_theme_service() -> ThemeService:
    return services.get_typed("theme_service", ThemeService)


def export_theme_snapshot(path: str) -> str:
    """Convenience function to export active ThemeService snapshot.

    Looks up the registered ThemeService and writes a snapshot to the
    requested path. Raises a RuntimeError if ThemeService is not registered.
    """
    svc = services.try_get("theme_service")
    if not isinstance(svc, ThemeService):  # pragma: no cover - defensive
        raise RuntimeError("ThemeService not registered")
    return svc.export_snapshot_to_file(path)
