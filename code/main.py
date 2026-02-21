"""CLI entrypoint: scout | prioritize | execute <task_file>."""

import os
import sys

from code.scout import scan_repo_and_generate_drafts
from code.prioritizer import prioritize_tasks
from code.executor import implement_task


def main():
    cmd = (sys.argv[1:] or [""])[0].lower()
    if cmd == "scout":
        drafts = scan_repo_and_generate_drafts()
        print(f"Created {len(drafts)} draft(s).")
    elif cmd == "prioritize":
        prioritize_tasks()
        print("PRIORITY.md updated.")
    elif cmd == "execute":
        path = (sys.argv[2:] or [""])[0]
        if not path or not os.path.isfile(path):
            print("Usage: python -m code execute <task_file.md>", file=sys.stderr)
            sys.exit(1)
        implement_task(path)
    else:
        print(
            "Usage: python -m code scout | prioritize | execute <task_file.md>",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
