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

    Extended under milestone 7.10.50 to include ingestion lab configuration
    knobs so tests and future settings UI can control performance and safety
    without relying on environment variables.

    Attributes:
        allow_placeholders: When True, views may render synthetic placeholder
            data when real ingested data is not available. Default True.
        ingestion_preview_batch_cap: Max number of files listed in a batch
            preview output (caps log / UI size). Default 50 (previous constant).
        ingestion_preview_perf_threshold_ms: Threshold in milliseconds after
            which a preview operation surfaces a performance badge warning.
        ingestion_disallow_custom_python: When True, custom python expression
            transforms in rule payloads are rejected (simulation fails fast).
        command_palette_auto_resize: When True (default), Command Palette dialog
            dynamically sizes to fit longest command & up to 10 rows with animation.
            Users/tests can disable to lock at initial default size.
    """

    # singleton convenience instance used in many places in the GUI. Tests
    # and application bootstrap may replace this with a test double.
    instance: ClassVar["SettingsService"]

    allow_placeholders: bool = True
    ingestion_preview_batch_cap: int = 50
    ingestion_preview_perf_threshold_ms: float = 120.0
    ingestion_disallow_custom_python: bool = False
    command_palette_auto_resize: bool = True


# Initialize default singleton
SettingsService.instance = SettingsService()
