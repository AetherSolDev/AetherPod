# Created: 2026-07-21
# Last Edited: 2026-07-31 13:08 CT (America/Chicago)
# Path: project_kit/new_project.md
# Purpose: New project initialization checklist. Use ONCE at project start.

# New Project Setup Checklist

## 0. Scaffold (recommended)

One command copies the kit and replaces every placeholder:

```bash
python /path/to/project_kit/scaffold.py my_project
# creates ./my_project/ fully bootstrapped
```

Skip to section 3 — `scaffold.py` handles sections 1–2 for you.

## 1. Repository Initialization (manual alternative)

- [ ] Create project directory
- [ ] Initialize git: `git init`
- [ ] Create `.gitignore` (copy from templates/.gitignore)
- [ ] Create `.repomixignore` (copy from templates/.repomixignore)
- [ ] Create initial commit: `git add . && git commit -m "init: initial project structure"`
- [ ] (Optional) Create remote repo and push

## 2. Copy Template Structure (manual alternative)

```bash
# Copy the template system into your new project
cp -r /path/to/templates/AGENTS.md ./AGENTS.md
cp -r /path/to/templates/instructions/ ./instructions/
cp -r /path/to/templates/docs/ ./docs/
cp -r /path/to/templates/scripts/ ./scripts/
```

- [ ] AGENTS.md — master guide copied and customized
- [ ] instructions/ — prompt templates copied
- [ ] docs/ — user guide and doc skeletons copied
- [ ] scripts/ — utility scripts copied
- [ ] project_audit/ — audit toolkit (self-contained, ships with the project)

## 3. Customize AGENTS.md

- [ ] Verify no `{project_id}` placeholders remain (scaffold.py replaces them)
- [ ] Search for any remaining hardcoded paths and replace with `$HOME/projects/{project_id}/` convention
- [ ] Update critical file list to match your project
- [ ] Update Database Schema section if applicable
- [ ] Update High Cost Alert timezone if different from CT
- [ ] Remove or update Critical Rules that are project-specific

## 3a. License (DECIDE BEFORE FIRST PUBLIC PUSH)

- [ ] Read `instructions/LICENSING.md` — default is **MIT + EULA**, flip to **GPL3** only if intended
- [ ] `LICENSE` (MIT) + `EULA.md` are included by default — customize the EULA for this app
- [ ] If this app is GPL3: replace `LICENSE` with GPL3 text and delete `EULA.md` NOW, before publishing
- [ ] Never copy GPL3 code into this kit or an MIT app (contaminates the MIT license)

## 4. Initialize Project Files

- [ ] Name your top-level package directory `{project_id}/` (not `src/`) — e.g., `aethertime/` for AetherTime. This prevents namespace collisions with sibling projects
- [ ] Create `{project_id}/__main__.py` as the entry point (run with `python -m {project_id}`)
- [ ] Read `instructions/STRUCTURE.md` — the canonical layout, entry point, and import conventions
- [ ] Create `docs/sys/PLAN.md` with initial phases
- [ ] Create `docs/sys/TASKS.md` with initial tasks
- [ ] Create `docs/sys/CHANGELOG.md` with first entry
- [ ] Create `docs/sys/ARCHITECTURE.md` with your project structure
- [ ] Create `docs/sys/KNOWLEDGE.md` with architecture TL;DR, critical files, key decisions
- [ ] Create `docs/sys/{project_id}.mmd` for mermaid diagram
- [ ] Create `docs/sys/BUGS.md` (empty tracker)
- [ ] Update `docs/sys/COST.md` with your pricing details
- [ ] Update `docs/sys/Model_Pricing_Reference.txt` with current rates
- [ ] Write `docs/USER_GUIDE.md` with features, installation, troubleshooting
- [ ] Build combined reference: `python scripts/build_reference.py`

## 5. Development Environment

- [ ] Install template tooling: `pip install -r requirements.txt` (only `mermaidx` if needed)
- [ ] Add your project-specific dependencies (e.g., `PySide6`, `flask`, `fastapi`) to `requirements.txt`
- [ ] Set up virtual environment: `python -m venv venv`
- [ ] Verify `.repomixignore` exists for AI context management
- [ ] Run initial lint/typecheck to establish baseline

## 6. Packaging & CLI

- [ ] Move `docs/` and `assets/` into `{project_id}/` so non-editable pip installs work
- [ ] Create `MANIFEST.in` for sdist inclusion (see `instructions/packaging.md`)
- [ ] Configure `pyproject.toml` with `package-data`, `data-files`, and `[project.scripts]` entry point (see `instructions/packaging.md`)
- [ ] Implement argument parsing in `{project_id}/__main__.py` with `--version`, `--debug`, `--upgrade`
- [ ] Create PyInstaller `.spec` file for standalone builds
- [ ] Test `pip install --user -e .` works outside a venv

## 7. First Commit

```bash
git add .
git commit -m "init: project scaffolding with template system"
```

## Post-Setup

After this checklist is complete, `templates/new_project.md` has served its purpose.
Refer to `AGENTS.md` and `instructions/` for ongoing development guidance.

### Session Resumption Protocol

When resuming after a gap (days/months):
1. Read `docs/sys/REFERENCE.md` or `docs/sys/REFERENCE.html` — full project overview
2. Read `docs/sys/KNOWLEDGE.md` — fastest context recovery
3. Read `AGENTS.md` for current rules
4. Read last 3 entries of `docs/sys/CHANGELOG.md` for recent changes
5. Only then read specific source files if needed

### Regenerate Reference

After any significant change to `docs/sys/`:
```bash
python scripts/build_reference.py
```
