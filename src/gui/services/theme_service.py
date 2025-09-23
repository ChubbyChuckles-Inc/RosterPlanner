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

from gui.design import ThemeManager, ThemeDiff, load_tokens
from .custom_theme import load_custom_theme, CustomThemeError
from .event_bus import EventBus, GUIEvent
from .service_locator import services

__all__ = [
    "ThemeService",
    "get_theme_service",
    "validate_theme_keys",
    "ThemeValidationError",
    "load_custom_theme",
    "CustomThemeError",
]


REQUIRED_COLOR_KEYS: tuple[str, ...] = (
    # Core surface/text roles (subset; extendable later)
    "background.primary",
    "background.secondary",
    "surface.card",
    "text.primary",
    "text.muted",
    "accent.base",
    "accent.hover",
    "accent.active",
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
        if cfg and getattr(cfg, "theme_variant", None) in (
            "default",
            "brand-neutral",
            "high-contrast",
        ):
            initial_variant = getattr(cfg, "theme_variant")  # type: ignore
        mgr = ThemeManager(tokens, variant=initial_variant)  # type: ignore[arg-type]
        base_map = dict(mgr.active_map())
        cls._augment_semantics(base_map)
        return cls(manager=mgr, _cached_map=base_map)

    # Accessors ---------------------------------------------------------
    def colors(self) -> Mapping[str, str]:
        return self._cached_map

    # Mutations ---------------------------------------------------------
    def set_variant(self, variant: str) -> ThemeDiff:
        diff = self.manager.set_variant(variant)  # type: ignore[arg-type]
        if not diff.no_changes:
            self._cached_map = dict(self.manager.active_map())
            self._augment_semantics(self._cached_map)
            self._publish_theme_changed(diff)
            # Persist variant if config available
            try:
                cfg = services.try_get("app_config")
                if cfg and getattr(cfg, "theme_variant", None) != variant:
                    cfg.theme_variant = variant  # type: ignore[attr-defined]
                    from gui.app.config_store import save_config

                    save_config(cfg)
            except Exception:  # pragma: no cover
                pass
        return diff

    def set_accent(self, base_hex: str) -> ThemeDiff:
        diff = self.manager.set_accent_base(base_hex)
        if not diff.no_changes:
            self._cached_map = dict(self.manager.active_map())
            self._augment_semantics(self._cached_map)
            self._publish_theme_changed(diff)
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
QHeaderView::section {{ background:{bg2}; color:{txt}; }}
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
 /* View Titles & Breadcrumb */
 QLabel#viewTitleLabel, QLabel#teamTitleLabel {{ font-weight:600; font-size:14px; color:{txt}; }}
 QLabel#breadcrumbLabel {{ color:{txt_muted}; font-size:11px; }}
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
            if (
                k.startswith("background.")
                or k.startswith("surface.")
                or k.startswith("text.")
                or k.startswith("accent.")
                or k.startswith("border.")
            ):
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
            self._publish_theme_changed(diff)
        return changed

    # Internal helpers -------------------------------------------------
    @staticmethod
    def _augment_semantics(mapping: dict[str, str]) -> None:
        """Insert semantic alias keys expected by higher-level styling.

        This bridges design-token-level keys (base/elevated) to semantic
        roles (primary/secondary) without mutating original token names.
        """
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
