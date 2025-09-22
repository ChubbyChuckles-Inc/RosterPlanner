"""Division table normalization utilities (Milestone 5.3).

Takes raw `DivisionStandingEntry` rows (already parsed from HTML elsewhere)
and enriches / normalizes derived fields for display:
 - Ensures recent_form is uppercased and trimmed to last N (default 5).
 - Provides helper to compute differential text.

This remains deliberately simple until real parsing integration; unit
tests validate behavior with synthetic rows.
"""

from __future__ import annotations
from typing import List
from dataclasses import dataclass

from gui.models import DivisionStandingEntry

__all__ = ["DivisionTableNormalizer", "NormalizedDivisionRow"]


@dataclass
class NormalizedDivisionRow:
    entry: DivisionStandingEntry
    differential_text: str | None
    form: str | None


class DivisionTableNormalizer:
    def __init__(self, form_window: int = 5):
        self.form_window = form_window

    def normalize(self, rows: List[DivisionStandingEntry]) -> List[NormalizedDivisionRow]:
        normalized: List[NormalizedDivisionRow] = []
        for e in rows:
            diff_val = e.differential()
            diff_txt = (
                None if diff_val is None else (f"+{diff_val}" if diff_val > 0 else str(diff_val))
            )
            form = None
            if e.recent_form:
                f = e.recent_form.upper().replace(" ", "")
                if len(f) > self.form_window:
                    f = f[-self.form_window :]
                form = f
            normalized.append(NormalizedDivisionRow(entry=e, differential_text=diff_txt, form=form))
        return normalized
