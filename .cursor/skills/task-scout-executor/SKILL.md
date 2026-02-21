---
name: task-scout-executor
description: Scan a repository for TODO/FIXME comments and convert them into draft task files, prioritize task files by score into tasks/PRIORITY.md, and execute a selected task file while enforcing scoped edits. Use when the user asks to scout tasks, prioritize backlog items, run or implement a task from tasks/*.md, or maintain this lightweight task workflow.
---

# Task Scout Executor

Use this skill to run a lightweight task loop in a repository: scout tasks from code comments, prioritize task files, and execute one task.

## Prerequisites

Install dependency before running the scripts:

```bash
pip install pyyaml
```

## Run Workflow

Run from repository root.

```bash
python .cursor/skills/task-scout-executor/scripts/task_workflow.py scout
python .cursor/skills/task-scout-executor/scripts/task_workflow.py prioritize
python .cursor/skills/task-scout-executor/scripts/task_workflow.py execute tasks/T001_main-py-line42_draft.md
```

## Use Bundled Scripts

- Use `scripts/task_workflow.py` as the entrypoint.
- Use `scripts/scout.py` for draft generation.
- Use `scripts/prioritizer.py` for rank generation and `tasks/PRIORITY.md` output.
- Use `scripts/executor.py` to load one task file, apply implementation, and set `status: done`.
- Use `scripts/task_id.py` to generate unique `T###` ids.
- Use `scripts/config.py` for defaults like `TASKS_DIR` and `ALLOWED_FILES`.

## Execution Rules

- Restrict edits to `allowed_files` in the task when present.
- If a task omits `allowed_files`, default to `main.py`, `bac_calculations.py`, and `drinks.py`.
- Apply minimal patches that satisfy the task intent.
- Preserve project invariants and run relevant tests before setting `status: done`.
- Avoid unrelated refactors while executing a task.

For schema details and examples, read [reference.md](reference.md).
