# ─── Stage 0: build Angular frontend ─────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend
COPY src/frontend/package*.json ./
RUN npm ci
COPY src/frontend/ ./
RUN npx ng build --configuration production


# ─── Stage 1: build venv ──────────────────────────────────────────────────────
FROM ubuntu:24.04 AS builder

# Install Python 3.12 (same as runtime so venv paths match)
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.12 python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

# Install uv — fast Python package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first so this layer is cached unless deps change
COPY pyproject.toml uv.lock README.md ./
# Minimal src stub required by hatchling to resolve the package during install
COPY src/ src/

# Create venv and install all production extras (anthropic + api)
# --frozen  → respect uv.lock exactly
# --no-dev  → skip dev-only tools (pytest, ruff, mypy)
# --python  → pin to the same Python the runtime will use
RUN uv sync --frozen --no-dev --extra anthropic --extra openai --extra api --extra auth --python /usr/bin/python3.12


# ─── Stage 2: runtime image ───────────────────────────────────────────────────
FROM ubuntu:24.04 AS runtime

LABEL org.opencontainers.image.title="surogate-agent" \
      org.opencontainers.image.description="Role-aware deep agent with meta-skill for conversational skill development" \
      org.opencontainers.image.source="https://github.com/invergent-ai/surogate-agent" \
      org.opencontainers.image.licenses="Apache-2.0"

# Install Python 3.12 runtime (no dev headers needed)
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.12 python3.12-venv \
    && ln -sf /usr/bin/python3.12 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.12 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed venv and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src   /app/src

# Copy Angular build output
COPY --from=frontend-builder /frontend/dist/surogate-frontend/browser /app/static

# Put the venv on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Default data directories — override via env vars or bind mounts
ENV SUROGATE_SKILLS_DIR=/data/skills \
    SUROGATE_SESSIONS_DIR=/data/sessions \
    SUROGATE_WORKSPACE_DIR=/data/workspace \
    SUROGATE_MODEL=claude-sonnet-4-6 \
    SUROGATE_STATIC_DIR=/app/static \
    SUROGATE_DATABASE_URL=sqlite:////data/surogate.db

# Create data directories
RUN mkdir -p /data/skills /data/sessions /data/workspace

EXPOSE 8000

# Declare /data as a volume so the SQLite DB and all data dirs persist across restarts
VOLUME ["/data"]

# Health check — verifies the API is reachable
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" \
    || exit 1

CMD ["surogate-agent", "serve", "--host", "0.0.0.0", "--port", "8000"]
