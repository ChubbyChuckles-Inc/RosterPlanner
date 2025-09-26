from __future__ import annotations

from gui.services.theme_service import ThemeService


def test_qss_includes_ingestion_lab_and_selector_picker():
    svc = ThemeService.create_default()
    qss = svc.generate_qss()
    # Core selectors for ingestion lab
    assert "#ingestionLabFileTree" in qss
    assert "#ingestionLabRuleEditor" in qss
    assert "#ingestionLabPreview" in qss
    assert "#ingestionLabLog" in qss
    # Selector picker dialog styling
    assert "#SelectorPickerDialog" in qss
