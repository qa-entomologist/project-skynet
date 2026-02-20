# Contributing to Project Skynet

## Hard Requirements

Every contributor (human or AI agent) **MUST** follow these rules. PRs and commits that violate them will be rejected.

### 1. Update CHANGELOG.md on Every Commit

**This is mandatory. No exceptions.**

Every commit must include an update to `CHANGELOG.md` under the `[Unreleased]` section. Use [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [Unreleased]

### Added
- Brief description of new feature or capability

### Changed
- Brief description of what changed in existing functionality

### Fixed
- Brief description of bug fix

### Removed
- Brief description of what was removed
```

Categories to use: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

**If your commit does not update CHANGELOG.md, it is incomplete.**

### 2. Pull Before Push

Always pull the latest code before pushing:

```bash
git stash        # if you have uncommitted changes
git pull --rebase
git stash pop    # if you stashed
```

Never force push to `main`.

### 3. Don't Break Imports

Run this before committing:

```bash
python3 -c "from src.agent import create_explorer_agent; print('OK')"
```

### 4. AI Agent Instructions

If you are an AI coding agent (Cursor, Copilot, etc.) assisting a contributor, you **MUST**:

1. **Update `CHANGELOG.md`** with every commit you create. Add entries under `[Unreleased]`.
2. **Pull latest code** (`git pull --rebase`) before every push.
3. **Verify imports** pass after your changes.
4. **Do not** modify `.env` or commit secrets.
5. **Do not** force push or rewrite history on `main`.

These are non-negotiable. Failing to follow them creates merge conflicts and breaks the team's workflow.

## Project Structure

```
├── src/                    # Web Cartographer QA agent (core)
│   ├── agent.py            # Strands Agent + tools + system prompt
│   ├── _pw_helper.py       # Playwright subprocess
│   ├── browser_manager.py  # Browser IPC wrapper
│   ├── graph_store.py      # Neo4j + in-memory graph
│   └── config.py           # Configuration
├── agent/                  # Release Revert Risk Advisor
├── server/                 # Flask API
├── ui/                     # React dashboard
├── web/                    # Graph visualization
├── run.py                  # CLI entry point
├── CHANGELOG.md            # ← UPDATE THIS ON EVERY COMMIT
└── CONTRIBUTING.md         # This file
```

## Running Tests

```bash
# Verify imports
python3 -c "from src.agent import create_explorer_agent; print('OK')"

# Quick smoke test
python3 run.py https://www.example.com --max-depth 1 --max-pages 3 --no-datadog

# Full exploration
python3 run.py https://books.toscrape.com --max-depth 3 --max-pages 15 --headed --no-datadog
```

## Commit Message Format

```
<short summary of change>

- Bullet point details of what was added/changed/fixed
```
