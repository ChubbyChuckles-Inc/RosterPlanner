"""Load/save tracking state (JSON persistence placeholder)."""

from __future__ import annotations
import json
import os
from datetime import datetime
from typing import Any, Dict
from domain.models import TrackingState, Match
from dataclasses import asdict, is_dataclass
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
    def _serialize_match(m: Match) -> Dict[str, Any]:
        if is_dataclass(m):
            return asdict(m)
        # Fallback if not dataclass
        return {
            "team_id": getattr(m, "team_id", None),
            "match_number": getattr(m, "match_number", None),
            "date": getattr(m, "date", None),
            "time": getattr(m, "time", None),
            "weekday": getattr(m, "weekday", None),
            "home_team": getattr(m, "home_team", None),
            "guest_team": getattr(m, "guest_team", None),
            "home_score": getattr(m, "home_score", None),
            "guest_score": getattr(m, "guest_score", None),
            "status": getattr(m, "status", None),
        }

    payload: Dict[str, Any] = {
        "last_scrape": state.last_scrape.isoformat() if state.last_scrape else None,
        "divisions": list(state.divisions.keys()),
        "upcoming_matches": [_serialize_match(m) for m in state.upcoming_matches],
    }
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
