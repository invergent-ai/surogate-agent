# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the frontend extension in this directory.

## Overview

Angular 19 + Tailwind CSS 4 frontend for Surogate Agent. Communicates with the `surogate-agent` REST API.
Two perspectives: **Developer** (IDE-style skill authoring) and **User** (chat + file management).

## API contract

The backend API is documented in `../../docs/api.md`. The base URL is configurable via environment files.

Key endpoints:
- `POST /chat` — SSE stream for agent responses
- `GET/POST/DELETE /skills` — skill management
- `GET/DELETE /sessions/{id}` — session management
- `GET /workspace/{skill}` — developer workspace browsing

## Development

```bash
cd src/frontend
npm install
ng serve                          # http://localhost:4200 (proxy to localhost:8000 is built-in)
```

Proxy config is in `proxy.conf.json` and wired in `angular.json` — all `/api/**` requests are
forwarded to `http://localhost:8000` with the `/api` prefix stripped.

## Build for Docker

```bash
ng build --configuration production
# Output: dist/surogate-frontend/browser/
# Docker COPY target: /app/static (served by FastAPI at /)
```

## Architecture

```
src/app/
├── core/
│   ├── models/      chat.models.ts  skill.models.ts  session.models.ts
│   └── services/    api-config  chat  skills  sessions  workspace
├── shared/components/
│   ├── chat/             Central chat pane (role-agnostic)
│   ├── message-bubble/   User/assistant message rendering
│   ├── thinking-block/   Collapsible thinking block (CLI-style)
│   ├── tool-call-block/  Collapsible tool call + result
│   ├── file-list/        Generic file manager (upload/download/delete)
│   ├── file-viewer/      Inline text editor
│   ├── skill-tabs/       IDE-style paginated skill tabs
│   └── validation-badge/ Valid/warning/error pill
└── pages/
    ├── entry/       Role picker + user ID
    ├── developer/   3-column IDE layout (skills browser | chat | workspace+test)
    └── user/        2-column layout (files | chat)
```

## Key conventions

- Angular 19 **standalone components** throughout — no NgModules
- Angular **Signals** for reactive state (`signal()`, `computed()`, `effect()`)
- **Tailwind v4** — no config file needed; just `@import "tailwindcss"` in styles.css
- SSE consumed via `fetch()` + `ReadableStream` (not `EventSource` — POST required)
- Lazy-loaded routes via `loadComponent`
- Environment: `src/app/environments/environment.ts` (prod) / `environment.development.ts` (dev)
