from __future__ import annotations

import shutil
from pathlib import Path


def execute_move(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source.replace(target)


def execute_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def rollback_move(target: Path, restore: Path) -> None:
    restore.parent.mkdir(parents=True, exist_ok=True)
    target.replace(restore)
