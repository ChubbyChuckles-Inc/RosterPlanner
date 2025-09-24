"""Stats Dock View

Initial UI integration for Milestone 6: shows KPIs and a simple time-series + histogram summary.
Chart visualizations are deferred to Milestone 7; for now we present textual summaries.
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QHeaderView,
)

from gui.viewmodels.stats_viewmodel import StatsViewModel


class StatsDockView(QWidget):  # pragma: no cover - thin widget container
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._vm = StatsViewModel()
        self._kpi_table = QTableWidget(0, 3)
        self._kpi_table.setHorizontalHeaderLabels(["KPI", "Value", "Units"])
        self._kpi_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._timeseries_label = QLabel("No time-series loaded")
        self._hist_label = QLabel("No histogram")
        lay = QVBoxLayout(self)
        kpi_group = QGroupBox("Team KPIs")
        kpi_lay = QVBoxLayout(kpi_group)
        kpi_lay.addWidget(self._kpi_table)
        lay.addWidget(kpi_group)
        ts_group = QGroupBox("Match Time-Series (Summary)")
        ts_lay = QVBoxLayout(ts_group)
        ts_lay.addWidget(self._timeseries_label)
        lay.addWidget(ts_group)
        hist_group = QGroupBox("LivePZ Histogram (Counts)")
        hist_lay = QVBoxLayout(hist_group)
        hist_lay.addWidget(self._hist_label)
        lay.addWidget(hist_group)

    def load_team(self, team_id: str):  # pragma: no cover - GUI wiring
        state = self._vm.load_for_team(team_id)
        # KPIs
        self._kpi_table.setRowCount(len(state.kpis))
        for row, kv in enumerate(state.kpis):
            self._kpi_table.setItem(row, 0, QTableWidgetItem(kv.label))
            self._kpi_table.setItem(
                row, 1, QTableWidgetItem("" if kv.value is None else str(kv.value))
            )
            self._kpi_table.setItem(row, 2, QTableWidgetItem(kv.units or ""))
        # Time-series summary
        if state.timeseries:
            last = state.timeseries[-1]
            self._timeseries_label.setText(
                f"{len(state.timeseries)} days | cumulative win%: "
                f"{round(last.cumulative_win_pct*100,2) if last.cumulative_win_pct is not None else '—'}"
            )
        else:
            self._timeseries_label.setText("No matches yet")
        # Histogram summary
        if state.histogram and state.histogram.bins:
            counts = state.histogram.as_dict()
            parts = [f"{k}:{v}" for k, v in counts.items()]
            self._hist_label.setText(
                f"Players: {state.histogram.players_with_live_pz}/{state.histogram.total_players} | "
                + ", ".join(parts[:6])
                + (" ..." if len(parts) > 6 else "")
            )
        else:
            self._hist_label.setText("No LivePZ data")

    def viewmodel(self) -> StatsViewModel:
        return self._vm


__all__ = ["StatsDockView"]
