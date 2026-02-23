# REST API Reference

The Surogate Agent REST API mirrors every CLI command as an HTTP endpoint. Chat responses stream via **Server-Sent Events (SSE)**. All filesystem paths are configured server-side via environment variables — clients never pass directory paths in requests.

---

## Installation & startup

```bash
pip install "surogate-agent[api]"
```

```bash
# Start the server (default: http://127.0.0.1:8000)
surogate-agent serve

# Or use the standalone entry point
surogate-agent-api

# Custom host/port with auto-reload
surogate-agent serve --host 0.0.0.0 --port 9000 --reload
```

Interactive API docs are available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Server configuration

All paths and the default model are configured via environment variables. Set them before starting the server.

| Variable | Default | Description |
|----------|---------|-------------|
| `SUROGATE_SKILLS_DIR` | `./skills` | User skills root directory |
| `SUROGATE_SESSIONS_DIR` | `./sessions` | Session workspace root directory |
| `SUROGATE_WORKSPACE_DIR` | `./workspace` | Developer scratch workspace root |
| `SUROGATE_MODEL` | `claude-sonnet-4-6` | Default LLM model string |

```bash
export SUROGATE_SKILLS_DIR=/data/skills
export SUROGATE_SESSIONS_DIR=/data/sessions
export SUROGATE_WORKSPACE_DIR=/data/workspace
export SUROGATE_MODEL=claude-sonnet-4-6
export ANTHROPIC_API_KEY=sk-ant-...

surogate-agent serve --host 0.0.0.0 --port 8000
```

---

## Authentication

The server does not implement authentication itself. Protect it with your infrastructure (reverse proxy, API gateway, mTLS, etc.) in production.

---

## Routes overview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Stream a chat response (SSE) |
| `GET` | `/skills` | List all skills |
| `GET` | `/skills/{name}` | Get skill details |
| `POST` | `/skills` | Create a new skill |
| `DELETE` | `/skills/{name}` | Delete a user skill |
| `POST` | `/skills/{name}/validate` | Validate a skill |
| `GET` | `/skills/{name}/files` | List helper files |
| `GET` | `/skills/{name}/files/{file}` | Download a helper file |
| `POST` | `/skills/{name}/files/{file}` | Upload a helper file |
| `DELETE` | `/skills/{name}/files/{file}` | Delete a helper file |
| `GET` | `/sessions` | List all sessions |
| `GET` | `/sessions/{id}` | Get session details |
| `DELETE` | `/sessions/{id}` | Delete a session |
| `GET` | `/sessions/{id}/files` | List session files |
| `GET` | `/sessions/{id}/files/{file}` | Download a session file |
| `POST` | `/sessions/{id}/files` | Upload a file to a session |
| `DELETE` | `/sessions/{id}/files/{file}` | Delete a session file |
| `GET` | `/workspace` | List all skill workspaces |
| `GET` | `/workspace/{skill}` | Get workspace details |
| `DELETE` | `/workspace/{skill}` | Delete a skill workspace |
| `GET` | `/workspace/{skill}/files` | List workspace files |
| `GET` | `/workspace/{skill}/files/{file}` | Download a workspace file |
| `POST` | `/workspace/{skill}/files` | Upload a file to a workspace |
| `DELETE` | `/workspace/{skill}/files/{file}` | Delete a workspace file |

---

## Chat

### `POST /chat`

Stream an agent response as Server-Sent Events.

**Request body** (`application/json`):

```json
{
  "message": "Summarise my Jira tickets",
  "role": "user",
  "session_id": "20260101-120000-abc123",
  "skill": "",
  "model": "claude-sonnet-4-6",
  "user_id": "",
  "allow_execute": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message` | `string` | required | User message text |
| `role` | `string` | `"user"` | `"developer"` or `"user"` |
| `session_id` | `string` | `""` | Resume an existing user session; creates a new one if empty |
| `skill` | `string` | `""` | Developer mode: skill context for this session (enables persistent history keyed by skill name) |
| `model` | `string` | `""` | Override the server default model |
| `user_id` | `string` | `""` | Audit identifier |
| `allow_execute` | `boolean` | `false` | Enable `LocalShellBackend` (shell execution) for this request |

**Response**: `text/event-stream`

Each SSE event has an `event` type and a JSON-encoded `data` payload:

```
event: thinking
data: {"text": "I need to check the available Jira API credentials..."}

event: tool_call
data: {"name": "execute", "args": {"command": "curl https://api.atlassian.com/..."}}

event: tool_result
data: {"name": "execute", "result": "[{\"key\": \"PROJ-42\", \"summary\": \"...\"}]"}

event: text
data: {"text": "Here are your 3 open Jira tickets:\n\n- **PROJ-42**: ..."}

event: done
data: {"session_id": "20260101-120000-abc123", "files": ["report.md"]}
```

| Event | Data fields | Description |
|-------|-------------|-------------|
| `thinking` | `text` | Extended thinking block (Claude only) |
| `tool_call` | `name`, `args` | Agent is calling a tool |
| `tool_result` | `name`, `result` | Tool returned a result (truncated to 500 chars) |
| `text` | `text` | Assistant text response |
| `done` | `session_id`, `files` | Stream complete; lists files written to the session workspace |
| `error` | `detail` | An error occurred |

**Example — `curl`:**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a skill that generates weekly git commit summaries",
    "role": "developer",
    "skill": "git-weekly-summary"
  }' \
  --no-buffer
```

**Example — Python (`httpx`):**

```python
import httpx, json

with httpx.stream("POST", "http://localhost:8000/chat",
                  json={"message": "Hello", "role": "user"}) as r:
    for line in r.iter_lines():
        if line.startswith("data:"):
            payload = json.loads(line[5:].strip())
            print(payload)
```

**Example — JavaScript (`EventSource` via fetch):**

```javascript
const resp = await fetch("http://localhost:8000/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: "Hello", role: "user" }),
});

const reader = resp.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  console.log(decoder.decode(value));
}
```

---

## Skills

### `GET /skills`

List all discovered skills (builtin + user).

**Query parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `role` | `all` | Filter: `all`, `developer`, or `user` |

**Response** `200 OK`:

```json
[
  {
    "name": "jira-summariser",
    "description": "Pulls Jira tickets and summarises them",
    "version": "0.1.0",
    "role_restriction": null,
    "path": "/data/skills/jira-summariser"
  }
]
```

---

### `GET /skills/{name}`

Get full details for a skill, including the `SKILL.md` content and helper file listing.

**Response** `200 OK`:

```json
{
  "name": "jira-summariser",
  "description": "Pulls Jira tickets and summarises them",
  "version": "0.1.0",
  "role_restriction": null,
  "allowed_tools": ["read_file", "execute"],
  "path": "/data/skills/jira-summariser",
  "skill_md_content": "---\nname: jira-summariser\n...",
  "helper_files": [
    { "name": "prompt.md", "size_bytes": 412 }
  ]
}
```

**Response** `404 Not Found` — skill not found.

---

### `POST /skills`

Create a new skill directory and `SKILL.md`.

**Request body:**

```json
{
  "name": "jira-summariser",
  "description": "Pulls Jira tickets and summarises them",
  "role_restriction": null,
  "allowed_tools": ["read_file", "execute"],
  "version": "0.1.0",
  "skill_md_body": "## Instructions\n\nWhen this skill is active..."
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Skill name in kebab-case |
| `description` | yes | One-liner (≤ 1024 chars) |
| `role_restriction` | no | `"developer"`, `"user"`, or `null` |
| `allowed_tools` | no | List of tool names |
| `version` | no | Semver string (default `"0.1.0"`) |
| `skill_md_body` | no | Markdown appended after the frontmatter |

**Response** `201 Created` — `SkillResponse` object (same as `GET /skills/{name}`).

**Response** `409 Conflict` — a skill with this name already exists.

---

### `DELETE /skills/{name}`

Delete a user skill directory. Built-in skills cannot be deleted.

**Response** `200 OK`:

```json
{ "deleted": "jira-summariser" }
```

**Response** `403 Forbidden` — attempting to delete a built-in skill.

**Response** `404 Not Found` — skill not found.

---

### `POST /skills/{name}/validate`

Validate a skill's `SKILL.md` frontmatter.

**Response** `200 OK`:

```json
{
  "valid": true,
  "errors": [],
  "warnings": ["description exceeds 1024 characters (will be truncated)"]
}
```

---

### `GET /skills/{name}/files`

List helper files for a skill (all files except `SKILL.md`).

**Response** `200 OK`:

```json
[
  { "name": "prompt.md", "size_bytes": 412 },
  { "name": "output-schema.json", "size_bytes": 1024 }
]
```

---

### `GET /skills/{name}/files/{file}`

Download a helper file.

**Response** `200 OK` — file content with appropriate `Content-Type`.

**Response** `404 Not Found`.

---

### `POST /skills/{name}/files/{file}`

Upload a helper file.

**Request:** `multipart/form-data` with field `upload` (the file).

**Query parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `force` | `false` | Overwrite if the file already exists |

```bash
curl -X POST http://localhost:8000/skills/jira-summariser/files/prompt.md \
  -F "upload=@./prompt.md"

# Overwrite existing
curl -X POST "http://localhost:8000/skills/jira-summariser/files/prompt.md?force=true" \
  -F "upload=@./prompt.md"
```

**Response** `201 Created`:

```json
{ "uploaded": "prompt.md", "size_bytes": 412 }
```

**Response** `409 Conflict` — file already exists and `force=false`.

---

### `DELETE /skills/{name}/files/{file}`

Delete a helper file. `SKILL.md` cannot be deleted via this endpoint.

**Response** `200 OK`:

```json
{ "deleted": "prompt.md" }
```

**Response** `403 Forbidden` — attempting to delete `SKILL.md`.

**Response** `404 Not Found`.

---

## Sessions

Sessions are isolated per-chat workspaces where users place input files and the agent writes output files.

### `GET /sessions`

List all sessions.

**Response** `200 OK`:

```json
[
  {
    "session_id": "20260101-120000-abc123",
    "workspace_dir": "/data/sessions/20260101-120000-abc123",
    "files": [
      { "name": "data.csv", "size_bytes": 2048 },
      { "name": "report.md", "size_bytes": 512 }
    ]
  }
]
```

---

### `GET /sessions/{id}`

Get details for a single session.

**Response** `200 OK` — `SessionResponse` object (same structure as above).

**Response** `404 Not Found`.

---

### `DELETE /sessions/{id}`

Delete a session workspace and all its files.

**Response** `200 OK`:

```json
{ "deleted": "20260101-120000-abc123" }
```

**Response** `404 Not Found`.

---

### `GET /sessions/{id}/files`

List files in a session workspace.

**Response** `200 OK` — array of `FileInfo` objects.

---

### `GET /sessions/{id}/files/{file}`

Download a file from a session workspace.

**Response** `200 OK` — file content.

**Response** `404 Not Found`.

---

### `POST /sessions/{id}/files`

Upload a file to a session workspace. Creates the session if it does not exist yet.

**Request:** `multipart/form-data` with field `upload`.

**Query parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `filename` | `""` | Override the destination filename |

```bash
# Upload input data before starting a chat
curl -X POST "http://localhost:8000/sessions/my-session/files?filename=data.csv" \
  -F "upload=@./data.csv"
```

**Response** `201 Created`:

```json
{ "uploaded": "data.csv", "session_id": "my-session", "size_bytes": 2048 }
```

---

### `DELETE /sessions/{id}/files/{file}`

Delete a file from a session workspace.

**Response** `200 OK`:

```json
{ "deleted": "data.csv" }
```

---

## Workspace

The developer workspace is a persistent scratch area for files used *while building* skills. These files are never part of a skill definition and never accessible in user sessions.

### `GET /workspace`

List all skill workspace directories.

**Response** `200 OK`:

```json
[
  {
    "skill": "jira-summariser",
    "workspace_dir": "/data/workspace/jira-summariser",
    "files": [
      { "name": "draft-prompt.md", "size_bytes": 234 },
      { "name": "test-tickets.json", "size_bytes": 1820 }
    ]
  }
]
```

---

### `GET /workspace/{skill}`

Get the workspace for a specific skill.

**Response** `200 OK` — `WorkspaceResponse` object.

**Response** `404 Not Found`.

---

### `DELETE /workspace/{skill}`

Delete a skill's workspace directory and all its files.

**Response** `200 OK`:

```json
{ "deleted": "jira-summariser" }
```

---

### `GET /workspace/{skill}/files`

List files in a skill workspace.

**Response** `200 OK` — array of `FileInfo` objects.

---

### `GET /workspace/{skill}/files/{file}`

Download a workspace file.

**Response** `200 OK` — file content.

---

### `POST /workspace/{skill}/files`

Upload a file to a skill workspace. Creates the workspace directory if it does not exist.

**Request:** `multipart/form-data` with field `upload`.

**Query parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `filename` | `""` | Override the destination filename |

```bash
curl -X POST "http://localhost:8000/workspace/jira-summariser/files?filename=test-input.json" \
  -F "upload=@./test-input.json"
```

**Response** `201 Created`:

```json
{ "uploaded": "test-input.json", "skill": "jira-summariser", "size_bytes": 1820 }
```

---

### `DELETE /workspace/{skill}/files/{file}`

Delete a file from a skill workspace.

**Response** `200 OK`:

```json
{ "deleted": "test-input.json" }
```

---

## Data models

### `ChatRequest`

```python
class ChatRequest(BaseModel):
    message: str
    role: str = "user"              # "developer" | "user"
    session_id: str = ""
    skill: str = ""
    model: str = ""
    user_id: str = ""
    allow_execute: bool = False
```

### `SkillCreateRequest`

```python
class SkillCreateRequest(BaseModel):
    name: str
    description: str
    role_restriction: Optional[str] = None
    allowed_tools: list[str] = []
    version: str = "0.1.0"
    skill_md_body: str = ""
```

### `SkillResponse`

```python
class SkillResponse(BaseModel):
    name: str
    description: str
    version: str
    role_restriction: Optional[str]
    allowed_tools: list[str]
    path: str
    skill_md_content: str
    helper_files: list[FileInfo]
```

### `SkillListItem`

```python
class SkillListItem(BaseModel):
    name: str
    description: str
    version: str
    role_restriction: Optional[str]
    path: str
```

### `FileInfo`

```python
class FileInfo(BaseModel):
    name: str
    size_bytes: int
```

### `ValidationResult`

```python
class ValidationResult(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]
```

### `SessionResponse`

```python
class SessionResponse(BaseModel):
    session_id: str
    workspace_dir: str
    files: list[FileInfo]
```

### `WorkspaceResponse`

```python
class WorkspaceResponse(BaseModel):
    skill: str
    workspace_dir: str
    files: list[FileInfo]
```

---

## Error responses

All endpoints return standard JSON error responses on failure:

```json
{
  "detail": "Skill 'my-skill' not found"
}
```

| HTTP Status | Meaning |
|-------------|---------|
| `404 Not Found` | The requested resource does not exist |
| `403 Forbidden` | Operation not allowed (e.g. deleting a built-in skill or `SKILL.md`) |
| `409 Conflict` | Resource already exists (skill, helper file without `force=true`) |
| `422 Unprocessable Entity` | Request body validation failed (Pydantic) |
| `500 Internal Server Error` | Unexpected server error |

---

## Complete workflow example

```bash
# 1. Start the server
SUROGATE_SKILLS_DIR=./skills surogate-agent serve &

# 2. Create a skill via the API
curl -X POST http://localhost:8000/skills \
  -H "Content-Type: application/json" \
  -d '{
    "name": "csv-to-report",
    "description": "Reads a CSV file and generates a Markdown report",
    "allowed_tools": ["read_file", "write_file"],
    "skill_md_body": "## Instructions\n\nRead the CSV, analyse it, write report.md."
  }'

# 3. Upload input data to a session
curl -X POST "http://localhost:8000/sessions/my-session/files?filename=data.csv" \
  -F "upload=@./data.csv"

# 4. Run a chat session (streams SSE)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Process data.csv and write a report",
    "role": "user",
    "session_id": "my-session"
  }' --no-buffer

# 5. Download the generated report
curl http://localhost:8000/sessions/my-session/files/report.md

# 6. Clean up
curl -X DELETE http://localhost:8000/sessions/my-session
```
