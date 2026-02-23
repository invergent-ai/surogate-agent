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
# Install all extras: Claude models + OpenAI models + API server + auth + dev tools
uv sync --extra anthropic --extra openai --extra api --extra auth --extra dev

# Activate the venv
source .venv/bin/activate
```

### With pip

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[anthropic,openai,api,auth,dev]"
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

# Auth (required when running with [auth] extra)
export SUROGATE_JWT_SECRET=dev-secret-change-in-prod
# SQLite default (local dev): sqlite:///./surogate.db  (file created in CWD)
# Docker default:             sqlite:////data/surogate.db  (set in Dockerfile ENV)
# export SUROGATE_DATABASE_URL=postgresql://user:pass@db:5432/surogate  # prod PostgreSQL
# export SUROGATE_ACCESS_TOKEN_EXPIRE_MINUTES=480
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
- Web UI: http://localhost:8000
- API docs (Swagger UI): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Frontend (Angular)

The Angular UI lives in `src/frontend/`. It is served by FastAPI at `/` in production, but during development you run it separately with a proxy:

```bash
cd src/frontend
npm install
ng serve       # http://localhost:4200 — proxies /api/* to localhost:8000
```

Build for production (output is bundled into `dist/surogate-frontend/browser/` which the Dockerfile copies to `/app/static`):

```bash
ng build --configuration production
```

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

The Dockerfile is a three-stage build:

1. **frontend-builder** — runs `ng build` inside a Node.js image; output lands in `dist/surogate-frontend/browser/`
2. **builder** — installs all Python dependencies with `uv` into `.venv`
3. **runtime** — `ubuntu:24.04` with Python 3.12; copies the venv, source, and built frontend; runs as root

### Run the container

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e SUROGATE_MODEL=claude-sonnet-4-6 \
  -e SUROGATE_JWT_SECRET=change-me-in-production \
  -p 8000:8000 \
  -v $(pwd)/data:/data \
  surogate-agent
```

This mounts a local `./data` directory to `/data` in the container, persisting skills, sessions, workspace files, and the SQLite database (`data/surogate.db`).

### Run with Docker Compose (SQLite, dev)

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
      SUROGATE_JWT_SECRET: ${JWT_SECRET:-change-me}
    volumes:
      - ./skills:/data/skills
      - ./sessions:/data/sessions
      - ./workspace:/data/workspace
    restart: unless-stopped
```

### Run with Docker Compose (PostgreSQL, prod)

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: surogate
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: surogate
    volumes:
      - pgdata:/var/lib/postgresql/data

  surogate-agent:
    image: ghcr.io/invergent-ai/surogate-agent:latest
    ports:
      - "8000:8000"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      SUROGATE_MODEL: claude-sonnet-4-6
      SUROGATE_JWT_SECRET: ${JWT_SECRET}
      SUROGATE_DATABASE_URL: postgresql://surogate:${DB_PASSWORD}@db:5432/surogate
    volumes:
      - ./skills:/data/skills
      - ./sessions:/data/sessions
      - ./workspace:/data/workspace
    depends_on: [db]
    restart: unless-stopped

volumes:
  pgdata:
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
| `/data/surogate.db` | SQLite auth database (default) | included in `/data` volume |

`/data` is declared as a Docker `VOLUME` — mount it to persist all data (skills, sessions, workspace, and the SQLite database) across container restarts.

To use PostgreSQL instead, set `SUROGATE_DATABASE_URL=postgresql://user:pass@db:5432/surogate` and the `/data/surogate.db` file will not be created.

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
│   ├── auth/               JWT auth — database, models, service, jwt, schemas
│   ├── core/               create_agent(), Role, AgentConfig, Session
│   ├── skills/             SkillLoader, SkillRegistry, builtin skills
│   ├── middleware/         RoleGuardAgent
│   ├── api/                FastAPI app, routers, models
│   └── cli/                Typer CLI commands
├── src/frontend/           Angular 19 + Tailwind CSS web UI
│   ├── src/app/
│   │   ├── core/           services, models, interceptors, guards
│   │   ├── shared/         reusable components (chat, file-list, skill-tabs…)
│   │   └── pages/          login, register, developer, user
│   └── dist/               built output (git-ignored; Docker copies to /app/static)
├── tests/                  109 fully-mocked tests
├── docs/                   CLI, API, and development documentation
├── assets/                 Logo and other static assets
├── Dockerfile              Three-stage production build (frontend + python + runtime)
├── .dockerignore
├── pyproject.toml          Package metadata, dependencies, tool config
├── uv.lock                 Locked dependency versions
├── release-please-config.json
├── .release-please-manifest.json
└── .github/
    └── workflows/
        └── release-please.yml   CI/CD: release + Docker push
```
