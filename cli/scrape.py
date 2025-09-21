"""Command line entrypoint for new modular scraping pipeline."""

from __future__ import annotations
import argparse
import json
from services import pipeline


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RosterPlanner scraping pipeline")
    p.add_argument("--club-id", type=int, default=2294, help="Club ID to start from")
    p.add_argument("--season", type=int, default=2025, help="Season year")
    p.add_argument("--json", action="store_true", help="Output JSON summary")
    p.add_argument("--full", action="store_true", help="Run full scrape workflow")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.full:
        result = pipeline.run_full(club_id=args.club_id, season=args.season)
    else:
        result = pipeline.run_basic(club_id=args.club_id, season=args.season)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        mode = "FULL" if args.full else "BASIC"
        print(f"Scrape summary ({mode}):")
        for k, v in result.items():
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
