"""Filesystem utility helpers."""

from __future__ import annotations
import os
import glob
from typing import Iterable


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_text(path: str, content: str, encoding: str = "utf-8") -> None:
    dir_part = os.path.dirname(path)
    if dir_part:
        ensure_dir(dir_part)
    with open(path, "w", encoding=encoding) as fh:
        fh.write(content)


def read_text(path: str, encoding: str = "utf-8") -> str:
    with open(path, "r", encoding=encoding) as fh:
        return fh.read()


def glob_files(pattern: str) -> list[str]:
    return glob.glob(pattern, recursive=True)
