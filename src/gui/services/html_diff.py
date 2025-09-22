"""HTML Diff & Retrieval Service (Milestone 5.5)

Provides small helpers to:
 - Locate the *current* HTML source file for a team or division.
 - Locate the *previous* version (heuristic: newest older file by timestamp naming if available).
 - Produce a unified diff (line-based) between previous and current versions.

This deliberately avoids external dependencies; for richer diffs later we
can extend with colored/side-by-side rendering.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Iterable
import difflib


@dataclass
class HtmlSource:
    label: str
    current_path: Path
    previous_path: Optional[Path]
    current_text: str
    previous_text: Optional[str]


class HtmlDiffService:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    # Resolution ----------------------------------------------------
    def find_team_roster_html(self, team_name: str) -> Optional[HtmlSource]:
        pattern = f"team_roster_*{team_name.replace(' ', '_')}*.html"
        matches = list(self.base_dir.rglob(pattern))
        if not matches:
            return None
        # Choose latest by modified time
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        current = matches[0]
        prev = matches[1] if len(matches) > 1 else None
        cur_text = _safe_read(current)
        prev_text = _safe_read(prev) if prev else None
        return HtmlSource(
            label=current.name,
            current_path=current,
            previous_path=prev,
            current_text=cur_text,
            previous_text=prev_text,
        )

    # Diff ----------------------------------------------------------
    def unified_diff(self, before: str | None, after: str, *, context: int = 3) -> str:
        before_lines = (before or "").splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)
        diff_iter: Iterable[str] = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="previous" if before else "previous (none)",
            tofile="current",
            n=context,
        )
        return "".join(diff_iter)


def _safe_read(path: Path | None) -> str:
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


__all__ = ["HtmlDiffService", "HtmlSource"]
