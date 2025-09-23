import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.theme_json_editor import ThemeJsonEditorDialog
from gui.services.theme_service import get_theme_service, ThemeService
from gui.services.service_locator import services


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_theme_json_editor_preview_and_cancel(qapp):
    # Ensure theme service exists (register if missing)
    if not services.try_get("theme_service"):
        services.register("theme_service", ThemeService.create_default())
    theme = get_theme_service()
    original_color = theme.colors().get("accent.base")
    dlg = ThemeJsonEditorDialog()
    dlg.editor.setPlainText('{"color": {"accent": {"base": "#123456"}}}')
    flat = dlg._parse_editor_json()
    assert flat and flat.get("accent.base") == "#123456"
    dlg._on_preview()
    assert theme.colors().get("accent.base") == "#123456"
    # Simulate cancel to rollback (dialog keeps original snapshot)
    dlg._on_cancel()
    assert theme.colors().get("accent.base") == original_color


def test_theme_json_editor_apply_updates_baseline(qapp):
    if not services.try_get("theme_service"):
        services.register("theme_service", ThemeService.create_default())
    theme = get_theme_service()
    dlg = ThemeJsonEditorDialog()
    dlg.editor.setPlainText('{"color": {"accent": {"base": "#654321"}}}')
    dlg._on_apply()
    assert theme.colors().get("accent.base") == "#654321"
    # Cancel after apply should not revert because baseline updated
    dlg._on_cancel()
    assert theme.colors().get("accent.base") == "#654321"  # persists after cancel
