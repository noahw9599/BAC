# Task Scout Executor Reference

## Prerequisite

- Install `PyYAML`: `pip install pyyaml`

## Task schema

Tasks are stored as YAML in `.md` files under `tasks/`.

| Field | Type | Required | Notes |
|---|---|---|---|
| task_id | string | yes | Unique id such as `T001` |
| title | string | yes | Short task description |
| status | string | yes | `draft`, `in_progress`, `done` |
| priority_score | number | yes | Higher means more important |
| priority_rank | number or null | no | Filled by prioritizer |
| priority_reason | string | no | Score rationale |
| created_at | string | no | ISO UTC timestamp |
| source | string | no | Usually `task-scout` |
| allowed_files | list[string] | no | Paths allowed for edits |
| estimated_effort | string | no | `S`, `M`, `L` |
| risk_level | string | no | `low`, `medium`, `high` |

## Example task file

```yaml
task_id: T001
title: "Address TODO: refactor BAC formula"
status: draft
priority_score: 70
priority_rank: null
priority_reason: TODO found in code
created_at: "2026-02-21T12:00:00.000Z"
source: task-scout
allowed_files:
  - main.py
estimated_effort: M
risk_level: medium
```

## Default allowed files

When `allowed_files` is missing, restrict edits to:

- `main.py`
- `bac_calculations.py`
- `drinks.py`

## Behavior summary

- Scout: read `*.py` in repo root, find `TODO` and `FIXME`, write one draft per match.
- Prioritize: load `tasks/*.md`, sort by `priority_score` descending, assign rank, write `tasks/PRIORITY.md`.
- Execute: load one task file, implement minimal patch, set `status: done`, and save.
