import pytest
from PyQt6.QtWidgets import QApplication
from gui.widgets.scrape_progress import ScrapeProgressWidget, PHASES

app = QApplication.instance() or QApplication([])


def test_weighted_progress_basic(qtbot):
    w = ScrapeProgressWidget()
    qtbot.addWidget(w)
    w.start()
    # Begin first phase
    first = PHASES[0]
    w.begin_phase(first.key)
    assert w.bar_total.value() == 0
    w.update_phase_progress(0.5)
    # Half of first phase weight
    expected = int((first.weight * 0.5) / sum(p.weight for p in PHASES) * 100)
    assert abs(w.bar_total.value() - expected) <= 1
    # Complete first phase
    w.complete_phase()
    expected_full_first = int((first.weight) / sum(p.weight for p in PHASES) * 100)
    assert abs(w.bar_total.value() - expected_full_first) <= 1
    # Start second phase and progress 20%
    second = PHASES[1]
    w.begin_phase(second.key)
    w.update_phase_progress(0.2)
    expected_running = (first.weight + second.weight * 0.2) / sum(p.weight for p in PHASES)
    assert abs(w.bar_total.value() - int(expected_running * 100)) <= 1


def test_debounce(qtbot, monkeypatch):
    w = ScrapeProgressWidget()
    qtbot.addWidget(w)
    w.start()
    first = PHASES[0]
    w.begin_phase(first.key)
    # Rapid updates should debounce (except final 1.0)
    w.update_phase_progress(0.1)
    val1 = w.bar_phase.value()
    w.update_phase_progress(0.11)  # likely ignored
    val2 = w.bar_phase.value()
    assert val2 == val1
    w.update_phase_progress(1.0)  # completion forced
    assert w.bar_phase.value() == 100
