# Created: 2026-07-27
# Last Edited: 2026-07-27 00:45 CT (America/Chicago)
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
Execute the steps from `new_project.md`:
- Create the project directory at `$HOME/projects/{project_id}/`
- Copy all template files: AGENTS.md, instructions/, docs/, scripts/
- Initialize git
- Create `.gitignore` and `.repomixignore`

## 3. Customize
- Replace every `{project_id}` placeholder with the actual project name
- Replace `{Project Name}` in PLAN.md, TASKS.md, ARCHITECTURE.md
- Update AGENTS.md: Working Directory, Critical Files, Database Schema
- Remove the "Final Phase" checklist section from AGENTS.md (only add it back when the project is feature-complete)

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
- Confirm AGENTS.md has no remaining `{project_id}` placeholders
- Confirm all docs open correctly

When done, use `recall` to summarize what was created.
