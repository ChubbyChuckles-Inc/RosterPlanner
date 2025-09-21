"""Load/save tracking state (JSON persistence placeholder)."""

from __future__ import annotations
import json
import os
from datetime import datetime
from typing import Any, Dict
from domain.models import TrackingState
from config import settings

FILENAME = "match_tracking.json"


def _path(base: str | None = None) -> str:
    base = base or settings.DATA_DIR
    return os.path.join(base, FILENAME)


def load_state(base: str | None = None) -> TrackingState:
    p = _path(base)
    if not os.path.exists(p):
        return TrackingState.empty()
    try:
        with open(p, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        last = datetime.fromisoformat(raw["last_scrape"]) if raw.get("last_scrape") else None
        # Divisions reconstruction deferred (requires richer serialization)
        return TrackingState(last_scrape=last, divisions={}, upcoming_matches=[])
    except Exception:
        return TrackingState.empty()


def save_state(state: TrackingState, base: str | None = None) -> None:
    p = _path(base)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    payload: Dict[str, Any] = {
        "last_scrape": state.last_scrape.isoformat() if state.last_scrape else None,
        # Divisions + matches serialization simplified for now
        "divisions": list(state.divisions.keys()),
        "upcoming_matches": [m.__dict__ for m in state.upcoming_matches],
    }
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
