"""CLI to compare two scrape directories."""
from __future__ import annotations
import argparse, json, sys, os
from services.compare_scrapes import compare_dirs, unified_diff


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare two roster scrape output directories")
    p.add_argument("old", help="Old/original data directory")
    p.add_argument("new", help="New modular scrape data directory")
    p.add_argument("--diff", metavar="RELFILE", help="Show unified diff for a specific relative file")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    res = compare_dirs(args.old, args.new)
    print(json.dumps(res, indent=2))
    if args.diff:
        old_file = os.path.join(args.old, args.diff)
        new_file = os.path.join(args.new, args.diff)
        print("\n=== Unified Diff ===")
        print(unified_diff(old_file, new_file))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())