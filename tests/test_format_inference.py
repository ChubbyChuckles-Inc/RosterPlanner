from __future__ import annotations

from gui.ingestion.format_inference import (
    infer_date_formats,
    infer_formats,
    infer_number_format,
)


def test_infer_number_format_normalises_decimal_samples() -> None:
    samples = [" 1.234,50 €", "12,0", "7,5", "0,00"]
    suggestion = infer_number_format(samples)
    assert suggestion is not None
    # Normalised preview should be decimal-dot strings regardless of locale handling
    assert suggestion.normalized_samples
    assert any(val.startswith("1234") for val in suggestion.normalized_samples)
    assert suggestion.confidence >= 0.75


def test_infer_date_formats_detects_day_month_year() -> None:
    samples = ["05.11.2023", "17.12.2023", "01.01.2024"]
    suggestions = infer_date_formats(samples)
    assert suggestions
    first = suggestions[0]
    assert first.formats == ["%d.%m.%Y"]
    assert first.example_iso == "2023-11-05"
    assert first.confidence >= 0.9


def test_infer_formats_returns_both_date_and_number() -> None:
    samples = [
        "05.11.2023",
        "06.11.2023",
        "1.234,50",
        "0,25",
    ]
    result = infer_formats(samples)
    assert result.number is not None
    assert result.dates
    assert result.number.normalized_samples
    assert result.dates[0].formats
