"""Load task files, sort by priority_score, and write PRIORITY.md."""

import os
from datetime import datetime
from glob import glob

import yaml

from config import TASKS_DIR


def prioritize_tasks():
    """Sort tasks by priority_score descending and update tasks/PRIORITY.md."""
    os.makedirs(TASKS_DIR, exist_ok=True)
    task_files = [
        p for p in glob(os.path.join(TASKS_DIR, "*.md")) if not p.endswith("PRIORITY.md")
    ]
    tasks = []
    for task_file in task_files:
        try:
            with open(task_file, encoding="utf-8") as f:
                task = yaml.safe_load(f)
                if task:
                    tasks.append(task)
        except Exception:
            pass

    tasks.sort(key=lambda task: task.get("priority_score", 0), reverse=True)
    for idx, task in enumerate(tasks, start=1):
        task["priority_rank"] = idx

    with open(os.path.join(TASKS_DIR, "PRIORITY.md"), "w", encoding="utf-8") as f:
        f.write("# Task Priority\n")
        f.write(f"Updated: {datetime.utcnow().isoformat()}Z\n\n")
        for task in tasks:
            f.write(f"{task['priority_rank']}. {task['title']} - Score: {task['priority_score']}\n")

    return tasks
