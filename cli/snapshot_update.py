"""CLI command to (re)generate snapshot extraction baselines (Milestone 7.10.59).

This tool executes a set of ingestion rule sets over HTML input files and
stores the resulting extracted resource row payloads as JSON snapshot
baselines. These baselines back regression tests that assert future
extraction logic changes are intentional.

Design choices:
- Reuse existing RuleSet + adapter pipeline (no duplicate parsing logic).
- Deterministic ordering: resources and rows are sorted for stable hashes.
- Simple discovery: by default scans data/ directory for *.html files unless
  explicit --input provided.
- Output location: tests/_extraction_snapshots/<snapshot_name>.json
- Update semantics: always overwrites the snapshot file (idempotent given
  deterministic ordering) unless --dry-run.

Usage examples:
  python -m cli.snapshot_update --rules rules/example_rules.json --name baseline_division
  python -m cli.snapshot_update --rules rules/standings.json --input data/division/*.html --name standings_v2

Future enhancements (documented for roadmap linkage):
- Allow multiple rule files (merge or iterate) and multi-snapshot batch mode.
- Add --fail-on-diff to compare in-memory generation with existing file.
- Add hashing summary for quick diff inspection in PRs.
"""
from __future__ import annotations

import argparse, json, glob, sys
from pathlib import Path
from typing import Dict, Any

from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_adapter import adapt_ruleset_over_files

SNAPSHOT_DIR = Path("tests/_extraction_snapshots")


def _load_rules(path: Path) -> RuleSet:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RuleSet.from_mapping(data)


def _collect_html(paths: list[str]) -> Dict[str, str]:
    collected: Dict[str, str] = {}
    for p in paths:
        pp = Path(p)
        if pp.is_file():
            collected[pp.name] = pp.read_text(encoding="utf-8", errors="ignore")
    return collected


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="snapshot-update", description="Generate/update extraction snapshots")
    p.add_argument("--rules", required=True, help="Path to rule set JSON file")
    p.add_argument("--name", required=True, help="Snapshot logical name (file stem)")
    p.add_argument("--input", nargs="*", help="HTML file paths or glob patterns (default: data/*.html)")
    p.add_argument("--allow-expr", action="store_true", help="Enable expression transforms when ruleset requires it")
    p.add_argument("--dry-run", action="store_true", help="Do not write file; print summary only")
    return p


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    rule_path = Path(args.rules)
    if not rule_path.exists():
        ap.error(f"Rules file not found: {rule_path}")
    rs = _load_rules(rule_path)
    if rs.allow_expressions is False and args.allow_expr:
        # Optional: toggle flag if caller asserts it's safe
        rs.allow_expressions = True  # type: ignore[attr-defined]

    inputs: list[str]
    if args.input:
        expanded: list[str] = []
        for pattern in args.input:
            matches = glob.glob(pattern)
            if matches:
                expanded.extend(matches)
        # If no matches at all (and patterns supplied) treat as error.
        if not expanded:
            ap.error("No HTML input files matched provided --input patterns")
        inputs = expanded
    else:
        inputs = glob.glob("data/*.html")
    if not inputs:
        ap.error("No HTML input files discovered")

    html_map = _collect_html(inputs)
    bundle = adapt_ruleset_over_files(rs, html_map)

    # Deterministic snapshot structure
    snapshot: Dict[str, Any] = {"resources": {}, "meta": {"rule_version": rs.version}}
    for rname in sorted(bundle.resources.keys()):
        res = bundle.resources[rname]
        rows = [dict(row) for row in res.rows]
        # Sort rows by their JSON representation for determinism
        rows_sorted = sorted(rows, key=lambda d: json.dumps(d, sort_keys=True))
        snapshot["resources"][rname] = {
            "kind": res.kind,
            "row_count": len(rows_sorted),
            "rows": rows_sorted,
        }
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SNAPSHOT_DIR / f"{args.name}.json"
    out_json = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False)
    if args.dry_run:
        print(f"[DRY-RUN] Snapshot would be written to {out_path}")
        print(out_json[:500] + ("..." if len(out_json) > 500 else ""))
        return 0
    out_path.write_text(out_json, encoding="utf-8")
    print(f"Snapshot written: {out_path} (resources={len(snapshot['resources'])})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
