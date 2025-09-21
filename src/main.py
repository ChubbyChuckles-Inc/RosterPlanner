"""CLI entry point for RosterPlanner scraping and comparison utilities."""

from __future__ import annotations
import argparse
import json
import sys
from typing import Any
import os

from services import pipeline
from config import settings
from utils import naming
from core import filesystem


def cmd_run_full(args: argparse.Namespace) -> None:
    club = int(args.club)
    season = int(args.season) if args.season else settings.DEFAULT_SEASON
    out_dir = args.out or naming.data_dir()
    result = pipeline.run_full(club, season=season, data_dir=out_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def _list_files(base: str) -> set[str]:
    collected: set[str] = set()
    for root, _dirs, files in os.walk(base):
        for f in files:
            rel = root[len(base) :].lstrip("/\\")
            rel_path = f if not rel else f"{rel}/{f}"
            collected.add(rel_path.replace("\\", "/"))
    return collected


def cmd_compare(args: argparse.Namespace) -> None:
    old_dir = args.old
    new_dir = args.new
    out_path = args.out
    old_files = _list_files(old_dir)
    new_files = _list_files(new_dir)
    missing = sorted(f for f in old_files if f not in new_files)
    extra = sorted(f for f in new_files if f not in old_files)
    changed: list[str] = []  # Simplified: content diff omitted for speed
    result: dict[str, Any] = {
        "total_old": len(old_files),
        "total_new": len(new_files),
        "missing_in_new": missing,
        "extra_in_new": extra,
        "changed": changed,
    }
    # Ensure directory if provided
    import os as _os

    out_dirname = _os.path.dirname(out_path)
    if out_dirname:
        filesystem.ensure_dir(out_dirname)
    filesystem.write_text(out_path, json.dumps(result, indent=2, ensure_ascii=False))
    print(
        json.dumps(
            {k: len(v) if isinstance(v, list) else v for k, v in result.items()},
            indent=2,
            ensure_ascii=False,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="roster-planner")
    sub = p.add_subparsers(dest="command", required=True)

    run_full = sub.add_parser("run-full", help="Run full scrape pipeline")
    run_full.add_argument("--club", required=True, help="Club ID")
    run_full.add_argument("--season", required=False, help="Season year (start year)")
    run_full.add_argument("--out", required=False, help="Output directory for scrape")
    run_full.set_defaults(func=cmd_run_full)

    compare = sub.add_parser("compare-scrapes", help="Compare two scrape directories")
    compare.add_argument("--old", required=True, help="Legacy/base data directory")
    compare.add_argument("--new", required=True, help="New scrape data directory")
    compare.add_argument("--out", required=True, help="Output JSON path")
    compare.set_defaults(func=cmd_compare)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
