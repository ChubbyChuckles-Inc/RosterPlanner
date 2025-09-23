"""Plugin style contract validator (Milestone 5.10.18).

Validates that a QWidget (representing a plugin-provided UI surface) only uses
approved design token driven colors, by scanning its `styleSheet()` for hex
color literals and comparing against the active theme color map (semantic
values) plus any explicitly whitelisted neutrals.

This is a lightweight runtime check to help plugin authors stay within the
visual language contract (no arbitrary hardcoded colors that would break
theming or accessibility). It reuses the color drift detection normalization
logic but operates on a single style sheet string instead of source files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Sequence, Set

from gui.design.color_drift import normalize_hex, HEX_PATTERN  # reuse pattern

__all__ = [
    "StyleContractIssue",
    "StyleContractReport",
    "StyleContractValidator",
]


@dataclass(frozen=True)
class StyleContractIssue:
    literal: str
    normalized: str
    reason: str
    context: str


@dataclass(frozen=True)
class StyleContractReport:
    issues: List[StyleContractIssue]
    allowed: int
    disallowed: int

    @property
    def ok(self) -> bool:  # noqa: D401
        return self.disallowed == 0


class StyleContractValidator:
    """Validate plugin widget stylesheet adherence."""

    def __init__(
        self,
        allowed_hex: Iterable[str],
        *,
        whitelist: Sequence[str] | None = None,
        min_contrast: float | None = None,  # reserved
    ) -> None:
        self._allowed: Set[str] = {h.upper() for h in allowed_hex}
        self._whitelist: Set[str] = {h.upper() for h in (whitelist or [])}
        self._min_contrast = min_contrast

    def scan_stylesheet(self, qss: str) -> StyleContractReport:
        issues: List[StyleContractIssue] = []
        allowed_count = 0
        disallowed_count = 0
        for match in HEX_PATTERN.finditer(qss):
            lit = match.group(0)
            norm = normalize_hex(lit)
            if norm in self._allowed or norm in self._whitelist:
                allowed_count += 1
                continue
            issues.append(
                StyleContractIssue(
                    literal=lit,
                    normalized=norm,
                    reason="hex not in active theme nor whitelist",
                    context=self._extract_context(qss, match.start(), match.end()),
                )
            )
            disallowed_count += 1
        return StyleContractReport(
            issues=issues, allowed=allowed_count, disallowed=disallowed_count
        )

    @staticmethod
    def _extract_context(src: str, start: int, end: int, window: int = 50) -> str:
        s = max(0, start - window)
        e = min(len(src), end + window)
        return src[s:e].replace("\n", " ")

    @classmethod
    def from_theme_mapping(
        cls,
        mapping: Mapping[str, str],
        *,
        whitelist: Sequence[str] | None = None,
    ) -> "StyleContractValidator":
        return cls(mapping.values(), whitelist=whitelist)
