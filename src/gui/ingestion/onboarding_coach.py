"""Guided onboarding overlay for the Ingestion Lab panel (Milestone 7.10.A20)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, MutableMapping, Optional, Sequence


@dataclass(slots=True)
class OnboardingStep:
    """Describe a single spotlight step in the walkthrough."""

    widget: Any
    title: str
    body: str


try:  # pragma: no cover - imported lazily when PyQt6 available
    from PyQt6.QtCore import QPoint, QRect, QRectF, QTimer, Qt
    from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
    from PyQt6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except Exception:  # pragma: no cover - headless test environments
    Qt = None  # type: ignore
    QWidget = object  # type: ignore
else:

    class OnboardingCoach(QWidget):  # pragma: no cover - exercised via smoke/manual tests
        """Semi-transparent overlay that walks the user through key UI areas."""

        def __init__(
            self,
            parent: Any,
            steps: Sequence[OnboardingStep],
            *,
            on_finish: Optional[Callable[[str], None]] = None,
        ) -> None:
            super().__init__(parent)
            if not steps:
                raise ValueError("OnboardingCoach requires at least one step")
            self._steps = list(steps)
            self._index = 0
            self._target_rect = QRect()
            self._on_finish = on_finish

            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setGeometry(parent.rect())
            self.hide()

            self._card = QFrame(self)
            self._card.setObjectName("ingestionOnboardingCard")
            self._card.setStyleSheet(
                "#ingestionOnboardingCard {"
                "background: rgba(18, 22, 33, 235);"
                "color: #fdfdfd;"
                "border-radius: 10px;"
                "border: 1px solid rgba(255, 255, 255, 60);"
                "padding: 12px;"
                "}"
            )
            card_layout = QVBoxLayout(self._card)
            card_layout.setContentsMargins(16, 16, 16, 12)
            card_layout.setSpacing(12)

            self._title_label = QLabel("", self._card)
            self._title_label.setObjectName("ingestionOnboardingTitle")
            self._title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
            card_layout.addWidget(self._title_label)

            self._body_label = QLabel("", self._card)
            self._body_label.setWordWrap(True)
            self._body_label.setObjectName("ingestionOnboardingBody")
            card_layout.addWidget(self._body_label)

            button_row = QHBoxLayout()
            button_row.setContentsMargins(0, 0, 0, 0)
            button_row.setSpacing(8)
            self._back_btn = QPushButton("Back", self._card)
            self._back_btn.clicked.connect(self._prev_step)
            self._next_btn = QPushButton("Next", self._card)
            self._next_btn.clicked.connect(self._next_step)
            self._skip_btn = QPushButton("Skip", self._card)
            self._skip_btn.clicked.connect(lambda: self._finish("skip"))
            button_row.addWidget(self._back_btn)
            button_row.addWidget(self._next_btn)
            button_row.addStretch(1)
            button_row.addWidget(self._skip_btn)
            card_layout.addLayout(button_row)

            self._poll_timer = QTimer(self)
            self._poll_timer.setInterval(160)
            self._poll_timer.timeout.connect(self._update_target_rect)

        # ------------------------------------------------------------------
        def start(self) -> None:
            self._index = 0
            self._update_step()
            self._update_target_rect()
            self._poll_timer.start()
            self.show()
            self.raise_()
            self.setFocus()

        # ------------------------------------------------------------------
        def paintEvent(self, event) -> None:  # type: ignore[override]
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), QColor(10, 12, 18, 210))
            if not self._target_rect.isNull():
                path = QPainterPath()
                rectf = QRectF(self.rect())
                path.addRect(rectf)
                highlight = QRectF(self._target_rect.adjusted(-12, -12, 12, 12))
                path.addRoundedRect(highlight, 12, 12)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.fillPath(path, QColor(0, 0, 0, 0))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                pen = QPen(QColor(255, 255, 255, 220), 2)
                painter.setPen(pen)
                painter.drawRoundedRect(highlight, 12, 12)

        # ------------------------------------------------------------------
        def resizeEvent(self, event) -> None:  # type: ignore[override]
            super().resizeEvent(event)
            self.setGeometry(self.parentWidget().rect())
            self._update_target_rect()

        # ------------------------------------------------------------------
        def keyPressEvent(self, event) -> None:  # type: ignore[override]
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
                self._next_step()
                event.accept()
            elif event.key() == Qt.Key.Key_Escape:
                self._finish("skip")
                event.accept()
            else:
                super().keyPressEvent(event)

        # ------------------------------------------------------------------
        def mousePressEvent(self, event) -> None:  # type: ignore[override]
            if self._card.geometry().contains(event.pos()):
                super().mousePressEvent(event)
                return
            self._next_step()

        # ------------------------------------------------------------------
        def _current_step(self) -> OnboardingStep:
            return self._steps[self._index]

        # ------------------------------------------------------------------
        def _update_step(self) -> None:
            step = self._current_step()
            self._title_label.setText(step.title)
            self._body_label.setText(step.body)
            self._back_btn.setEnabled(self._index > 0)
            self._next_btn.setText("Finish" if self._index == len(self._steps) - 1 else "Next")
            self._update_target_rect()

        # ------------------------------------------------------------------
        def _update_target_rect(self) -> None:
            step = self._current_step()
            widget = step.widget
            if widget is None or not widget.isVisible():
                self._target_rect = QRect()
                self._card.move(40, 40)
                self.update()
                return
            rect = widget.rect()
            top_left = widget.mapTo(self.parentWidget(), rect.topLeft())
            bottom_right = widget.mapTo(self.parentWidget(), rect.bottomRight())
            new_rect = QRect(top_left, bottom_right)
            if new_rect != self._target_rect:
                self._target_rect = new_rect
                self._position_card()
                self.update()

        # ------------------------------------------------------------------
        def _position_card(self) -> None:
            if self._target_rect.isNull():
                self._card.move(40, 40)
                return
            parent_rect = self.rect()
            preferred = QPoint(self._target_rect.right() + 24, self._target_rect.top())
            card_size = self._card.sizeHint()
            x = min(preferred.x(), parent_rect.right() - card_size.width() - 24)
            x = max(24, x)
            y = min(preferred.y(), parent_rect.bottom() - card_size.height() - 24)
            y = max(24, y)
            self._card.move(x, y)
            self._card.resize(card_size)

        # ------------------------------------------------------------------
        def _next_step(self) -> None:
            if self._index >= len(self._steps) - 1:
                self._finish("complete")
                return
            self._index += 1
            self._update_step()

        # ------------------------------------------------------------------
        def _prev_step(self) -> None:
            if self._index == 0:
                return
            self._index -= 1
            self._update_step()

        # ------------------------------------------------------------------
        def _finish(self, state: str) -> None:
            self._poll_timer.stop()
            if self._on_finish:
                self._on_finish(state)
            self.hide()
            self.deleteLater()


SETTINGS_KEY = "onboarding_state_v1"


def should_run_onboarding(settings: Optional[MutableMapping[str, str]] = None) -> bool:
    """Return True if the onboarding walkthrough should be launched."""

    state = _read_state(settings)
    return state not in {"complete", "skip"}


def mark_onboarding_state(state: str, settings: Optional[MutableMapping[str, str]] = None) -> None:
    """Persist the onboarding state. Expected values: 'complete', 'skip', 'pending'."""

    if state not in {"complete", "skip", "pending"}:
        raise ValueError("Invalid onboarding state")
    store = _ensure_settings(settings)
    store[SETTINGS_KEY] = state


def mark_onboarding_complete(settings: Optional[MutableMapping[str, str]] = None) -> None:
    """Convenience wrapper to mark the walkthrough as complete."""

    mark_onboarding_state("complete", settings=settings)


def mark_onboarding_skipped(settings: Optional[MutableMapping[str, str]] = None) -> None:
    """Mark the walkthrough as skipped to avoid re-launching automatically."""

    mark_onboarding_state("skip", settings=settings)


def _read_state(settings: Optional[MutableMapping[str, str]]) -> str:
    store = _ensure_settings(settings)
    value = store.get(SETTINGS_KEY, "pending")
    return str(value)


def _ensure_settings(settings: Optional[MutableMapping[str, str]]) -> MutableMapping[str, str]:
    if settings is not None:
        return settings
    try:
        from PyQt6.QtCore import QSettings

        qs = QSettings("RosterPlanner", "IngestionLab")
        return _QSettingsAdapter(qs)
    except Exception:  # pragma: no cover - fallback when QSettings unavailable
        return _MemorySettings()


class _QSettingsAdapter(dict):  # pragma: no cover - thin wrapper around QSettings
    def __init__(self, settings):
        super().__init__()
        self._settings = settings

    def __getitem__(self, key):
        val = self._settings.value(key, "pending")
        return val if val is not None else "pending"

    def __setitem__(self, key, value):
        self._settings.setValue(key, value)

    def get(self, key, default=None):
        val = self._settings.value(key, default)
        return val if val is not None else default


class _MemorySettings(dict):
    """Fallback mutable mapping used in headless/test environments."""

    pass
