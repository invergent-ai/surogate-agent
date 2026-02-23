# Development Guide

Everything you need to run, test, lint, and ship surogate-agent locally or in a container.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | ≥ 3.12 | Required for the package |
| [uv](https://docs.astral.sh/uv/) | latest | Recommended package manager |
| Docker | ≥ 24 | For containerised runs and image builds |
| An LLM API key | — | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |

---

## Clone & install

```bash
git clone https://github.com/invergent-ai/surogate-agent
cd surogate-agent
```

### With uv (recommended)

```bash
# Install all extras: Claude models + OpenAI models + API server + dev tools
uv sync --extra anthropic --extra openai --extra api --extra dev

# Activate the venv
source .venv/bin/activate
```

### With pip

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[anthropic,openai,api,dev]"
```

---

## Environment variables

```bash
# Required for LLM calls
export ANTHROPIC_API_KEY=sk-ant-...   # Claude models
export OPENAI_API_KEY=sk-...          # OpenAI models (optional)

# Optional — override defaults
export SUROGATE_MODEL=claude-sonnet-4-6
export SUROGATE_SKILLS_DIR=./skills
export SUROGATE_SESSIONS_DIR=./sessions
export SUROGATE_WORKSPACE_DIR=./workspace
```

---

## Running locally

### Interactive CLI

```bash
# Developer session — meta-skill loaded, skill authoring enabled
surogate-agent developer

# User session
surogate-agent user

# Resume a skill-development session
surogate-agent developer --skill jira-summariser
```

### REST API server

```bash
# Default: http://127.0.0.1:8000
surogate-agent serve

# Custom host/port
surogate-agent serve --host 0.0.0.0 --port 9000

# With auto-reload on file changes (development)
surogate-agent serve --reload
```

Once running:
- API docs (Swagger UI): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: `curl http://localhost:8000/`

---

## Running tests

The full test suite is fully mocked — no LLM or network access required.

```bash
# Run all 109 tests
pytest tests/ -v

# Run a single test file
pytest tests/test_api.py -v

# Run a single test by name
pytest tests/test_agent.py::TestCreateAgent::test_developer_gets_meta_skill -v

# Run with coverage
pytest tests/ --cov=src/surogate_agent --cov-report=term-missing
```

---

## Lint & type check

```bash
# Lint (ruff)
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/

# Type check (mypy)
mypy src/
```

---

## Docker

### Build the image locally

```bash
docker build -t surogate-agent .
```

The Dockerfile is a two-stage build:

1. **builder** — installs all Python dependencies with `uv` into `.venv`
2. **runtime** — `ubuntu:24.04` with Python 3.12 installed; only the venv and source are copied across; runs as root

### Run the container

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e SUROGATE_MODEL=claude-sonnet-4-6 \
  -p 8000:8000 \
  -v $(pwd)/skills:/data/skills \
  -v $(pwd)/sessions:/data/sessions \
  -v $(pwd)/workspace:/data/workspace \
  surogate-agent
```

### Run with Docker Compose

Create a `docker-compose.yml` in your project:

```yaml
services:
  surogate-agent:
    image: ghcr.io/invergent-ai/surogate-agent:latest
    ports:
      - "8000:8000"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      SUROGATE_MODEL: claude-sonnet-4-6
    volumes:
      - ./skills:/data/skills
      - ./sessions:/data/sessions
      - ./workspace:/data/workspace
    restart: unless-stopped
```

```bash
docker compose up
```

### Data directories

| Container path | Purpose | Mount |
|----------------|---------|-------|
| `/data/skills` | User-authored skill definitions | `./skills` |
| `/data/sessions` | Per-chat user workspaces | `./sessions` |
| `/data/workspace` | Developer scratch area | `./workspace` |

All three are declared as Docker `VOLUME`s. Mount them to persist data across container restarts.

### Build for production (multi-platform)

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/invergent-ai/surogate-agent:latest \
  --push \
  .
```

---

## Release process

Releases are fully automated via [release-please](https://github.com/googleapis/release-please) and the GitHub Actions workflow at `.github/workflows/release-please.yml`.

### How it works

1. Merge commits to `main` following the [Conventional Commits](https://www.conventionalcommits.org/) spec.
2. Release Please opens (or updates) a release PR that bumps the version in `pyproject.toml` and updates `CHANGELOG.md`.
3. When the release PR is merged, release-please creates a GitHub Release and a version tag (e.g. `v0.2.0`).
4. The `docker` job in the workflow triggers, builds the image, and pushes it to GHCR with three tags:
   - `ghcr.io/invergent-ai/surogate-agent:0.2.0` — exact version
   - `ghcr.io/invergent-ai/surogate-agent:latest` — floating latest
   - `ghcr.io/invergent-ai/surogate-agent:sha-<commit>` — immutable SHA tag

### Commit message conventions

| Prefix | Effect | Example |
|--------|--------|---------|
| `feat:` | Minor version bump | `feat: add workspace clone command` |
| `fix:` | Patch version bump | `fix: correct session ID generation` |
| `feat!:` / `BREAKING CHANGE:` | Major version bump | `feat!: rename Role.ADMIN to Role.DEVELOPER` |
| `chore:`, `docs:`, `test:` | No version bump | `docs: update API reference` |

---

## Project layout

```
surogate-agent/
├── src/surogate_agent/     Python package
│   ├── core/               create_agent(), Role, AgentConfig, Session
│   ├── skills/             SkillLoader, SkillRegistry, builtin skills
│   ├── middleware/         RoleGuardAgent
│   ├── api/                FastAPI app, routers, models
│   └── cli/                Typer CLI commands
├── tests/                  109 fully-mocked tests
├── docs/                   CLI, API, and development documentation
├── assets/                 Logo and other static assets
├── Dockerfile              Two-stage production build
├── .dockerignore
├── pyproject.toml          Package metadata, dependencies, tool config
├── uv.lock                 Locked dependency versions
├── release-please-config.json
├── .release-please-manifest.json
└── .github/
    └── workflows/
        └── release-please.yml   CI/CD: release + Docker push
```
