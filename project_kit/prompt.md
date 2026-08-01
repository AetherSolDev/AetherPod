# Created: 2026-07-27
# Last Edited: 2026-07-31 13:08 CT (America/Chicago)
# Path: prompt.md
# Purpose: Copy-paste prompt for AI to scaffold a new project from this template.

---

I'm starting a new project called `{project_id}`. Follow the instructions below precisely.

## 1. Read the Template System
Read these files in order before doing anything:
- `AGENTS.md` — master rules and conventions
- `new_project.md` — setup checklist
- `instructions/plan_prompt.md` — how to write plans
- `instructions/tasks_example.md` — how to write tasks
- `instructions/memory.md` — session continuity rules

## 2. Scaffold the Project

The scaffold has already been applied: `scaffold.py` copied the kit into this
project and replaced every `{project_id}` placeholder. Verify that is true
(grep for `{project_id}` — there should be zero matches).

If the project was NOT scaffolded (no `prompt.md`, no `project_audit/`), run it
once from the kit location before continuing:

```bash
python /path/to/project_kit/scaffold.py {project_id}
```

Then complete `new_project.md` for anything not yet done (git init, venv).

## 3. Customize

- Confirm no `{project_id}` placeholders remain anywhere
- Update AGENTS.md: Working Directory, Critical Files, Database Schema
- Remove the "Final Phase" checklist section from AGENTS.md (only add it back when the project is feature-complete)

## 3a. License — decide BEFORE the first public push

- Read `instructions/LICENSING.md`
- Default is `LICENSE` (MIT) + `EULA.md` (commercial). Customize the EULA for this app.
- If this app is meant to be GPL3, swap `LICENSE` to GPL3 and delete `EULA.md` now.
- Never copy GPL3 code into the kit or into an MIT app.

## 4. Initialize Project Docs
Create the following in `docs/sys/`:
- `PLAN.md` — high-level phases and milestones
- `TASKS.md` — prioritized task breakdown with acceptance criteria
- `ARCHITECTURE.md` — directory structure and key components
- `KNOWLEDGE.md` — architecture TL;DR, critical files, gotchas
- `CHANGELOG.md` — first entry describing the initial scaffold
- `BUGS.md` — empty tracker with header only
- `{project_id}.mmd` — mermaid diagram placeholder
- `COST.md` — copy pricing from template cost_example.md
- `Model_Pricing_Reference.txt` — current rates

## 5. Session Keywords
Use these keywords for session continuity:
- **`recall`** — Read KNOWLEDGE.md, last 3 CHANGELOG entries, git log. Resume context.
- **`save session`** — Update KNOWLEDGE.md Session History, CHANGELOG.md, commit all changes.

## 6. First Commit
Run these in order:
```bash
git add .
git commit -m "init: project scaffolding with template system"
```

## 7. Verify
- Run `python scripts/build_reference.py` to generate combined reference
- Confirm AGENTS.md has no remaining `{project_id}` placeholders (grep)
- Confirm all docs open correctly

When done, use `recall` to summarize what was created.
