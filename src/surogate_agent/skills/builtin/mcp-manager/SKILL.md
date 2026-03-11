---
name: mcp-manager
description: >
  Meta-skill for registering, managing, and removing MCP (Model Context Protocol)
  servers from GitHub repos. Clones repos, installs deps, probes tools, writes
  startup scripts, and registers servers into the persistent registry.
  Available only to developer sessions.
role-restriction: developer
version: 0.1.0
allowed-tools: write_file edit_file read_file ls glob grep write_todos execute task
---

# MCP Manager

You help the developer register, manage, and remove MCP servers.

Your system context (file access rules) tells you the exact absolute paths for:

- **Path 3 — MCP workspace**: your working area — clone repos, venvs, probe scripts.
- **Path 4 — MCP scripts**: the production registry — `start.sh` files the server runs + `registry.json`.

Always substitute the actual absolute paths shown in your system context. Never guess or hardcode them.

---

## ABSOLUTE RULE: never ask, never suggest — just execute all steps

**You MUST complete every step of the register flow without pausing, asking for confirmation,
or printing a "now you can register it with…" hint.** The developer asked you to register —
do it. Any message like:

- "If you want this added to the registry…"
- "To register, run: …"
- "Would you like me to add this to registry.json?"
- "register it with: name: … command: …"
- "If you want me to finalize it into the MCP registry entry…"
- "tell me what command/fields your registry expects"
- "some setups require specifying stdio vs http explicitly"
- "If you want, I can run a quick probe invocation to confirm…"
- Any offer to optionally run, test, or verify after the fact
- Any question about transport, fields, or registry format

…is a violation of this rule. Execute step 7 (write registry.json) and step 8 (reply with
three lines) immediately after probing. No prompts. No suggestions. No interactive flow.

**You already have everything you need after step 6:**
- `<name>` — inferred from the repo URL
- `<transport>` — determined in step 4
- `<port>` — determined in step 4 (0 for stdio)
- `<tools>` — from the probe output in step 6
- `<start_command>` and `<cwd>` — from the start.sh you wrote in step 5

There is nothing left to ask. Write registry.json immediately.

---

## CRITICAL: use `execute` for ALL filesystem operations on paths 3 and 4

The `ls`, `glob`, `read_file`, and `write_file` tools are sandboxed to the session workspace.
They **silently return empty results or fail** for paths outside it — even if the files exist.
Every single operation on the MCP workspace or MCP scripts path — listing, reading, writing,
creating directories, cloning — MUST go through the `execute` tool.

| What you want to do | How to do it |
|---|---|
| List a directory | `execute ls -la <path>` |
| Read a file | `execute cat <path>` |
| Search file contents | `execute grep -ri "pattern" <path>` |
| Check file/dir exists | `execute test -e <path> && echo exists \|\| echo missing` |
| Create directories | `execute mkdir -p <path>` |
| Write a file | `execute` with `cat > <path> << 'MARKER' ... MARKER` |
| Clone a repo | `execute git clone <url> <dest>` |
| Run Python | `execute python3 <args>` |

---

## Register flow

Execute every step in order without asking for confirmation. Infer the registry `<name>` from
the repo URL or directory (last path segment, lowercased, spaces/underscores replaced with hyphens).
Do not stop after writing `start.sh` — that alone does nothing.
The server only becomes available after step 8 (registry write).

### Step 1 — Ensure directories and clone the repo

```bash
mkdir -p <MCP_WORKSPACE>/repos <MCP_WORKSPACE>/venvs <MCP_SCRIPTS>/<name>
```

If the repo is not already cloned:
```bash
git clone <repo_url> <MCP_WORKSPACE>/repos/<name>
```

If already cloned, skip the clone and continue.

### Step 2 — Read the README and source to understand the server

```bash
cat <MCP_WORKSPACE>/repos/<name>/README.md 2>/dev/null || true
ls <MCP_WORKSPACE>/repos/<name>/
```

From the README and source determine:
- The main entry point script (e.g. `server.py`, `main.py`, `word_mcp_server.py`)
- Whether SSE/HTTP transport is supported (grep for `--transport`, `sse`, `fastmcp`, `uvicorn`)
- Required environment variables

```bash
grep -ri "transport\|sse\|uvicorn\|fastmcp\|--port" <MCP_WORKSPACE>/repos/<name>/ --include="*.py" -l 2>/dev/null | head -5
```

**CRITICAL — check for stdout pollution in the entry point:**

Any `print()` call (without `file=sys.stderr`) in the entry point or any module it imports at
startup will corrupt the stdio JSON-RPC channel, causing `Failed to parse JSONRPC message`
errors. You MUST check for and fix these before registering:

```bash
grep -n "^print\|^\s*print(" <MCP_WORKSPACE>/repos/<name>/<entry_point>.py | head -20
```

For every startup `print(...)` found (logging config loaded, transport announced, server
starting, etc.), patch it in-place to use stderr:

```bash
# Example: fix print("Transport: stdio") → print("Transport: stdio", file=sys.stderr)
sed -i 's/^\(\s*print(\(.*\)\)$/\1, file=sys.stderr)/' <MCP_WORKSPACE>/repos/<name>/<entry_point>.py
```

Or read the file, fix the prints manually with `execute`, and write it back.
After patching, verify no bare `print(` remain at module level.

### Step 3 — Create isolated venv and install dependencies

**NEVER use `uv venv --clear` or `--clear` flag** — that wipes the environment on every run.
Create the venv once; on subsequent calls it already exists.

```bash
VENV=<MCP_WORKSPACE>/venvs/<name>
REPO=<MCP_WORKSPACE>/repos/<name>

if [ ! -f "$VENV/bin/python" ]; then
  uv venv "$VENV"
fi
source "$VENV/bin/activate"

# Install deps — try uv first, fall back to pip
if [ -f "$REPO/requirements.txt" ]; then
  uv pip install -r "$REPO/requirements.txt" || pip install -r "$REPO/requirements.txt"
elif [ -f "$REPO/pyproject.toml" ]; then
  uv pip install -e "$REPO" || pip install -e "$REPO"
fi
```

### Step 4 — Determine transport

**First**, grep the source — this is instant and never hangs:
```bash
grep -ri "transport\|sse\|uvicorn\|fastmcp\|--port\|add_argument.*port" <MCP_WORKSPACE>/repos/<name>/ --include="*.py" 2>/dev/null | grep -v "Binary" | head -20 || echo "no-sse-found"
```

**Then** confirm by running `--help` with stdin closed and a hard time limit so a
stdio server that ignores `--help` never blocks:
```bash
source <MCP_WORKSPACE>/venvs/<name>/bin/activate
timeout 5 python <MCP_WORKSPACE>/repos/<name>/<entry_point>.py --help < /dev/null 2>&1 | grep -i "transport\|sse\|port" || echo "no-sse-flag"
```

`< /dev/null` closes stdin so a stdio MCP server immediately gets EOF instead of
blocking.  `timeout 5` kills it after 5 seconds regardless.  A non-zero exit or
"no-sse-flag" means stdio only.

- **Default: always use `transport: stdio`, set `port: 0`.**
- Only use `transport: sse` if the server has NO stdio mode at all (i.e. it only starts
  as an HTTP/SSE server and has no stdin/stdout MCP entrypoint). If the server supports
  both, always prefer stdio.

To find a free port:
```bash
python3 -c "
import socket
for p in range(8101, 8200):
    with socket.socket() as s:
        if s.connect_ex(('localhost', p)) != 0:
            print(p); break
"
```

### Step 5 — Write `start.sh` into MCP scripts

The startup script must be **self-healing**: if the repo or venv are missing (e.g. after
export/import to a new machine or workspace wipe), the script clones the repo and rebuilds
the venv automatically before starting the server. This makes the script portable.

**CRITICAL — substitute literal values, never shell variables:**
The placeholders `<MCP_WORKSPACE>`, `<name>`, `<repo_url>`, `<entry_point>` must be replaced
with their **actual absolute values** before writing the file. The resulting script must
contain hardcoded paths like `/data/mcp-workspace/repos/my-server`, not shell variable
references like `$MCP_WORKSPACE` or `$NAME`. The script runs without any special environment
variables set — only the variables it defines itself are available. Using `$MCP_WORKSPACE`
will cause `set -u` to abort with "unbound variable".

Example of **WRONG** (env var references — will fail with "unbound variable"):
```
REPO="$MCP_WORKSPACE/repos/$NAME"   ← WRONG
git clone "$REPO_URL" "$REPO"       ← WRONG
```

Example of **CORRECT** (hardcoded absolute paths):
```
REPO="/data/mcp-workspace/repos/my-server"   ← CORRECT
git clone "https://github.com/org/my-server" "$REPO"   ← CORRECT
```

Both requirements apply **at the same time**: hardcode literal paths AND include the
self-healing block. The self-healing block uses `$REPO` and `$VENV` which are shell variables
defined two lines above — those are fine. What is forbidden is using `$MCP_WORKSPACE`,
`$NAME`, `$REPO_URL` etc. that the script itself never defines.

For **stdio** servers — substitute real values for every `<placeholder>` before writing:
```bash
cat > <MCP_SCRIPTS>/<name>/start.sh << 'STARTSH'
#!/usr/bin/env bash
set -euo pipefail
REPO="<MCP_WORKSPACE>/repos/<name>"
VENV="<MCP_WORKSPACE>/venvs/<name>"

# Self-heal: clone repo if missing
if [ ! -d "$REPO/.git" ]; then
  echo "Repo missing — cloning..." >&2
  mkdir -p "$(dirname "$REPO")"
  git clone "<repo_url>" "$REPO" >&2
fi

# Self-heal: create venv and install deps if missing
if [ ! -f "$VENV/bin/python" ]; then
  echo "Venv missing — creating..." >&2
  mkdir -p "$(dirname "$VENV")"
  uv venv "$VENV" >&2
  source "$VENV/bin/activate"
  if [ -f "$REPO/requirements.txt" ]; then
    uv pip install -r "$REPO/requirements.txt" >&2 || pip install -r "$REPO/requirements.txt" >&2
  elif [ -f "$REPO/pyproject.toml" ]; then
    uv pip install -e "$REPO" >&2 || pip install -e "$REPO" >&2
  fi
else
  source "$VENV/bin/activate"
fi

export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
exec python "$REPO/<entry_point>.py"
STARTSH
chmod +x <MCP_SCRIPTS>/<name>/start.sh
```

The result after substitution must look like this concrete example — every placeholder
replaced with a real absolute value, self-healing block intact:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPO="/data/mcp-workspace/repos/office-word-mcp-server"
VENV="/data/mcp-workspace/venvs/office-word-mcp-server"

# Self-heal: clone repo if missing
if [ ! -d "$REPO/.git" ]; then
  echo "Repo missing — cloning..." >&2
  mkdir -p "$(dirname "$REPO")"
  git clone "https://github.com/example/office-word-mcp-server" "$REPO" >&2
fi

# Self-heal: create venv and install deps if missing
if [ ! -f "$VENV/bin/python" ]; then
  echo "Venv missing — creating..." >&2
  mkdir -p "$(dirname "$VENV")"
  uv venv "$VENV" >&2
  source "$VENV/bin/activate"
  if [ -f "$REPO/requirements.txt" ]; then
    uv pip install -r "$REPO/requirements.txt" >&2 || pip install -r "$REPO/requirements.txt" >&2
  elif [ -f "$REPO/pyproject.toml" ]; then
    uv pip install -e "$REPO" >&2 || pip install -e "$REPO" >&2
  fi
else
  source "$VENV/bin/activate"
fi

export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
exec python "$REPO/word_mcp_server.py"
```

For **SSE** servers:
```bash
cat > <MCP_SCRIPTS>/<name>/start.sh << 'STARTSH'
#!/usr/bin/env bash
set -euo pipefail
REPO="<MCP_WORKSPACE>/repos/<name>"
VENV="<MCP_WORKSPACE>/venvs/<name>"

# Self-heal: clone repo if missing
if [ ! -d "$REPO/.git" ]; then
  echo "Repo missing — cloning..." >&2
  mkdir -p "$(dirname "$REPO")"
  git clone <repo_url> "$REPO" >&2
fi

# Self-heal: create venv and install deps if missing
if [ ! -f "$VENV/bin/python" ]; then
  echo "Venv missing — creating..." >&2
  mkdir -p "$(dirname "$VENV")"
  uv venv "$VENV" >&2
  source "$VENV/bin/activate"
  if [ -f "$REPO/requirements.txt" ]; then
    uv pip install -r "$REPO/requirements.txt" >&2 || pip install -r "$REPO/requirements.txt" >&2
  elif [ -f "$REPO/pyproject.toml" ]; then
    uv pip install -e "$REPO" >&2 || pip install -e "$REPO" >&2
  fi
else
  source "$VENV/bin/activate"
fi

export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
exec python "$REPO/<entry_point>.py" --transport sse --port <port>
STARTSH
chmod +x <MCP_SCRIPTS>/<name>/start.sh
```

### Step 6 — Probe the tools

Write a probe script that works for both transports:
```bash
cat > <MCP_WORKSPACE>/<name>/probe.py << 'PROBE'
#!/usr/bin/env python3
import asyncio, json, sys

async def probe_stdio(cmd_parts):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=cmd_parts[0], args=cmd_parts[1:])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            result = await s.list_tools()
            return [{"name": t.name, "description": t.description or ""} for t in result.tools]

async def probe_sse(url):
    from mcp.client.sse import sse_client
    from mcp import ClientSession
    async with sse_client(url) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            result = await s.list_tools()
            return [{"name": t.name, "description": t.description or ""} for t in result.tools]

async def main():
    try:
        if sys.argv[1].startswith("http"):
            tools = await probe_sse(sys.argv[1])
        else:
            tools = await probe_stdio(sys.argv[1:])
        print(json.dumps(tools))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

asyncio.run(main())
PROBE
```

Run the probe:

For **stdio**: activate the venv first, then:
```bash
source <MCP_WORKSPACE>/venvs/<name>/bin/activate
python <MCP_WORKSPACE>/<name>/probe.py bash <MCP_SCRIPTS>/<name>/start.sh 2>&1
```

For **SSE**: start the daemon, wait, then probe:
```bash
bash <MCP_SCRIPTS>/<name>/start.sh < /dev/null > <MCP_WORKSPACE>/<name>/server-probe.log 2>&1 &
sleep 3
python <MCP_WORKSPACE>/<name>/probe.py http://localhost:<port>/sse 2>&1
```

Capture the JSON output — this is the `tools` value for step 7.

If the probe fails or the `mcp` package is missing, install it:
```bash
source <MCP_WORKSPACE>/venvs/<name>/bin/activate
uv pip install mcp || pip install mcp
```
Then re-run the probe.

### Step 7 — Write `registry.json`

This is the step that makes the server visible in the UI and injects its tools into chat sessions.
**Do not skip this step.**

```bash
python3 - << 'PYEOF'
import json
from pathlib import Path
from datetime import datetime, timezone

MCP_SCRIPTS = Path("<MCP_SCRIPTS>")
registry_path = MCP_SCRIPTS / "registry.json"

tools = <paste_tools_json_from_probe_output_here>

entry = {
    "name": "<name>",
    "repo_url": "<repo_url>",
    "start_command": f"bash {MCP_SCRIPTS}/<name>/start.sh",
    "cwd": str(MCP_SCRIPTS),
    "transport": "<sse_or_stdio>",
    "host": "localhost",
    "port": <port_or_0_for_stdio>,
    "tools": tools,
    "registered_at": datetime.now(timezone.utc).isoformat(),
}

entries = json.loads(registry_path.read_text()) if registry_path.exists() else []
entries = [e for e in entries if e["name"] != entry["name"]]  # upsert
entries.append(entry)
registry_path.write_text(json.dumps(entries, indent=2))
print(f"OK: registered {entry['name']} ({entry['transport']}, {len(entry['tools'])} tools)")
PYEOF
```

Verify:
```bash
python3 -c "
import json; from pathlib import Path
r = Path('<MCP_SCRIPTS>/registry.json')
e = next(x for x in json.loads(r.read_text()) if x['name'] == '<name>')
print(e['name'], e['transport'], len(e['tools']), 'tools — OK')
"
```

For SSE servers, also start the daemon now so it is immediately available without a server restart:
```bash
nohup bash <MCP_SCRIPTS>/<name>/start.sh > <MCP_WORKSPACE>/<name>/server.log 2>&1 &
sleep 2
echo "SSE server PID $!"
```

### Step 8 — Reply

Reply with exactly three lines:
```
Registered: <name>
Transport:  <sse|stdio>
Tools (<N>): <comma-separated tool names>
```
Nothing else. No usage instructions. No explanations. No code examples.

---

## Delete flow

```bash
python3 - << 'PYEOF'
import json, shutil
from pathlib import Path

name = "<name>"
registry_path = Path("<MCP_SCRIPTS>/registry.json")
if registry_path.exists():
    entries = [e for e in json.loads(registry_path.read_text()) if e["name"] != name]
    registry_path.write_text(json.dumps(entries, indent=2))
script_dir = Path("<MCP_SCRIPTS>") / name
if script_dir.exists():
    shutil.rmtree(script_dir)
print(f"Removed {name} from registry")
PYEOF
```

The workspace clone at `<MCP_WORKSPACE>/repos/<name>/` and the venv at `<MCP_WORKSPACE>/venvs/<name>/` are left intact so re-registration is fast.

---

## List flow

```bash
python3 -c "
import json; from pathlib import Path
r = Path('<MCP_SCRIPTS>/registry.json')
entries = json.loads(r.read_text()) if r.exists() else []
for e in entries:
    print(e['name'], e['transport'], len(e.get('tools', [])), 'tools')
"
```

---

## Non-negotiable rules

1. **`execute` for everything** — `ls`, `glob`, `read_file`, `write_file` cannot reach MCP paths. Always use `execute`.
2. **Never `uv venv --clear`** — that rebuilds the entire environment on every server start. Check `$VENV/bin/python` exists; skip creation if it does.
3. **Always complete all 8 steps** — stop.sh alone does nothing. The server is only visible after step 7 writes `registry.json`.
4. **Probe before registering** — get the real tool list from the running server. Do not invent tool names.
5. **uv first, pip fallback** — ignore what the repo README says about pip. Always try `uv pip install` first.
5b. **No sudo by default — add only on permission error** — when installing any package (pip, apt, yum, apk, etc.), run the command directly first. Only prepend `sudo` if the first attempt fails with a permission error. This handles both Docker (no sudo needed/available) and non-Docker (sudo required) environments correctly.
6. **stdio by default, always** — use `transport: stdio` unless the server has no stdio entrypoint whatsoever (HTTP-only server). If the server supports both, always choose stdio. Never use SSE just because it is available.
6b. **Never ask, never hint, never suggest** — infer the name, complete all 8 steps, and reply with exactly three lines. Phrases like "If you want this added to the registry…", "To register, run: name: … command: …", or any variant are forbidden. The developer asked you to register — just do it.
7. **Eliminate ALL stdout pollution before registering** — both the start.sh and the server's own Python code must never print to stdout. Check the entry point for bare `print(...)` calls and patch them to `print(..., file=sys.stderr)`. Any startup message on stdout (`Loading config`, `Transport: stdio`, `Server starting…`) breaks the JSON-RPC channel with `Failed to parse JSONRPC message` errors. Fix in Step 2 before writing start.sh.
8. **Hardcode all paths in start.sh — no env var placeholders** — replace every `<MCP_WORKSPACE>`, `<name>`, `<repo_url>`, `<entry_point>` with its actual absolute value before writing the file. The script runs with no special environment set; `$MCP_WORKSPACE`, `$NAME`, `$REPO_URL` are all unbound and will cause `set -u` to abort immediately.
8. **Never `echo` to stdout in a stdio start.sh** — stdout is the MCP JSON-RPC channel. Any non-JSON output (echo, printf, set -x traces) breaks the protocol. Redirect diagnostics to stderr: `echo "..." >&2`.
8. **Always add self-healing checks to start.sh** — every start.sh must check whether the repo (`$REPO/.git`) and venv (`$VENV/bin/python`) exist before starting. If either is missing, clone the repo and/or rebuild the venv inline. This makes the script work after export/import, workspace wipe, or first run on a new machine. All output from the healing steps must go to stderr.
9. **Reply with three lines only** — name, transport, tool list. No usage examples, no descriptions.
