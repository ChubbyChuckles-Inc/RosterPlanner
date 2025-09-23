"""Helper script to capture & persist initial visual regression baselines.

Run with QT_QPA_PLATFORM=offscreen to avoid opening real windows:
  set QT_QPA_PLATFORM=offscreen
  python scripts/dump_visual_baselines.py

This script is idempotent; it overwrites existing baseline PNG/JSON files.
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from gui.components.empty_state import EmptyStateWidget
from gui.views.division_table_view import DivisionTableView
from gui.components.toast_host import ToastHost, NotificationManager
from gui.services.theme_service import ThemeService
from gui.testing.visual_regression import capture_widget_screenshot, hash_image_bytes

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
app = QApplication.instance() or QApplication([])
app.setStyle("Fusion")

base_dir = Path("tests/_visual_baseline/core")
base_dir.mkdir(parents=True, exist_ok=True)

def capture_case(filename: str, factory, size):
    data = capture_widget_screenshot(factory, size=size)
    h = hash_image_bytes(data)
    (base_dir / f"{filename}.png").write_bytes(data)
    (base_dir / f"{filename}.json").write_text(json.dumps({"hash": h}, indent=2) + "\n")
    return h

hashes = {}
# Empty state example
hashes['empty_state_no_division_rows'] = capture_case('empty_state_no_division_rows', lambda: EmptyStateWidget('no_division_rows'), (320,140))
# Division table (empty)
hashes['division_table_empty'] = capture_case('division_table_empty', lambda: DivisionTableView(), (640,260))
# Toast host single toast
host = ToastHost()
manager = NotificationManager(host, disable_timers=True)
manager.show_notification('info', 'Hello world')
hashes['toast_info_single'] = capture_case('toast_info_single', lambda: host, (320,130))

print("Captured baselines:")
for k,v in hashes.items():
    print(f"  {k}: {v}")
