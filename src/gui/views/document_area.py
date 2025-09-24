"""DocumentArea - tabbed central workspace (Milestone 2.1.1).

Lightweight wrapper around QTabWidget that:
 - Prevents duplicate logical documents (by doc_id)
 - Provides open_or_focus(doc_id, title, factory)
 - Emits a simple Python callback hook (on_changed) when current tab changes

Future enhancements (later milestones):
 - Persistence of open tab order
 - Close handling + dirty state prompts
 - Context menu actions (close others, pin, etc.)
"""

from __future__ import annotations
from typing import Callable, Dict, Optional, Any
from PyQt6.QtWidgets import QTabWidget, QMenu, QColorDialog, QWidget, QGraphicsOpacityEffect
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QObject, pyqtSignal, Qt

from gui.services.tab_metadata_persistence import TabMetadataPersistenceService

__all__ = ["DocumentArea"]


class DocumentArea(QTabWidget):
    # (Could add a Qt signal later if needed; for now simple override)
    def __init__(self, base_dir: str | None = None):
        super().__init__()
        self._doc_index: Dict[str, int] = {}
        self._base_dir = base_dir or "."
        self._tab_meta = TabMetadataPersistenceService(self._base_dir)
        # Legacy compatibility structures expected by older tests
        self._documents = []  # type: ignore[attr-defined]
        self._widgets_by_id = {}  # type: ignore[attr-defined]
        # Enable custom context menu
        try:
            self.setContextMenuPolicy(0x0003)  # Qt.ContextMenuPolicy.CustomContextMenu value
            self.customContextMenuRequested.connect(self._on_tab_context_menu)  # type: ignore
        except Exception:
            pass

    # Public API -----------------------------------------------------
    def open_or_focus(self, doc_id: str, title: str, factory: Callable[[], Any]) -> Any:
        if doc_id in self._doc_index:
            idx = self._doc_index[doc_id]
            self.setCurrentIndex(idx)  # type: ignore[attr-defined]
            return self.widget(idx)  # type: ignore[attr-defined]
        widget = factory()
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

        if not isinstance(widget, QWidget):  # wrap plain objects for safety
            wrapper = QWidget()
            lay = QVBoxLayout(wrapper)
            lab = QLabel(repr(widget))
            lay.addWidget(lab)
            widget = wrapper
        idx = self.addTab(widget, title)  # type: ignore[attr-defined]
        self._doc_index[doc_id] = idx
        # Maintain simple records similar to prior implementation (object with doc_id attribute)
        record = type("_DocRecord", (), {"doc_id": doc_id, "widget": widget})()
        self._documents.append(record)  # type: ignore[attr-defined]
        self._widgets_by_id[doc_id] = record  # type: ignore[attr-defined]
        # Apply metadata (color)
        self._apply_tab_metadata(doc_id, idx)
        # Reorder if pinned
        self._reorder_pinned()
        self.setCurrentIndex(idx)  # type: ignore[attr-defined]
        # Animate open (fade + scale) unless in reduced motion or test mode
        try:
            self._animate_open(widget)
        except Exception:
            pass
        return widget

    def has_document(self, doc_id: str) -> bool:
        return doc_id in self._doc_index

    def document_widget(self, doc_id: str) -> Optional[Any]:
        if doc_id not in self._doc_index:
            return None
        return self.widget(self._doc_index[doc_id])  # type: ignore[attr-defined]

    # --- Pin & Color Support --------------------------------------
    def _on_tab_context_menu(self, pos):  # pragma: no cover - GUI path
        try:
            index = self.tabBar().tabAt(pos)  # type: ignore[attr-defined]
        except Exception:
            return
        if index < 0:
            return
        # Reverse lookup doc_id
        doc_id = None
        for k, v in self._doc_index.items():
            if v == index:
                doc_id = k
                break
        if not doc_id:
            return
        menu = QMenu(self)
        meta = self._tab_meta.get(doc_id)
        act_pin = menu.addAction("Unpin" if meta.pinned else "Pin")
        act_color = menu.addAction("Set Color...")
        act_clear_color = None
        if meta.color:
            act_clear_color = menu.addAction("Clear Color")
        act_close = menu.addAction("Close Tab")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == act_pin:
            self._tab_meta.set_pinned(doc_id, not meta.pinned)
            self._reorder_pinned()
        elif chosen == act_color:
            qcolor = QColorDialog.getColor(
                QColor(meta.color) if meta.color else QColor("#ffffff"), self
            )
            if qcolor.isValid():
                self._tab_meta.set_color(doc_id, qcolor.name())
                self._apply_tab_metadata(doc_id, self._doc_index[doc_id])
        elif chosen == act_clear_color and meta.color:
            self._tab_meta.set_color(doc_id, None)
            self._apply_tab_metadata(doc_id, self._doc_index[doc_id])
        elif chosen == act_close:
            self._close_tab(index)

    def _apply_tab_metadata(self, doc_id: str, index: int):  # pragma: no cover - GUI path
        try:
            meta = self._tab_meta.get(doc_id)
            if meta.color:
                self.tabBar().setTabTextColor(index, QColor(meta.color))  # type: ignore[attr-defined]
            else:
                # Reset to default palette color if available (ignore errors)
                pass
            if meta.pinned:
                self.tabBar().setTabText(index, f"📌 {self.tabText(index)}")  # type: ignore[attr-defined]
            else:
                txt = self.tabText(index)
                if txt.startswith("📌 "):
                    self.tabBar().setTabText(index, txt[3:])  # type: ignore[attr-defined]
        except Exception:
            pass

    def _reorder_pinned(self):  # pragma: no cover - GUI path
        # Move pinned tabs to the left while preserving their relative order
        try:
            pinned = []
            others = []
            for doc_id, idx in list(self._doc_index.items()):
                if self._tab_meta.get(doc_id).pinned:
                    pinned.append((doc_id, idx))
                else:
                    others.append((doc_id, idx))
            desired_order = [d for d, _ in sorted(pinned, key=lambda t: t[1])] + [
                d for d, _ in sorted(others, key=lambda t: t[1])
            ]
            # Rebuild if order differs
            current_widgets = {i: self.widget(i) for i in range(self.count())}  # type: ignore[attr-defined]
            current_titles = {i: self.tabText(i) for i in range(self.count())}  # type: ignore[attr-defined]
            new_widgets = []
            for doc_id in desired_order:
                idx = self._doc_index[doc_id]
                new_widgets.append((doc_id, current_widgets[idx], current_titles[idx]))
            if [d for d, _, _ in new_widgets] != list(self._doc_index.keys()):
                # Clear all tabs and rebuild
                while self.count():  # type: ignore[attr-defined]
                    self.removeTab(0)  # type: ignore[attr-defined]
                self._doc_index.clear()
                for doc_id, w, title in new_widgets:
                    new_idx = self.addTab(w, title)  # type: ignore[attr-defined]
                    self._doc_index[doc_id] = new_idx
                    self._apply_tab_metadata(doc_id, new_idx)
        except Exception:
            pass

    def _close_tab(self, index: int):  # pragma: no cover - GUI path
        try:
            w = self.widget(index)  # type: ignore[attr-defined]
            if w is None:
                return
            self._animate_close(index, w)
        except Exception:
            # Fallback to immediate removal
            try:
                self.removeTab(index)  # type: ignore[attr-defined]
            except Exception:
                pass

    # ---- Animation Helpers -------------------------------------------------
    def _motion_enabled(self) -> bool:
        # Honour reduced motion + test mode quick path
        import os

        if os.environ.get("RP_TEST_MODE") == "1":
            return True  # still run but extremely fast to exercise path
        if os.environ.get("RP_REDUCED_MOTION") == "1":
            return False
        return True

    def _duration_ms(self) -> int:
        import os

        if os.environ.get("RP_TEST_MODE") == "1":
            return 5
        # Fallback constant; could fetch from design tokens via motion.get_duration_ms
        try:
            from gui.design.loader import load_tokens
            from gui.design.motion import get_duration_ms

            tokens = load_tokens()
            return min(260, get_duration_ms(tokens, "subtle"))  # clamp to 260ms max
        except Exception:
            return 180

    def _animate_open(self, widget: QWidget):  # pragma: no cover - visual path
        if not self._motion_enabled():
            return
        # Apply opacity effect
        if widget.graphicsEffect() is None:
            eff = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(eff)
        else:
            eff = widget.graphicsEffect()
        try:
            eff.setOpacity(0.0)  # type: ignore
        except Exception:
            return
        anim = QPropertyAnimation(eff, b"opacity", widget)
        anim.setDuration(self._duration_ms())
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # Keep reference to prevent GC
        if not hasattr(self, "_live_anims"):
            self._live_anims = []  # type: ignore
        self._live_anims.append(anim)  # type: ignore

        def _cleanup():  # type: ignore
            try:
                self._live_anims.remove(anim)  # type: ignore
            except Exception:
                pass

        anim.finished.connect(_cleanup)  # type: ignore
        anim.start()

    def _animate_close(self, index: int, widget: QWidget):  # pragma: no cover - visual path
        import os

        if os.environ.get("RP_TEST_MODE") == "1":
            # Deterministic fast path for tests – skip animation scheduling
            self._finalize_close(index)
            return
        if not self._motion_enabled():
            self._finalize_close(index)
            return
        eff = widget.graphicsEffect()
        if eff is None:
            eff = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", widget)
        anim.setDuration(self._duration_ms())
        try:
            from gui.design.motion import parse_cubic_bezier  # reuse parser if custom curve desired
        except Exception:
            pass
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        if not hasattr(self, "_live_anims"):
            self._live_anims = []  # type: ignore
        self._live_anims.append(anim)  # type: ignore

        def _finish():  # type: ignore
            self._finalize_close(index)
            try:
                self._live_anims.remove(anim)  # type: ignore
            except Exception:
                pass

        anim.finished.connect(_finish)  # type: ignore
        anim.start()

    def _finalize_close(self, index: int):  # pragma: no cover - GUI path
        try:
            # Reverse map doc_id
            doc_id = None
            for k, v in list(self._doc_index.items()):
                if v == index:
                    doc_id = k
            self.removeTab(index)  # type: ignore[attr-defined]
            if doc_id:
                self._doc_index.pop(doc_id, None)
                for k, v in list(self._doc_index.items()):
                    if v > index:
                        self._doc_index[k] = v - 1
        except Exception:
            pass
