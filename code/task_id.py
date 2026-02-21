"""Generate unique task IDs (T001, T002, ...) from existing task files."""

import os
from glob import glob

from code.config import TASKS_DIR


def next_task_id():
    """Next id T001, T002, ... from existing task files."""
    os.makedirs(TASKS_DIR, exist_ok=True)
    existing = set()
    for path in glob(os.path.join(TASKS_DIR, "*.md")):
        if path.endswith("PRIORITY.md"):
            continue
        name = os.path.basename(path)
        if name.startswith("T") and "_" in name:
            try:
                existing.add(int(name[1:].split("_")[0]))
            except ValueError:
                pass
    n = 1
    while n in existing:
        n += 1
    return f"T{n:03d}"
