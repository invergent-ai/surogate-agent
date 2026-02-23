# CLI Reference

`surogate-agent` is the main command-line interface for the Surogate Agent framework. It provides interactive chat sessions, skill management, session management, and developer workspace tools.

---

## Installation

```bash
pip install "surogate-agent[anthropic]"   # Claude models
pip install "surogate-agent[openai]"      # OpenAI models
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # Claude
export OPENAI_API_KEY=sk-...          # OpenAI
```

Override the default model:

```bash
export SUROGATE_MODEL=claude-sonnet-4-6
```

---

## Top-level commands

```
surogate-agent [OPTIONS] COMMAND [ARGS]...

Commands:
  chat        Generic interactive chat session (--role developer|user)
  user        Start a USER-role chat session (shortcut)
  developer   Start a DEVELOPER-role chat session (shortcut)
  serve       Start the FastAPI REST server
  skills      Manage agent skills
  session     Manage chat session workspaces
  workspace   Manage the developer scratch workspace
```

---

## `surogate-agent chat`

Start an interactive multi-turn chat session. Supports both developer and user roles.

```
surogate-agent chat [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--role` | `-r` | `developer` | Session role: `developer` or `user` |
| `--skill` | `-k` | | Skill name to develop (developer). Resumes previous session if one exists |
| `--model` | `-m` | `$SUROGATE_MODEL` | LangChain model string (e.g. `claude-sonnet-4-6`, `gpt-4o`) |
| `--skills-dir` | `-s` | `./skills` | Directory for user skills |
| `--workspace` | `-w` | `./workspace` | Developer scratch workspace root |
| `--extra-skills` | | | Additional directory to scan for installed skills |
| `--session` | `-t` | | Session ID to resume (user mode) |
| `--user` | `-u` | | User identifier for audit context |

**Key bindings:**

- `Alt+Enter` / `Meta+Enter` — submit message
- `Enter` — insert newline
- `Ctrl-D` / `exit` / `quit` — end session

**Examples:**

```bash
# Developer session — meta-skill loaded
surogate-agent chat --role developer

# Developer session working on a specific skill (persistent history)
surogate-agent chat --role developer --skill jira-summariser

# User session with a custom skills directory
surogate-agent chat --role user --skills-dir ./my-skills

# Resume a previous user session
surogate-agent chat --role user --session 20260101-120000-abc123

# Use a different model
surogate-agent chat --role user --model gpt-4o
```

---

## `surogate-agent user`

Shortcut for `surogate-agent chat --role user`.

```
surogate-agent user [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--model` | `-m` | `$SUROGATE_MODEL` | LangChain model string |
| `--session` | `-t` | | Session ID to resume |
| `--skills-dir` | `-s` | `./skills` | Skills directory |
| `--extra-skills` | | | Additional skills directory |
| `--user` | `-u` | | User identifier |

```bash
surogate-agent user
surogate-agent user --session 20260101-120000-abc123
```

---

## `surogate-agent developer`

Shortcut for `surogate-agent chat --role developer`. The meta-skill is always active.

```
surogate-agent developer [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--skill` | `-k` | | Skill to develop. Resume previous session with the same name if it exists |
| `--model` | `-m` | `$SUROGATE_MODEL` | LangChain model string |
| `--skills-dir` | `-s` | `./skills` | Directory where new skills are saved |
| `--workspace` | `-w` | `./workspace` | Developer scratch workspace root |
| `--extra-skills` | | | Additional skills directory |
| `--user` | `-u` | | User identifier |

```bash
# Start a new developer session
surogate-agent developer

# Work on a specific skill (SQLite history persists across restarts)
surogate-agent developer --skill jira-summariser

# Resume and show that the previous context is loaded
surogate-agent developer --skill jira-summariser
# → "Resuming jira-summariser  thread: dev:jira-summariser"
```

**How skill-development sessions work:**

- With `--skill <name>`: a `SqliteSaver` checkpointer is opened at `workspace/.history.db`, keyed by `dev:<name>`. The conversation is fully persistent — restart the CLI and pick up exactly where you left off.
- Without `--skill`: a fresh in-memory session is created each time.
- Shell execution is enabled by default for developer sessions (`allow_execute=True`).

---

## `surogate-agent serve`

Start the FastAPI REST server. Requires the `[api]` extra.

```
surogate-agent serve [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8000` | Bind port |
| `--reload` | `False` | Enable auto-reload (development) |

```bash
pip install "surogate-agent[api]"

surogate-agent serve
surogate-agent serve --host 0.0.0.0 --port 9000
surogate-agent serve --reload   # auto-reload on file changes
```

See [docs/api.md](./api.md) for the full REST API reference.

---

## `surogate-agent skills`

Manage agent skills — list, inspect, create, validate, delete, and manage helper files.

```
surogate-agent skills [OPTIONS] COMMAND [ARGS]...

Commands:
  list      List all discovered skills
  show      Print SKILL.md and helper file listing for a skill
  new       Scaffold a blank skill directory interactively
  validate  Validate a skill directory
  delete    Delete a user skill directory
  files     Manage helper files inside a skill directory
```

### `skills list`

```
surogate-agent skills list [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--skills-dir` | `-s` | `./skills` | Root directory to scan for user skills |
| `--role` | `-r` | `all` | Filter by role: `developer`, `user`, or `all` |

```bash
surogate-agent skills list
surogate-agent skills list --role user
surogate-agent skills list --skills-dir ./custom-skills
```

**Output columns:** Name, Version, Role (`all` / `developer`), Description, Path

### `skills show`

Print the full `SKILL.md` content and list any helper files.

```
surogate-agent skills show <name> [OPTIONS]
```

```bash
surogate-agent skills show jira-summariser
```

### `skills new`

Scaffold a blank skill directory interactively. Prompts for name, description, role restriction, and optional helper files.

```
surogate-agent skills new [NAME] [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--skills-dir` | `-s` | `./skills` | Where to create the skill |

```bash
surogate-agent skills new jira-summariser
# → prompts for description, role, helper files
# → creates ./skills/jira-summariser/SKILL.md
```

The scaffolded `SKILL.md` includes placeholder comments. Edit it directly or ask the developer agent to fill it in.

### `skills validate`

Validate a skill directory and report errors or warnings.

```
surogate-agent skills validate <path>
```

```bash
surogate-agent skills validate ./skills/jira-summariser
```

**Checks:**
- `SKILL.md` exists and has valid YAML frontmatter
- `name` is present and in kebab-case
- `description` is ≤ 1024 characters
- `role-restriction` is `developer`, `user`, or omitted

Exit code `0` = valid; `1` = validation failed.

### `skills delete`

Delete a user skill directory. Built-in skills are protected and cannot be deleted.

```
surogate-agent skills delete <name> [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--skills-dir` | `-s` | `./skills` | Skills root |
| `--force` | `-f` | `False` | Skip confirmation prompt |

```bash
surogate-agent skills delete jira-summariser
surogate-agent skills delete jira-summariser --force
```

### `skills files`

Manage helper files (any file other than `SKILL.md`) inside a skill directory.

```
surogate-agent skills files [OPTIONS] COMMAND [ARGS]...

Commands:
  list    List helper files for a skill
  show    Print the contents of a helper file
  add     Create or update a helper file
  remove  Delete a helper file
```

#### `skills files list`

```bash
surogate-agent skills files list jira-summariser
```

#### `skills files show`

```bash
surogate-agent skills files show jira-summariser prompt.md
```

#### `skills files add`

Create or update a helper file. Content can be supplied via `--content`, piped from stdin, or entered interactively.

```
surogate-agent skills files add <skill> <filename> [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--content` | `-c` | | File content (reads stdin if omitted) |
| `--force` | `-f` | `False` | Overwrite if file already exists |
| `--skills-dir` | `-s` | `./skills` | Skills root |

```bash
# Via --content flag
surogate-agent skills files add jira-summariser prompt.md \
  --content "Summarise in 3 bullet points."

# Pipe from stdin
cat prompt.md | surogate-agent skills files add jira-summariser prompt.md

# Interactive
surogate-agent skills files add jira-summariser schema.json
# → Enter content, finish with Ctrl-D
```

#### `skills files remove`

```bash
surogate-agent skills files remove jira-summariser prompt.md
surogate-agent skills files remove jira-summariser prompt.md --force
```

`SKILL.md` cannot be removed with this command — delete the whole skill with `skills delete` instead.

---

## `surogate-agent session`

Manage user chat session workspaces. Each session has an isolated directory under `./sessions/<session-id>/` where the agent reads input files and writes output files.

```
surogate-agent session [OPTIONS] COMMAND [ARGS]...

Commands:
  list     List all session workspaces
  show     Show session details and file listing
  clean    Delete a session workspace and all its files
  files    Manage files in a session workspace
```

### `session list`

```bash
surogate-agent session list
surogate-agent session list --sessions-dir ./custom-sessions
```

**Output columns:** Session ID, Files count, Total size, Workspace path

### `session show`

```bash
surogate-agent session show 20260101-120000-abc123
```

### `session clean`

```
surogate-agent session clean <session-id> [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Skip confirmation |

```bash
surogate-agent session clean 20260101-120000-abc123
surogate-agent session clean 20260101-120000-abc123 --force
```

### `session files`

```
surogate-agent session files [OPTIONS] COMMAND [ARGS]...

Commands:
  list    List files in a session workspace
  show    Print a file from the workspace
  add     Copy a file into a session workspace
  remove  Delete a file from the workspace
```

#### `session files add`

Copy a local file into a session workspace. Creates the session if it does not exist yet.

```
surogate-agent session files add <session-id> <source-path> [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--filename` | `-n` | Override the destination filename |

```bash
# Place input data before starting a chat
surogate-agent session files add my-session ./data.csv
surogate-agent chat --role user --session my-session

# Then in chat:
# > Process data.csv and generate a report
```

#### `session files show`

```bash
surogate-agent session files show my-session report.md
```

#### `session files remove`

```bash
surogate-agent session files remove my-session data.csv
surogate-agent session files remove my-session data.csv --force
```

---

## `surogate-agent workspace`

Manage the **developer scratch workspace** — a persistent area for files used *while building* skills. Workspace files are never part of a skill definition and never accessible to user sessions.

```
workspace/
└── <skill-name>/     ← one dir per skill being developed
    ├── draft-prompt.md
    ├── test-input.json
    └── experiment-notes.md
```

```
surogate-agent workspace [OPTIONS] COMMAND [ARGS]...

Commands:
  list     List all skill workspace directories
  show     Show files for a skill's workspace
  clean    Delete a skill's workspace directory
  files    Manage files inside a skill workspace
```

### `workspace list`

```bash
surogate-agent workspace list
surogate-agent workspace list --workspace-dir ./custom-workspace
```

### `workspace show`

```bash
surogate-agent workspace show jira-summariser
```

### `workspace clean`

```
surogate-agent workspace clean <skill> [OPTIONS]
```

```bash
surogate-agent workspace clean jira-summariser
surogate-agent workspace clean jira-summariser --force
```

### `workspace files`

```
surogate-agent workspace files [OPTIONS] COMMAND [ARGS]...

Commands:
  list    List files in a skill workspace
  show    Print a workspace file
  add     Copy a file into a skill workspace
  remove  Delete a workspace file
```

#### `workspace files add`

```bash
# Add a sample input for testing a skill being developed
surogate-agent workspace files add csv-to-report ./sample-data.csv
```

#### `workspace files show`

```bash
surogate-agent workspace files show csv-to-report sample-data.csv
```

#### `workspace files remove`

```bash
surogate-agent workspace files remove csv-to-report sample-data.csv --force
```

---

## Global options

All commands accept `--help` / `-h` for usage information:

```bash
surogate-agent --help
surogate-agent chat --help
surogate-agent skills --help
surogate-agent skills files add --help
```

---

## Directory layout reference

```
./skills/               User-authored skill definitions
  └── <skill-name>/
      ├── SKILL.md      Required — defines the skill
      └── helper.*      Optional — prompts, schemas, templates

./workspace/            Developer scratch area (not shipped with skills)
  └── <skill-name>/
      └── draft.md

./sessions/             Per-chat user workspaces
  └── <session-id>/
      ├── input.csv     Input placed by user
      └── report.md     Output written by agent
```

Override the default locations using `--skills-dir`, `--workspace-dir`, `--sessions-dir` flags or the corresponding `SUROGATE_*` environment variables when using the [REST API](./api.md).

---

## Skill SKILL.md format

```markdown
---
name: skill-name          # kebab-case; required
description: One-liner    # max 1024 chars; required
role-restriction: developer  # "developer", "user", or omit for all roles
version: 0.1.0            # informational
allowed-tools: read_file write_file execute   # space-separated string
---

# Natural-language instructions

The agent follows these instructions when this skill is active.
Helper files in this directory can be read with `read_file`.
```

**`allowed-tools` values:**

| Tool | Description |
|------|-------------|
| `read_file` | Read a file from the filesystem |
| `write_file` | Write a file to the filesystem |
| `edit_file` | Edit a file in-place |
| `glob` | Find files matching a pattern |
| `grep` | Search file contents |
| `execute` | Run a shell command (activates `LocalShellBackend`) |
