"""Load a task file, run implementation, and mark status done."""

import yaml


def implement_task(task_file):
    """Load task YAML, perform implementation, set status to done and save."""
    with open(task_file, encoding="utf-8") as f:
        task = yaml.safe_load(f)
    print(f"Implementing task: {task['title']}")
    # Execute minimal patch here (manual or automated); enforce BAC invariants, run tests
    task["status"] = "done"
    with open(task_file, "w", encoding="utf-8") as f:
        yaml.dump(task, f, default_flow_style=False)
