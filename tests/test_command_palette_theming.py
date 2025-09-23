import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.command_palette import CommandPaletteDialog
from gui.services.command_registry import global_command_registry


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ensure_commands():
    # Register sample commands; attach category/icon attributes dynamically
    if not global_command_registry.is_registered("sample.open"):
        global_command_registry.register(
            command_id="sample.open",
            title="Open Team",
            callback=lambda: None,
        )
        entry = [e for e in global_command_registry.list() if e.command_id == "sample.open"][0]
        object.__setattr__(entry, "category", "Navigation")  # type: ignore[attr-defined]
        object.__setattr__(entry, "icon", "status-info")  # type: ignore[attr-defined]
    if not global_command_registry.is_registered("sample.refresh"):
        global_command_registry.register(
            command_id="sample.refresh",
            title="Refresh Data",
            callback=lambda: None,
        )
        entry = [e for e in global_command_registry.list() if e.command_id == "sample.refresh"][0]
        object.__setattr__(entry, "category", "Data")  # type: ignore[attr-defined]
        object.__setattr__(entry, "icon", "status-success")  # type: ignore[attr-defined]


def test_group_headers_and_highlight(qapp):
    _ensure_commands()
    dlg = CommandPaletteDialog()
    # Simulate user typing 'ref'
    dlg._refresh_list("ref")  # direct call for test
    # Expect at least one group header item (disabled) and one highlight span usage
    header_roles = []
    highlight_found = False
    from PyQt6.QtCore import Qt

    for i in range(dlg.list_widget.count()):  # type: ignore[attr-defined]
        item = dlg.list_widget.item(i)  # type: ignore[attr-defined]
        # Heuristic: headers have no user role data AND are not enabled
        if item.data(32) is None and not (
            item.flags() & Qt.ItemFlag.ItemIsEnabled
        ):  # 32 == UserRole
            header_roles.append(item.text())
        if "<span data-role='hl'>" in item.text():
            highlight_found = True
    assert header_roles, "No group headers detected"
    assert highlight_found, "No highlighted span for query"


def test_icon_badge_data_role_present(qapp):
    _ensure_commands()
    dlg = CommandPaletteDialog()
    dlg._refresh_list("")
    has_icon_role = False
    for i in range(dlg.list_widget.count()):  # type: ignore[attr-defined]
        item = dlg.list_widget.item(i)  # type: ignore[attr-defined]
        if item.data(1):  # 1 == DecorationRole
            has_icon_role = True
            break
    assert has_icon_role, "No icon decoration role present on any command item"
