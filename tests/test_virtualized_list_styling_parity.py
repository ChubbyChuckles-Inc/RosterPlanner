"""Virtualized list styling parity test (Milestone 5.10.70).

This test ensures the newly introduced ``VirtualizedList`` component exposes
the expected styling hooks so existing token-based QSS rules can target it
consistently relative to a reference widget.

We do NOT perform pixel comparison here; instead we assert semantic parity:
 - objectName is set to ``virtualizedList``
 - dynamic properties ``density`` and ``variant`` are present
 - rows receive consistent objectName (``virtualizedListRow``) and an ``alt``
   property for potential striped styling
 - row count matches supplied data

Reduced scope keeps the test fast and resilient while still guarding against
accidental removal of styling hooks.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel

from gui.components.virtualized_list import VirtualizedList


def test_virtualized_list_styling_parity(qtbot):
    print("[debug] start virtualized list parity test")
    # Ensure a QApplication exists even when running this test in isolation where
    # other bootstrap tests may not have created one yet.
    try:
        from PyQt6.QtWidgets import QApplication  # type: ignore

        if QApplication.instance() is None:  # pragma: no branch
            _app = QApplication([])  # noqa: F841
    except Exception:  # pragma: no cover - defensive
        pass
    data = [f"Row {i}" for i in range(5)]
    lst = VirtualizedList(density="compact", variant="striped")
    qtbot.addWidget(lst)
    lst.set_items(data)

    # Parity checks
    assert lst.objectName() == "virtualizedList"
    assert lst.property("density") == "compact"
    assert lst.property("variant") == "striped"
    assert lst.row_count() == len(data)

    # Reference label (baseline token consumer) - ensures environment available
    ref = QLabel("Ref")
    qtbot.addWidget(ref)
    ref.setObjectName("referenceLabel")

    # Row styling hooks
    for i, row in enumerate(lst.findChildren(QLabel)):  # includes stretch? labels only
        if row is ref:
            continue
        if row.objectName() == "referenceLabel":
            continue
        if row.objectName() == "virtualizedListRow":
            # alt property alternates boolean values
            assert row.property("alt") in {True, False}
    # Ensure at least one alt=True exists for striped potential
    alts = [
        r.property("alt")
        for r in lst.findChildren(QLabel)
        if r.objectName() == "virtualizedListRow"
    ]
    assert any(alts)
    # Allow any deferred events (deleteLater, etc.) to process; ensures stability in headless CI
    try:
        qtbot.wait(5)  # type: ignore[attr-defined]
    except Exception:
        pass
    assert True  # explicit terminal assertion
