# Task workflow (modular)

Run from **project root** (`bac_tracker_web`):

```bash
python -m code scout
python -m code prioritize
python -m code execute tasks/T001_main-py-line42_draft.md
```

| File | Role |
|------|------|
| `config.py` | `TASKS_DIR`, `ALLOWED_FILES` |
| `task_id.py` | `next_task_id()` |
| `scout.py` | `scan_repo_and_generate_drafts()` |
| `prioritizer.py` | `prioritize_tasks()` |
| `executor.py` | `implement_task(task_file)` |
| `main.py` | CLI entrypoint |

Requires: `PyYAML` (`pip install pyyaml`).
