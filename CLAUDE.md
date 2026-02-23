# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

```
src/surogate_agent/   Python package — agent, CLI, REST API
src/frontend/         Frontend extension — see src/frontend/CLAUDE.md
tests/                Test suite for the Python package (109 tests, all mocked)
docs/                 CLI and API reference docs
```

## Commands

```bash
# Install for development (system Python 3.9 works for tests via --no-deps)
pip install -e . --no-deps
pip install pyyaml pytest pytest-asyncio pytest-mock

# Install with full dependencies (requires Python >=3.12)
pip install -e ".[anthropic]"   # Claude models
pip install -e ".[openai]"      # OpenAI models
pip install -e ".[dev]"         # + testing tools (pytest, ruff, mypy)

# Run all tests (no LLM required — all mocked)
pytest tests/ -v

# Run a single test file
pytest tests/test_skill_loader.py -v

# Run a single test by name
pytest tests/test_agent.py::TestCreateAgent::test_developer_gets_meta_skill -v

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

The preferred workflow uses `uv`: `uv add <pkg>` and `uv run pytest`.

Set `SUROGATE_MODEL` env var to override the default model (`claude-sonnet-4-6`).

## Architecture

`surogate-agent` wraps [`deepagents`](https://github.com/langchain-ai/deepagents) (a LangGraph runtime) with role-based skill gating. The public API is `create_agent()` which returns a `RoleGuardAgent`.

### Role system

Two roles (`Role.DEVELOPER` / `Role.USER`) control which skills are loaded and what system-prompt context the agent receives. `RoleContext` carries `role`, `user_id`, `session_id`, and `metadata`; it is injected into every LangGraph call via `config["configurable"]` in `RoleGuardAgent._merge_config()`.

### Skill loading pipeline

Skills are directories containing a `SKILL.md` with YAML frontmatter (`name`, `description`, optional `role-restriction`, `allowed-tools`, `version`).

1. `SkillLoader` (per directory) — scans subdirs, parses frontmatter, normalises malformed LLM-generated SKILL.md files (BOM, leading blanks, headings before `---`, missing trailing newline). Silently rewrites the file on disk when normalisation was needed.
2. `SkillRegistry` — aggregates loaders, deduplicates by name (user skills shadow builtins), and filters by role via `paths_for_role()`.
3. `create_agent()` assembles a `skill_sources` list of parent directories and passes it to `create_deep_agent(skills=...)`. Role filtering is achieved purely by controlling which source directories appear in that list:
   - `DEVELOPER` → `builtin/` (contains the meta-skill) + `user_skills_dir` + `config.skills_dirs`
   - `USER` → `user_skills_dir` + `config.skills_dirs` (no builtin)

### Backend selection (shell execution)

`create_agent()` picks between `FilesystemBackend` (default, file ops only) and `LocalShellBackend` (adds `execute` tool) based on:
- `AgentConfig.allow_execute = True` — explicit developer consent, or
- Auto-detected: any user-visible skill declares `execute` in its `allowed-tools` frontmatter.

### Session / workspace isolation

`SessionManager` manages per-session workspace directories under `sessions/<session-id>/`. Workspace directories are created lazily on first file write. Developer sessions use a separate `workspace/` scratch area (not the session dir) for drafting skills in progress.

### Key paths

| Path | Purpose |
|------|---------|
| `src/surogate_agent/core/agent.py` | `create_agent()` factory — main entry point |
| `src/surogate_agent/core/roles.py` | `Role` enum, `RoleContext` |
| `src/surogate_agent/core/config.py` | `AgentConfig`; `_DEFAULT_SKILLS_DIR` constant |
| `src/surogate_agent/core/session.py` | `Session`, `SessionManager` |
| `src/surogate_agent/skills/loader.py` | `SkillLoader`, `SkillInfo`, `_normalize_skill_md` |
| `src/surogate_agent/skills/registry.py` | `SkillRegistry` |
| `src/surogate_agent/skills/builtin/` | Built-in skills (currently: `meta/` — the skill-developer meta-skill) |
| `src/surogate_agent/middleware/role_guard.py` | `RoleGuardAgent` wrapper |
| `src/surogate_agent/cli/main.py` | Typer CLI entry point (`surogate-agent` command) |

### CLI commands

```
surogate-agent user             # Start USER-role chat
surogate-agent developer        # Start DEVELOPER-role chat (meta-skill active)
surogate-agent chat             # Generic chat (--role developer|user)
surogate-agent skills list|show|validate|delete
surogate-agent session ...
surogate-agent workspace ...
surogate-agent serve            # Start FastAPI HTTP server (requires [api] extra)
```

### Model string conventions

`_build_llm()` in `agent.py` dispatches on model string prefix: `claude*` → `ChatAnthropic`, `gpt*`/`o1*`/`o3*` → `ChatOpenAI`. Any other prefix raises `ValueError`.

### Skill format

```markdown
---
name: my-skill
description: One-liner, max 1024 chars
role-restriction: developer   # omit for all roles
version: 0.1.0
allowed-tools: read_file write_file execute   # space-delimited string (preferred) or YAML list
---

Natural-language instructions the agent follows when this skill is active.
```

`allowed-tools: execute` in a user-visible skill automatically activates `LocalShellBackend` for that session.

## REST API

`surogate-agent` ships a FastAPI layer under `src/surogate_agent/api/`.

### Install

```bash
pip install -e ".[api]"    # fastapi, sse-starlette, uvicorn, python-multipart
```

### Start the server

```bash
surogate-agent serve                     # 127.0.0.1:8000
surogate-agent serve --host 0.0.0.0 --port 9000
surogate-agent-api                       # standalone entry point
```

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SUROGATE_SKILLS_DIR` | `./skills` | User skills root |
| `SUROGATE_SESSIONS_DIR` | `./sessions` | Session workspaces root |
| `SUROGATE_WORKSPACE_DIR` | `./workspace` | Dev scratch workspace root |
| `SUROGATE_MODEL` | `claude-sonnet-4-6` | Default LLM model |

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | SSE stream (`text/event-stream`) — chat with the agent |
| `GET` | `/skills` | List skills (`?role=all\|developer\|user`) |
| `GET/POST/DELETE` | `/skills/{name}` | Get / create / delete a skill |
| `POST` | `/skills/{name}/validate` | Validate a skill |
| `GET/POST/DELETE` | `/skills/{name}/files/{file}` | Helper file CRUD |
| `GET/DELETE` | `/sessions/{id}` | Session info / delete |
| `GET/POST/DELETE` | `/sessions/{id}/files/{file}` | Session file CRUD |
| `GET/DELETE` | `/workspace/{skill}` | Workspace info / delete |
| `GET/POST/DELETE` | `/workspace/{skill}/files/{file}` | Workspace file CRUD |

### Key API files

| Path | Purpose |
|------|---------|
| `src/surogate_agent/api/app.py` | `create_app()` factory — wires routers + CORS |
| `src/surogate_agent/api/deps.py` | `ServerSettings` dataclass + `Depends` injection |
| `src/surogate_agent/api/models.py` | All Pydantic request/response models |
| `src/surogate_agent/api/server.py` | `main()` uvicorn entry point |
| `src/surogate_agent/api/routers/chat.py` | SSE chat endpoint |
| `src/surogate_agent/api/routers/skills.py` | Skills CRUD |
| `src/surogate_agent/api/routers/sessions.py` | Sessions CRUD |
| `src/surogate_agent/api/routers/workspace.py` | Workspace CRUD |
| `tests/test_api.py` | 46 API tests (all mocked — no LLM required) |
