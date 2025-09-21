"""Structured parsing/validation errors for scraping pipeline."""

from __future__ import annotations
from typing import Any


class ParsingError(Exception):
    """Base class for parsing related issues."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.context = context or {}


class MissingSectionError(ParsingError):
    """Raised when an expected HTML section is absent."""


class ColumnMismatchError(ParsingError):
    """Raised when a table does not have the expected number of columns."""


class ValueExtractionError(ParsingError):
    """Raised when a critical value (id, score, etc.) cannot be extracted."""
