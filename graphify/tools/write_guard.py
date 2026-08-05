"""Single write boundary for Lamha Graphify tooling."""

from __future__ import annotations

import csv
import io
import json
import stat
from pathlib import Path
from typing import Iterable, Mapping


GRAPHIFY_ROOT = Path(__file__).resolve().parents[1]


def _is_reparse(path: Path) -> bool:
    try:
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, FileNotFoundError, OSError):
        return path.is_symlink()


def guard_write_path(path: Path | str) -> Path:
    """Reject traversal, absolute escape, symlinks, junctions, and reparse escape."""
    candidate = Path(path)
    if ".." in candidate.parts:
        raise ValueError(f"parent traversal rejected: {candidate}")
    root = GRAPHIFY_ROOT.resolve(strict=True)
    resolved = candidate.resolve(strict=False)
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"write outside Graphify rejected: {resolved}") from error
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.exists() and _is_reparse(cursor):
            raise ValueError(f"reparse-point write rejected: {cursor}")
    return resolved


def _prepare(path: Path | str) -> Path:
    target = guard_write_path(path)
    missing: list[Path] = []
    cursor = target.parent
    while cursor != GRAPHIFY_ROOT and not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    if _is_reparse(cursor):
        raise ValueError(f"reparse-point parent rejected: {cursor}")
    for directory in reversed(missing):
        guard_write_path(directory).mkdir()
    return target


def write_bytes(path: Path | str, data: bytes) -> None:
    _prepare(path).write_bytes(data)


def write_text(path: Path | str, text: str) -> None:
    _prepare(path).write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path | str, value: object) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2))


def write_csv(path: Path | str, rows: Iterable[Mapping[str, object]], fields: list[str]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write_text(path, stream.getvalue())


def remove_file(path: Path | str) -> None:
    target = guard_write_path(path)
    if target.exists():
        if target.is_dir():
            raise ValueError(f"refusing directory removal through file guard: {target}")
        target.unlink()
