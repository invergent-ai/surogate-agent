<p align="center">
  <img src="./assets/logo.png" alt="Surogate Agent" width="480" />
</p>

<h1 align="center">Conversational skill development for enterprise AI agents</h1>

<p align="center">
  <em>Role-aware deep agent framework with a meta-skill for authoring new skills through conversation</em>
</p>

<p align="center">
  <a href="https://docs.surogate.ai"><strong>Docs</strong></a>
  ·
  <a href="docs/cli.md"><strong>CLI Reference</strong></a>
  ·
  <a href="docs/api.md"><strong>API Reference</strong></a>
  ·
  <a href="https://github.com/invergent-ai/surogate"><strong>Surogate</strong></a>
  ·
  <a href="https://github.com/invergent-ai/surogate-studio"><strong>Surogate Studio</strong></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/surogate-agent/"><img src="https://img.shields.io/pypi/v/surogate-agent?color=%23a855f7&label=pypi" alt="PyPI version" /></a>
  <a href="https://pypi.org/project/surogate-agent/"><img src="https://img.shields.io/pypi/pyversions/surogate-agent?color=%23a855f7" alt="Python versions" /></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-%23a855f7" alt="License" /></a>
</p>

---

## What is Surogate Agent?

**Surogate Agent** is an open-source Python framework for building **role-aware AI agents** with a unique skill-authoring workflow — no manual file editing required.

It wraps [LangChain's deepagents](https://github.com/langchain-ai/deepagents) (LangGraph runtime) with two core ideas:

- **Role system** — `DEVELOPER` and `USER` roles control which skills are loaded, what tools are available, and what context the agent receives. The same agent codebase serves both skill authors and end users.
- **Meta-skill** — a built-in skill loaded exclusively for `DEVELOPER` sessions. It instructs the agent to create, edit, and validate new skills **through conversation alone**. No IDE, no YAML wrangling.

```
Developer: "Create a skill that summarises Slack threads"

Agent (DEVELOPER role, meta-skill active):
  → Asks clarifying questions about Slack API access and output format
  → Writes ./skills/slack-summariser/SKILL.md with full instructions
  → Reports: "Skill created — activate with surogate-agent user"
```

Surogate Agent is the engine behind the conversational skill-development workflow in [Surogate Studio](https://github.com/invergent-ai/surogate-studio).

---

## Key Features

- **Two-role architecture** — `DEVELOPER` and `USER` roles control skill visibility and tool access at the framework level; no per-request configuration needed.
- **Meta-skill for zero-code skill authoring** — developers create and iterate on skills purely through conversation.
- **Skill format** — plain Markdown with YAML frontmatter (`SKILL.md`). Skills are directories; helper files (prompts, schemas, templates) live alongside the definition.
- **Automatic shell backend selection** — if any installed skill declares `execute` in its `allowed-tools`, `LocalShellBackend` is activated automatically; no explicit opt-in required.
- **Session isolation** — each user chat gets a private workspace directory. Files written by the agent are accessible but sandboxed per session.
- **Developer workspace** — a persistent scratch area (`workspace/<skill>/`) for drafts and test inputs that never bleeds into shipped skill definitions.
- **Persistent conversation history** — per-skill SQLite checkpointing lets developers resume exactly where they left off across sessions.
- **Multi-model support** — `claude-*` → Anthropic, `gpt-*` / `o1-*` / `o3-*` → OpenAI; swap with one env var.
- **REST API with SSE streaming** — `POST /chat` streams agent output as Server-Sent Events. Full CRUD for skills, sessions, and workspaces over HTTP.
- **Interactive CLI** — 25 commands across four command groups (`chat`, `skills`, `session`, `workspace`) with rich terminal output.
- **Fully mocked test suite** — 109 tests, no LLM or network required.

---

## Quickstart

### Install

```bash
pip install "surogate-agent[anthropic]"   # Claude models
pip install "surogate-agent[openai]"      # OpenAI models
pip install "surogate-agent[api]"         # + FastAPI REST server
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
```

### Start a developer session

```bash
surogate-agent developer
```

```
You (Alt+Enter to send)
> Create a skill that pulls the latest Jira tickets assigned to me and
  summarises them as a bullet list

Agent ● skill-developer
  ▶ write_file (path='skills/jira-summariser/SKILL.md', ...)
  ✓ write_file: ok

  Agent
  I've created the **jira-summariser** skill at `skills/jira-summariser/SKILL.md`.
  Activate it in a user session with `surogate-agent user`.
```

### Start a user session

```bash
surogate-agent user
```

### Resume a skill-development session

```bash
surogate-agent developer --skill jira-summariser
# Picks up the conversation exactly where you left off
```

### Python API

```python
from surogate_agent import create_agent, Role, AgentConfig
from pathlib import Path

config = AgentConfig(
    model="claude-sonnet-4-6",
    user_skills_dir=Path("./skills"),
)

# Developer session — meta-skill loaded automatically
agent = create_agent(role=Role.DEVELOPER, config=config)
result = agent.invoke({
    "messages": [{"role": "user", "content": "Create a Jira summariser skill"}]
})

# User session — only non-restricted skills visible
agent = create_agent(role=Role.USER, config=config)
```

### REST API

```bash
pip install "surogate-agent[api]"
surogate-agent serve               # starts on http://127.0.0.1:8000
```

```bash
# Stream a chat response via SSE
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Summarise my Jira tickets", "role": "user"}' \
  --no-buffer

# event: text
# data: {"text": "Here are your latest tickets..."}
# event: done
# data: {"session_id": "20260101-120000-abc123", "files": []}
```

### Run with Docker

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -p 8000:8000 \
  -v $(pwd)/skills:/data/skills \
  -v $(pwd)/sessions:/data/sessions \
  -v $(pwd)/workspace:/data/workspace \
  ghcr.io/invergent-ai/surogate-agent:latest
```

API available at `http://localhost:8000` · Swagger UI at `http://localhost:8000/docs`

---

## End-to-end example with Docker

This walkthrough shows the full developer → user lifecycle using the published Docker image and an OpenAI key.

### 1 — Create a local skills directory

```bash
mkdir -p skills sessions workspace
```

### 2 — Developer session: author a new skill

```bash
docker run -it --rm \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e SUROGATE_MODEL=gpt-5.2 \
  -v $(pwd)/skills:/data/skills \
  -v $(pwd)/workspace:/data/workspace \
  ghcr.io/invergent-ai/surogate-agent:latest \
  surogate-agent developer
```

```
You (Alt+Enter to send)
> Create a skill called "tech-joke" that tells a single short tech joke when asked.

Agent ● skill-developer
  ▶ write_file (path='skills/tech-joke/SKILL.md')
  ✓ write_file: ok

  I've created the **tech-joke** skill at `skills/tech-joke/SKILL.md`.
  It will respond to any request for a joke with a short, original tech-themed joke.
  Test it with `surogate-agent user`.
```

> Press `Ctrl+D` or type `/quit` to exit.

The skill file is now on your host at `./skills/tech-joke/SKILL.md` (written through the bind mount).

### 3 — User session: use the skill

```bash
docker run -it --rm \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e SUROGATE_MODEL=gpt-5.2 \
  -v $(pwd)/skills:/data/skills \
  -v $(pwd)/sessions:/data/sessions \
  ghcr.io/invergent-ai/surogate-agent:latest \
  surogate-agent user
```

```
You (Alt+Enter to send)
> Tell me a joke

Agent ● tech-joke
  Why do Java developers wear glasses?
  Because they don't C#.
```

The `tech-joke` skill is automatically discovered from `/data/skills` and made available to the user-role agent. No restart or configuration change needed — just share the same `skills/` volume.

---

## Skill format

A skill is a directory containing a `SKILL.md` file with YAML frontmatter:

```
my-skill/
├── SKILL.md          ← required; defines the skill
├── prompt.md         ← optional helper file
└── output-schema.json
```

```markdown
---
name: jira-summariser
description: Pulls Jira tickets assigned to the current user and summarises them
role-restriction: null        # omit = available to all roles
version: 0.1.0
allowed-tools: read_file execute
---

# Jira Summariser

When this skill is active:
1. Use `execute` to call the Jira REST API…
2. Format the result as a bullet list…
```

The meta-skill guides the agent to produce exactly this format during `DEVELOPER` sessions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Interfaces                           │
│   CLI (Typer)            REST API (FastAPI + SSE)           │
│   surogate-agent …       POST /chat  GET/POST /skills …     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    create_agent()                           │
│                                                             │
│  Role resolution → Skill source selection → Backend pick    │
│  ┌─────────────┐  ┌──────────────────────┐  ┌───────────┐  │
│  │ RoleContext │  │  SkillRegistry       │  │ LLM build │  │
│  │ DEVELOPER   │  │  builtin/ (meta)     │  │ claude-*  │  │
│  │ USER        │  │  user skills_dir/    │  │ gpt-*     │  │
│  └─────────────┘  └──────────────────────┘  └───────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│              deepagents  (LangGraph runtime)                │
│   FilesystemBackend  |  LocalShellBackend (execute tool)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                   RoleGuardAgent                            │
│   Injects RoleContext into every invoke/stream call         │
│   Session & workspace path isolation                        │
│   SQLite checkpointing (per-skill history)                  │
└─────────────────────────────────────────────────────────────┘
```

### Role system

`Role.DEVELOPER` loads the **meta-skill** (`builtin/skill-developer/`) alongside any user skills. `Role.USER` receives only user-authored skills without a `role-restriction: developer` tag. `RoleContext` (`role`, `user_id`, `session_id`, `metadata`) travels through every LangGraph call via `config["configurable"]`.

### Skill loading pipeline

1. **`SkillLoader`** — scans a root directory for subdirs containing `SKILL.md`; normalises malformed LLM-generated files (BOM, missing frontmatter delimiters, stray headings) in place.
2. **`SkillRegistry`** — aggregates multiple loaders, deduplicates by name (user skills shadow builtins), and filters by role via `paths_for_role()`.
3. **`create_agent()`** — assembles `skill_sources` (parent dirs for deepagents' `SkillsMiddleware`) by controlling which directories are included for each role.

### Backend selection

| Condition | Backend |
|-----------|---------|
| `AgentConfig.allow_execute = True` | `LocalShellBackend` — file ops + `execute` |
| Any user skill declares `execute` in `allowed-tools` | `LocalShellBackend` — auto-detected |
| Default | `FilesystemBackend` — file ops only |

### File isolation

```
./skills/          ← skill definitions (ship with the skill)
./workspace/       ← developer scratch area (never shipped)
  └── <skill>/
./sessions/        ← per-user-chat workspaces
  └── <session-id>/
```

---

## Project structure

```
src/surogate_agent/
├── core/
│   ├── agent.py          create_agent() factory
│   ├── config.py         AgentConfig
│   ├── roles.py          Role enum, RoleContext
│   └── session.py        Session, SessionManager
├── skills/
│   ├── loader.py         SkillLoader, SkillInfo, _normalize_skill_md
│   ├── registry.py       SkillRegistry
│   └── builtin/
│       └── skill-developer/
│           └── SKILL.md  ← the meta-skill
├── middleware/
│   └── role_guard.py     RoleGuardAgent wrapper
├── api/
│   ├── app.py            FastAPI create_app() factory
│   ├── deps.py           ServerSettings (env-var config)
│   ├── models.py         Pydantic request/response models
│   ├── server.py         uvicorn entry point
│   └── routers/
│       ├── chat.py       POST /chat  (SSE stream)
│       ├── skills.py     /skills CRUD
│       ├── sessions.py   /sessions CRUD
│       └── workspace.py  /workspace CRUD
└── cli/
    ├── main.py           Typer app entry point
    ├── chat.py           chat / user / developer / serve commands
    ├── skills.py         skills subcommands
    ├── session.py        session subcommands
    └── workspace.py      workspace subcommands
tests/
├── test_agent.py
├── test_roles.py
├── test_skill_loader.py
├── test_session.py
└── test_api.py           46 API tests
```

---

## Configuration

```python
from surogate_agent import AgentConfig
from pathlib import Path

config = AgentConfig(
    model="claude-sonnet-4-6",          # SUROGATE_MODEL env var
    user_skills_dir=Path("./skills"),   # where new skills are written
    skills_dirs=[Path("./shared")],     # extra directories to scan
    dev_workspace_dir=Path("./workspace"),
    sessions_dir=Path("./sessions"),
    allow_execute=False,                # True = LocalShellBackend
    max_iterations=50,
    system_prompt_suffix="",            # appended to every system prompt
)
```

**Environment variables:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `SUROGATE_MODEL` | `claude-sonnet-4-6` | Default LLM model |
| `SUROGATE_SKILLS_DIR` | `./skills` | User skills root (API server) |
| `SUROGATE_SESSIONS_DIR` | `./sessions` | Session workspaces root (API server) |
| `SUROGATE_WORKSPACE_DIR` | `./workspace` | Dev workspace root (API server) |

---

## Development

```bash
# Clone
git clone https://github.com/invergent-ai/surogate-agent
cd surogate-agent

# Install for development (Python 3.12+ recommended)
pip install -e ".[dev,anthropic,api]"
# or with uv:
uv sync --extra dev --extra anthropic --extra api

# Run the test suite (no LLM required — all mocked)
pytest tests/ -v

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

---

## Contributing

Contributions are welcome! Feel free to open an issue to report bugs or suggest improvements, and submit pull requests for fixes or new features.

When submitting a PR, please include:

- A clear description of the change and the motivation behind it
- Steps to test or verify the change locally
- New or updated tests covering the changed behaviour
- Relevant examples for new CLI commands or API endpoints

Please make sure all existing tests pass (`pytest tests/ -v`) and the linter is clean (`ruff check src/ tests/`) before submitting.

---

## License

Apache 2.0 — see [LICENSE](./LICENSE).
