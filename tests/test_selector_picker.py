import pytest

from gui.ingestion.selector_picker import build_selector_for_item, SelectorPickerDialog
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def test_build_selector_simple(qtbot):  # qtbot fixture if available else fallback
    html = """<html><body><div id='main'><ul class='lst a'><li class='row'>One</li><li class='row special'>Two</li></ul></div></body></html>"""
    dlg = SelectorPickerDialog(html)
    qtbot.addWidget(dlg)
    tree = dlg._tree  # access internal for test
    # Expand and locate the UL node then second LI
    root = tree.topLevelItem(0)
    assert root.text(0) == "document"
    div = root.child(0)  # html
    # descend to body->div#main->ul.lst.a->li
    body = div.child(0)
    div_main = body.child(0)
    ul = div_main.child(0)
    li_second = ul.child(1)
    selector = build_selector_for_item(li_second)
    # Expect path: html > body > div#main > ul.lst.a > li.row:nth-of-type(2)
    assert "div#main" in selector
    assert selector.endswith("li.row:nth-of-type(2)")
    # Accept dialog and ensure selected_selector returns value after click
    dlg._on_item_clicked(li_second)
    assert dlg.selected_selector().endswith("li.row:nth-of-type(2)")
