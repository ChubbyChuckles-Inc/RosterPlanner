"""Utilities to compare two scrape output directories and report discrepancies."""
from __future__ import annotations
import os
import difflib
from typing import Dict, List, Tuple

EXTENSIONS = {".html", ".json"}


def collect_files(root: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for base, _, files in os.walk(root):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in EXTENSIONS:
                continue
            rel = os.path.relpath(os.path.join(base, f), root)
            mapping[rel] = os.path.join(base, f)
    return mapping


def compare_dirs(old: str, new: str) -> Dict[str, List[str]]:
    old_files = collect_files(old)
    new_files = collect_files(new)
    old_set = set(old_files.keys())
    new_set = set(new_files.keys())
    missing_in_new = sorted(list(old_set - new_set))
    extra_in_new = sorted(list(new_set - old_set))
    common = sorted(list(old_set & new_set))
    changed: List[str] = []
    for rel in common:
        try:
            with open(old_files[rel], "r", encoding="utf-8", errors="ignore") as f1, open(
                new_files[rel], "r", encoding="utf-8", errors="ignore"
            ) as f2:
                if f1.read() != f2.read():
                    changed.append(rel)
        except Exception:
            changed.append(rel)
    return {
        "missing_in_new": missing_in_new,
        "extra_in_new": extra_in_new,
        "changed": changed,
        "total_old": [str(len(old_files))],
        "total_new": [str(len(new_files))],
    }


def unified_diff(old_file: str, new_file: str, n: int = 3) -> str:
    try:
        with open(old_file, "r", encoding="utf-8", errors="ignore") as f1, open(
            new_file, "r", encoding="utf-8", errors="ignore"
        ) as f2:
            old_lines = f1.readlines()
            new_lines = f2.readlines()
        diff = difflib.unified_diff(old_lines, new_lines, fromfile=old_file, tofile=new_file, n=n)
        return "".join(diff)
    except Exception as e:
        return f"Error generating diff: {e}"
