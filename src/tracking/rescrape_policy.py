"""Logic to determine whether a division needs re-scraping."""

from __future__ import annotations
from datetime import datetime, timedelta
from domain.models import TrackingState


WINDOW_HOURS = 2


def should_rescrape(division_name: str, state: TrackingState) -> bool:
    if not state.upcoming_matches:
        return True
    if not state.last_scrape:
        return True
    last = state.last_scrape
    for m in state.upcoming_matches:
        if m.team_id and division_name in (m.team_id, getattr(m, "division_name", division_name)):
            # Placeholder logic; real division association needed later
            try:
                if m.date and m.time:
                    dt = datetime.strptime(f"{m.date} {m.time}", "%d.%m.%Y %H:%M")
                    if last <= dt <= last + timedelta(hours=WINDOW_HOURS):
                        return True
            except Exception:
                return True
    return False
