# Surogate Agent — Web UI

Angular 19 + Tailwind CSS 4 frontend for the Surogate Agent API. Served by FastAPI at `/` in production; proxied to the API during development.

## Architecture

```
src/app/
├── core/
│   ├── models/          auth.models.ts  chat.models.ts  skill.models.ts  session.models.ts
│   ├── services/        auth  api-config  chat  skills  sessions  workspace
│   ├── interceptors/    auth.interceptor.ts  (attaches Bearer token; handles 401)
│   └── guards/          auth.guard.ts  (redirect to /login if unauthenticated)
├── shared/
│   └── components/
│       ├── chat/              Central chat pane (role-agnostic, SSE)
│       ├── message-bubble/    User / assistant message rendering
│       ├── thinking-block/    Collapsible thinking block (CLI-style)
│       ├── tool-call-block/   Collapsible tool call + result
│       ├── file-list/         Generic file manager (upload / download / delete)
│       ├── file-viewer/       Inline text viewer / editor
│       ├── skill-tabs/        IDE-style paginated skill tabs
│       └── validation-badge/  Valid / warning / error pill
└── pages/
    ├── login/       Login form (username + password → JWT)
    ├── register/    Registration form (username, email, password, role)
    ├── developer/   3-column IDE layout (skills browser | chat | workspace + test panel)
    └── user/        2-column layout (file panels | chat)
```

## Routes

| Path | Component | Guard |
|------|-----------|-------|
| `/` | redirect → `/login` | — |
| `/login` | `LoginComponent` | none |
| `/register` | `RegisterComponent` | none |
| `/developer` | `DeveloperComponent` | `authGuard` |
| `/user` | `UserComponent` | `authGuard` |

Role-based navigation: after login the user is redirected to `/developer` or `/user` based on the `role` claim in the JWT.

## Development

```bash
npm install
ng serve        # http://localhost:4200
                # proxies /api/* → http://localhost:8000 (see proxy.conf.json)
```

The backend must be running (`surogate-agent serve`) with the `[api,auth]` extras installed.

## Build for production

```bash
ng build --configuration production
# Output: dist/surogate-frontend/browser/
# Docker copies this to /app/static; FastAPI serves it at /
```

## Key conventions

- Angular 19 **standalone components** — no NgModules anywhere.
- Angular **Signals** (`signal()`, `computed()`, `effect()`) for reactive state.
- **Tailwind v4** — `@import "tailwindcss"` in `styles.css`; no config file needed.
- SSE consumed via `fetch()` + `ReadableStream` (not `EventSource` — POST required).
- Lazy-loaded routes via `loadComponent`.
- JWT stored in `localStorage` under key `surogate_token`; decoded client-side for username/role/expiry.

## Environment

| File | Used when |
|------|-----------|
| `src/environments/environment.ts` | Production build (`apiUrl: ''` — same origin) |
| `src/environments/environment.development.ts` | Dev server (`apiUrl: 'http://localhost:8000'`) |
