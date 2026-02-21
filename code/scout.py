"""Scan repo for TODO/FIXME and generate draft task files."""

import os
import yaml
from datetime import datetime
from glob import glob

from code.config import TASKS_DIR
from code.task_id import next_task_id


def scan_repo_and_generate_drafts():
    """Find TODO/FIXME in *.py and write one draft task file per match."""
    drafts = []
    for py_file in glob("*.py"):
        with open(py_file, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if "TODO" in line or "FIXME" in line:
                    task_id = next_task_id()
                    slug = f"{os.path.splitext(py_file)[0]}-line{i + 1}"
                    draft = {
                        "task_id": task_id,
                        "title": f"Address {line.strip()}",
                        "status": "draft",
                        "priority_score": 70,
                        "priority_rank": None,
                        "priority_reason": "TODO found in code",
                        "created_at": datetime.utcnow().isoformat() + "Z",
                        "source": "task-scout",
                        "allowed_files": [py_file],
                        "estimated_effort": "M",
                        "risk_level": "medium",
                    }
                    draft_path = os.path.join(TASKS_DIR, f"{task_id}_{slug}_draft.md")
                    with open(draft_path, "w", encoding="utf-8") as f_out:
                        yaml.dump(draft, f_out, default_flow_style=False)
                    drafts.append(draft)
    return drafts
