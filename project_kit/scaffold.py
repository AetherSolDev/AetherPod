#!/usr/bin/env python3
# Created: 2026-07-31
# Last Edited: 2026-07-31 12:33 CT (America/Chicago)
# Path: project_kit/scaffold.py
# Purpose: Scaffold a new project from this kit — copy the template and replace placeholders.

# Usage:
#   python scaffold.py my_project               # create ./my_project/
#   python scaffold.py my_project /path/to       # create /path/to/my_project/

import argparse
import shutil
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent
SKIP = {"scaffold.py", "__pycache__", ".git", ".gitignore_1", "venv", ".venv"}

PLACEHOLDERS = ("{project_id}", "{project_name}", "{Project_Root}")
TEXT_EXTS = {
    ".py", ".md", ".txt", ".sh", ".toml", ".gitignore", ".repomixignore",
    ".mmd", ".json", ".yml", ".yaml", ".cfg", ".ini",
}


def _is_text(path: Path) -> bool:
    return path.suffix in TEXT_EXTS or path.name in (".gitignore", ".repomixignore")


def _copy(src: Path, dst: Path) -> None:
    for item in sorted(src.iterdir()):
        if item.name in SKIP:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(item, target)


def _rewrite(root: Path, name: str) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        new_name = path.name
        for placeholder in PLACEHOLDERS:
            new_name = new_name.replace(placeholder, name)
        if new_name != path.name:
            path = path.rename(path.with_name(new_name))
        if _is_text(path):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            changed = False
            for placeholder in PLACEHOLDERS:
                if placeholder in text:
                    text = text.replace(placeholder, name)
                    changed = True
            if changed:
                path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold a new project from this kit (replaces {project_id} placeholders)."
    )
    parser.add_argument("name", help="New project name (also the package name), e.g. my_app")
    parser.add_argument("parent", nargs="?", default=".", help="Parent directory for the new project (default: current dir)")
    args = parser.parse_args()

    name = args.name.strip().lower().replace(" ", "_")
    if not name:
        sys.exit("Project name cannot be empty")

    target = Path(args.parent).expanduser().resolve() / name
    if target.exists() and any(target.iterdir()):
        sys.exit(f"Target already exists and is not empty: {target}")

    target.mkdir(parents=True, exist_ok=True)
    print(f"📁 Scaffolding project '{name}' into {target}")
    _copy(KIT_ROOT, target)
    _rewrite(target, name)

    print(f"✅ Created {target}")
    print("   - AGENTS.md, instructions/, docs/, scripts/, project_audit/")
    print(f"   - {name}.mmd / {name}.txt in docs/sys/ (renamed from placeholders)")
    print("\nNext steps:")
    print(f"   1. cd {target}")
    print(f"   2. Paste project_kit/prompt.md (now {target}/prompt.md) to the agent")
    print(f"   3. Fine-tune {target}/AGENTS.md for this specific app")
    print("   4. git init && git add . && git commit -m 'init: project scaffolding'")


if __name__ == "__main__":
    main()
