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
import re


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

    # Cleaning ------------------------------------------------------
    def clean_html(self, html: str) -> str:
        """Produce a simplified 'cleaned' version of HTML for diffing.

        Steps:
        - Remove <script> and <style> blocks
        - Strip HTML comments
        - Collapse runs of whitespace to a single space
        - Trim leading/trailing space per line and drop empty leading/trailing lines
        """
        if not html:
            return ""
        # Remove script/style blocks (non-greedy, case-insensitive)
        cleaned = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        cleaned = re.sub(r"<style[\s\S]*?</style>", "", cleaned, flags=re.IGNORECASE)
        # Remove comments
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
        # Collapse whitespace
        cleaned = re.sub(r"\s+", " ", cleaned)
        # Normalize line breaks around tags for readability (optional minimal formatting)
        cleaned = re.sub(r">\s<", ">\n<", cleaned)
        lines = [l.strip() for l in cleaned.splitlines()]
        # Remove empty lines at start/end
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)


def _safe_read(path: Path | None) -> str:
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


__all__ = ["HtmlDiffService", "HtmlSource"]
