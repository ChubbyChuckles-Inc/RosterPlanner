"""Bulk Edit Dialog (Milestone 7.10.A8)

Provides a lightweight UI + helper logic to apply batch modifications to
multiple list rule fields at once:

Features
--------
* Add a simple transform (trim, collapse_ws, to_number) to selected fields.
* Perform selector find/replace refinement across selected fields.
* Skips duplicates (will not add the same transform twice).

Design Notes
------------
* Kept intentionally small and dependency-light for maintainability.
* Core logic is extracted into ``bulk_edit_rules`` for direct unit testing
  without invoking the PyQt UI event loop.
* Dialog only surfaces list rule fields (table columns are positional and
  not individually mapped with selectors/transforms in this milestone).
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Tuple, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QComboBox,
    QLineEdit,
    QLabel,
)

try:  # pragma: no cover - import guard for tests
    from gui.components.chrome_dialog import ChromeDialog
except Exception:  # pragma: no cover
    from PyQt6.QtWidgets import QDialog as ChromeDialog  # type: ignore

SimpleRuleMapping = Dict[str, object]


def bulk_edit_rules(
    rules_mapping: SimpleRuleMapping,
    selections: List[Tuple[str, str]],
    *,
    add_transform: Optional[str] = None,
    find: Optional[str] = None,
    replace: Optional[str] = None,
) -> SimpleRuleMapping:
    """Apply bulk modifications to a rule mapping.

    Parameters
    ----------
    rules_mapping : dict
        Parsed rules JSON/YAML mapping (mutable copy will be produced).
    selections : list[(resource, field)]
        Target list rule fields to modify.
    add_transform : str, optional
        Simple transform (trim, collapse_ws, to_number) to add if absent.
    find, replace : str, optional
        When both provided and ``find`` is non-empty, perform a simple
        ``str.replace(find, replace)`` on the field selector text.
    """
    if not isinstance(rules_mapping, dict):  # defensive
        return rules_mapping
    res_map = rules_mapping.get("resources")
    if not isinstance(res_map, dict):
        return rules_mapping
    # Work on a shallow copy to avoid mutating original reference unexpectedly
    out = {
        **rules_mapping,
        "resources": {k: v.copy() if isinstance(v, dict) else v for k, v in res_map.items()},
    }
    resources = out["resources"]  # type: ignore[index]
    for rname, fname in selections:
        spec = resources.get(rname)
        if not isinstance(spec, dict):
            continue
        if spec.get("kind") != "list":
            continue
        fields = spec.get("fields")
        if not isinstance(fields, dict):
            continue
        fmap = fields.get(fname)
        if isinstance(fmap, str):  # normalize simple string form -> mapping
            fmap = {"selector": fmap}
            fields[fname] = fmap
        if not isinstance(fmap, dict):
            continue
        # Ensure selector
        selector_val = fmap.get("selector")
        if not isinstance(selector_val, str):
            continue
        # Apply selector replace
        if find and replace is not None and find in selector_val:
            fmap["selector"] = selector_val.replace(find, replace)
        # Add transform
        if add_transform:
            if add_transform not in {"trim", "collapse_ws", "to_number"}:
                # ignore unsupported transform kinds in this bulk mode
                pass
            else:
                chain = fmap.get("transforms")
                if chain is None:
                    fmap["transforms"] = [add_transform]
                elif isinstance(chain, list):
                    if add_transform not in chain:
                        chain.append(add_transform)
    return out


class BulkEditDialog(ChromeDialog):  # pragma: no cover - GUI wiring; logic tested via helper
    """Dialog for selecting multiple list rule fields and applying batch edits."""

    def __init__(self, rules_mapping: Mapping[str, object], parent=None):  # noqa: ANN001
        super().__init__(parent, title="Bulk Edit Fields")
        self.setObjectName("BulkEditDialog")
        try:
            self.resize(720, 520)
        except Exception:
            pass
        self._original = rules_mapping
        self._modified: Optional[SimpleRuleMapping] = None
        self._build_ui()
        self._populate()

    # UI -----------------------------------------------------------------
    def _build_ui(self):  # noqa: D401
        lay = self.content_layout() if hasattr(self, "content_layout") else QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Resource", "Field", "Selector", "Transforms"])
        lay.addWidget(self.tree)
        ctrl_row = QHBoxLayout()
        self.transform_combo = QComboBox()
        self.transform_combo.addItem("(no transform)", userData="")
        for t in ["trim", "collapse_ws", "to_number"]:
            self.transform_combo.addItem(t, userData=t)
        ctrl_row.addWidget(QLabel("Add Transform:"))
        ctrl_row.addWidget(self.transform_combo)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find selector fragment")
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with")
        ctrl_row.addWidget(self.find_edit)
        ctrl_row.addWidget(self.replace_edit)
        lay.addLayout(ctrl_row)
        btn_row = QHBoxLayout()
        self.btn_apply = QPushButton("Apply")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_apply.clicked.connect(self._on_apply)  # type: ignore
        self.btn_cancel.clicked.connect(self.reject)  # type: ignore
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_cancel)
        lay.addLayout(btn_row)

    def _populate(self):
        res_map = self._original.get("resources") if isinstance(self._original, dict) else {}
        if not isinstance(res_map, dict):
            return
        for rname, spec in sorted(res_map.items()):
            if not isinstance(spec, dict) or spec.get("kind") != "list":
                continue
            fields = spec.get("fields")
            if not isinstance(fields, dict):
                continue
            for fname, fmap in sorted(fields.items()):
                selector = ""
                transforms = ""
                if isinstance(fmap, str):
                    selector = fmap
                elif isinstance(fmap, dict):
                    selector = str(fmap.get("selector", ""))
                    tr = fmap.get("transforms")
                    if isinstance(tr, list):
                        transforms = ",".join(map(str, tr))
                item = QTreeWidgetItem([rname, fname, selector, transforms])
                item.setCheckState(0, Qt.CheckState.Unchecked)
                self.tree.addTopLevelItem(item)

    # Event Handlers -----------------------------------------------------
    def _on_apply(self):
        selections: List[Tuple[str, str]] = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked:
                selections.append((it.text(0), it.text(1)))
        add_transform = self.transform_combo.currentData() or None
        if add_transform == "":
            add_transform = None
        find = self.find_edit.text().strip() or None
        replace = self.replace_edit.text() if find else None
        self._modified = bulk_edit_rules(
            dict(self._original),
            selections,
            add_transform=add_transform,
            find=find,
            replace=replace,
        )
        self.accept()

    # API ----------------------------------------------------------------
    def modified_rules(self) -> Optional[SimpleRuleMapping]:
        return self._modified
