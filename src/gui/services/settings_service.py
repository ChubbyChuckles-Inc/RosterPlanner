"""Application-level settings service for runtime toggles.

This small service centralizes feature flags and user preferences used by the
GUI. It is intentionally lightweight and designed to be injected or accessed
via the global service locator. For now it exposes `allow_placeholders` which
controls whether UI placeholder generators are used when repository-backed
data is absent. Default is True to preserve existing test expectations; the
roadmap task 5.9.30 may flip this to False after integration tests are
updated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class SettingsService:
    """Runtime settings and feature flags.

    Attributes:
        allow_placeholders: When True, views may render synthetic placeholder
            data when real ingested data is not available. Default True to
            avoid breaking current integration tests; can be toggled by the
            application or test fixtures.
    """

    # singleton convenience instance used in many places in the GUI. Tests
    # and application bootstrap may replace this with a test double.
    instance: ClassVar["SettingsService"]

    allow_placeholders: bool = True


# Initialize default singleton
SettingsService.instance = SettingsService()
