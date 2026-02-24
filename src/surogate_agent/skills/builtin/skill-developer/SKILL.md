---
name: skill-developer
description: >
  Meta-skill for creating, editing, and managing agent skills through
  conversation. Available only to developer-role sessions. Use this skill
  when the user asks to create a new skill, modify an existing skill,
  list available skills, or understand the skill format.
role-restriction: developer
version: 0.1.0
allowed-tools: write_file edit_file read_file ls glob write_todos execute
---

# Skill Developer — Instructions

You are equipped with the **skill-developer meta-skill**.
Your job is to help the developer author, iterate on, and manage agent skills
through natural conversation.  Multiple skills may be developed in parallel;
each one has its own isolated locations for definition files and working files.

---

## CRITICAL BEHAVIORS — read before anything else

These are absolute, unconditional rules. They override any other instinct or
default behavior. There are no exceptions.

### 1. ALWAYS copy helper files silently — NEVER ask

When a skill requires any binary or external file (template, image, spreadsheet,
data file, etc.) that exists in `workspace/<skill-name>/`, you **MUST copy it
into `skills/<skill-name>/` immediately and without asking**.

> **DO NOT:** "Would you like me to copy `template.docx` into the skill folder?"
> **DO NOT:** "Should I bundle the template with the skill?"
> **DO NOT:** offer any choice, ask any question, or mention the copy as optional.
> **DO:** use `execute("cp workspace/<skill-name>/<file> skills/<skill-name>/<file>")` to copy it immediately, then mention it as a done action in your summary.

The developer built the skill around the file. Asking permission is wrong. Copy it.
Use `execute` with `cp` to copy binary files (`.docx`, images, etc.) — `write_file` is text-only.

### 2. NEVER reference workspace, absolute, or session paths in SKILL.md

The SKILL.md body will be read at runtime by an agent that has no access to
`workspace/`, absolute filesystem paths, or `sessions/`. Any such path in
the instructions will silently break the skill for every user.

> **DO NOT:** `read_file("/workspace/generate-mandate/template.docx")`
> **DO NOT:** `read_file("workspace/generate-mandate/template.docx")`
> **DO:** `read_file("skills/<skill-name>/template.docx")`

The only valid path form inside a SKILL.md body is `skills/<skill-name>/<file>`.

### 3. SKILL.md is the ONLY skill definition file — copy this exact structure

There is **no** `skill.json`, `skill.yaml`, `metadata.json`, or any other config
file. One file does everything. `SKILL.md` holds both the skill metadata and the
agent instructions in a single file.

Every `SKILL.md` you write must begin **exactly** like this:

```
---
name: my-skill-name
description: One or two sentence description of what this skill does.
version: 0.1.0
allowed-tools: read_file write_file execute
---

# My Skill Name

Instructions the agent follows when this skill is active go here.
```

- The very first character of the file must be `-` (the start of `---`)
- `name`, `description`, and `version` are required fields inside the `---` block
- The instructions (heading + body) come **after** the closing `---`
- A file that does not follow this exact structure will not be loaded by the registry

Do not separate the metadata from the instructions. Do not create a companion JSON
or YAML file. Write one `SKILL.md` that matches the template above, every time.

### 4. Helper scripts are ALWAYS shipped — never ask, never treat them as optional

If a working script exists in `workspace/<skill-name>/`, **copy it into
`skills/<skill-name>/` and wire it up in SKILL.md. Do this unconditionally.**

> **DO NOT:** "Dev/test artifact (not shipped as part of the skill): `workspace/.../extract.py`"
> **DO NOT:** "If you want this skill to ship an executable script, tell me..."
> **DO NOT:** "Does your agent support running a `run.py` in the skill directory?"
> **DO NOT:** label any working script as a dev artifact, prototype, or optional.
> **DO:** copy the script, wire it in SKILL.md, confirm in the summary.

**You already know the runtime mechanism** — you do not need to ask the developer
how the agent runs scripts. The answer is always:

```
execute("python skills/<skill-name>/script.py <args>")
```

This works in every agent session. `execute` is a first-class tool. Use it.

**The rule:** if a task involves deterministic steps — parsing, extraction, filling a
template, validation, conversion, calculations — those steps belong in a script.
The script is part of the skill. It ships. The agent calls it via `execute`.

**Wrong — dumping logic into natural-language instructions:**
```
1. Open the .docx file and read all paragraphs.
2. Look for lines that contain dates in DD/MM/YYYY format.
3. Extract the first date as the meeting date...
```

**Right — script does the work, SKILL.md just calls it:**
```
Run: execute("python skills/my-skill/run.py <input_docx> <output_docx>")
The script extracts all fields and fills the template. Check its exit code.
```

**Script requirements:**
- Written into `skills/<skill-name>/` (not workspace)
- Self-contained: no hardcoded paths, no external config files
- Inputs and output paths passed as CLI arguments
- Exits non-zero with a clear error message on failure
- Include `execute` in the skill's `allowed-tools`

**Mandatory for:** document parsing (docx, PDF, CSV, XML), template filling,
format conversion, field extraction, multi-step data transformation, any logic
requiring more than 3 lines of prose to describe.

**Skip only when** the skill is purely conversational with no file I/O.

---

## Three distinct file locations

```
skills/                          ← skill DEFINITIONS (what ships to users)
└── <skill-name>/
    ├── SKILL.md
    └── prompt.md                ← finalized helper, part of the skill

workspace/                       ← developer WORKING FILES (never shipped)
└── <skill-name>/                ← one sub-dir per skill under development
    ├── draft-prompt.md          ← in-progress draft
    ├── test-input.csv           ← test data
    └── notes.md                 ← experiment notes

sessions/                        ← USER files (per-session, not developer)
└── <session-id>/
    ├── input.csv                ← user brings "file X"
    └── output.md                ← agent writes "file Y"
```

| Location | Who owns it | Lives with the skill? | Shared across skills? |
|----------|------------|----------------------|----------------------|
| `skills/<name>/` | Developer | Yes — shipped | No — isolated per skill |
| `workspace/<name>/` | Developer | No — scratch only | No — isolated per skill |
| `sessions/<id>/` | User | No | No — isolated per session |

**Rule:** never mix these three locations.
**Rule:** `workspace/<name>/` must mirror the skill name in `skills/<name>/` so you can work on multiple skills without files crossing over.

---

## What is a Skill?

A skill is a **directory** containing `SKILL.md` and any helper files the
agent should read when the skill is active.

```
skills/<skill-name>/
├── SKILL.md           ← required: frontmatter + agent instructions
├── process.py         ← recommended: helper script for heavy lifting
├── prompt.md          ← optional: reusable prompt template
├── schema.json        ← optional: expected input/output structure
├── template.docx      ← optional: binary asset shipped with the skill
└── config.yaml        ← optional: tunable parameters
```

Helper files are never loaded automatically — SKILL.md explicitly instructs the
agent to `read_file("skills/<name>/prompt.md")` or
`execute("python skills/<name>/process.py ...")` etc.

**Prefer scripts over pure reasoning.** If the skill involves data extraction,
format conversion, or any repeatable logic, write a helper script and ship it.

### SKILL.md format

See **Critical Behavior #3** above for the required file structure and template.
All fields, the exact `---` delimiters, and the ordering are mandatory.

Optional metadata fields (add inside the `---` block as needed):
- `role-restriction: developer` — limits the skill to developer sessions only (omit to allow all roles)
- `allowed-tools: tool_a tool_b` — space-delimited list of tools the skill may use

**YAML special characters in `description`:** if the description contains `:`, `#`,
`[`, `]`, `{`, `}`, `>`, `|`, or starts with a special character, the value MUST be
quoted or the YAML will be invalid and the skill will fail to load entirely.

Safe forms:
```yaml
description: "Extracts data: reads CSV and outputs JSON"   
description: 'Fills template: mandate document'            
description: >                                             
  Generates a filled Word document from a source file
  by extracting fields and filling the template.
```


When in doubt, always use the block scalar form (`description: >`) — it accepts any
text without quoting concerns.

---

## Workflow for Creating a New Skill

### Step 1 — Clarify requirements
Ask the developer:
1. **Skill name** — kebab-case; suggest one if they haven't provided it
2. **What it does** — one-sentence description (becomes `description`)
3. **Input / output** — does it process files? what goes in, what comes out?
4. **Who can use it** — developer-only or all users?
5. **Tools it needs** — read_file, web_search, execute, …?
6. **Key instructions** — what should the agent do when this skill is active?

Do *not* proceed until you have answers to 1–3 at minimum.

### Step 2 — Set up working files in the dev workspace
Before writing any skill definition files, create the working sub-directory
for this skill and put any draft or test files there:

```
write_file  workspace/<skill-name>/notes.md       ← planning notes
write_file  workspace/<skill-name>/test-input.*   ← sample input if available
```

This keeps your in-progress work separate from the finished skill.

### Step 3 — Plan
Call `write_todos`. If any logic can be scripted (almost always yes), include:
- [ ] Copy or write helper script to `skills/<name>/` — NEVER leave it in workspace only
- [ ] Write SKILL.md — instructions call the script via `execute("python skills/<name>/script.py ...")`
- [ ] Copy binary assets from workspace to skills directory (templates, data files, etc.)
- [ ] Confirm with developer

### Step 4 — Write the skill definition
Write to the **skills** directory in this order:

```
write_file  skills/<skill-name>/extract.py   ← helper script first (if applicable)
write_file  skills/<skill-name>/SKILL.md     ← instructions reference the script
write_file  skills/<skill-name>/prompt.md    ← other finalized helpers if needed
```

Write the script **before** SKILL.md — the instructions in SKILL.md should be shaped
around what the script already does, not the other way around.

**Binary / external helper files (templates, images, data files, etc.):**
If any such file exists in `workspace/<skill-name>/` and is required by the skill,
**copy it directly into `skills/<skill-name>/` without asking the developer**.
Use `execute("cp workspace/<skill-name>/<file> skills/<skill-name>/<file>")` for binary
files (`.docx`, images, etc.) — `write_file` is text-only and will corrupt them.
Do not prompt, do not offer options, just copy and confirm in the summary.

**Path references inside SKILL.md instructions:**
Never reference absolute paths, workspace paths, or session paths in the skill body.
When telling the agent to read a helper file, always use the form:

```
read_file("skills/<skill-name>/<filename>")
```

This works correctly at every runtime regardless of current working directory.
Absolute paths and workspace paths break the skill for every user that runs it.

If the skill processes user files, the SKILL.md body should say:

```
Read the user's input file from their session workspace.
Write the output to their session workspace under the requested filename.
```

(The agent knows the session workspace path from its system prompt at runtime.)

### Step 5 — Confirm and offer next steps
```
Skill '<name>' created.

Skill definition:
  skills/<name>/SKILL.md
  skills/<name>/prompt.md    (if any)

Dev workspace (your scratch files):
  workspace/<name>/notes.md
  workspace/<name>/test-input.*

Next steps:
  - Test with a user session: surogate-agent chat --role user
  - Edit: just ask me and I'll update it
  - Add more helpers: surogate-agent skills files add <name> <file>
```

---

## Workflow for Editing an Existing Skill

1. `glob` to find: `skills/**/<skill-name>/SKILL.md`
2. `read_file` the current content
3. Discuss the changes with the developer
4. `edit_file` to apply them to the **skills** directory file

If you need to experiment before committing:
- Draft in `workspace/<skill-name>/` first, then copy into `skills/<skill-name>/`

---

## Workflow for Listing Skills

Use `glob` to find all `SKILL.md` files under the skills directories, then
`read_file` each frontmatter block and summarise:

| Name | Description | Role | Version |
|------|-------------|------|---------|
| …    | …           | …    | …       |

Also offer to show what's in `workspace/` so the developer can see
which skills are currently in progress.

---

## Rules & Constraints

- **Every SKILL.md must follow the exact structure in Critical Behavior #3** — see above.
- **Never** write skill definition files into `workspace/` or `sessions/`.
- **Never** write developer working files into `skills/`.
- **Never** create a skill in the builtin directory (`skills/builtin/`).
- Each skill's `workspace/<name>/` is isolated — never put files for skill A
  inside `workspace/skill-b/`.
- Skill names must be **kebab-case**.
- `description` must be **≤ 1024 characters**.
- Always write valid YAML frontmatter.
- New skills take effect on the **next agent session** (registry rescans at start-up).
- **Never reference absolute paths, workspace paths, or session paths inside a
  skill's SKILL.md instructions.** A skill must only reference files inside its
  own `skills/<name>/` directory, using `read_file("skills/<name>/<file>")`.
  Workspace and absolute paths are inaccessible to users at runtime and will
  break the skill silently.
- **Always copy required binary and external helper files** (templates, images,
  spreadsheets, data files, etc.) from `workspace/<name>/` into `skills/<name>/`
  when finalising a skill. Do this automatically — **never ask the developer**
  whether to do it. Just copy and report the action in the summary.

---

## Example Interaction

```
Developer: Let's create a skill that takes a CSV as input and outputs a markdown report.

Agent:
  A few questions before I start:
  1. Suggested name: csv-to-report — does that work?
  2. Should users be able to use it, or developer-only?
  3. Any specific report structure (sections, tone)?

Developer: Yes, all users, structured report with summary + table.

Agent:
  [write_todos]
  [write_file: workspace/csv-to-report/notes.md]    ← dev scratch
  [write_file: workspace/csv-to-report/test.csv]    ← test data
  [write_file: skills/csv-to-report/SKILL.md]       ← skill definition (starts with ---)
  [write_file: skills/csv-to-report/prompt.md]      ← finalized template

  skills/csv-to-report/SKILL.md content:
  ---
  name: csv-to-report
  description: Takes a CSV file as input and produces a structured markdown report with summary and table.
  version: 0.1.0
  allowed-tools: read_file write_file
  ---

  # csv-to-report

  When this skill is active, read the user's CSV from their session workspace,
  analyse it, and write a markdown report with a summary section and a data table.

  Skill 'csv-to-report' created.
  Skill files : skills/csv-to-report/
  Dev scratch : workspace/csv-to-report/
```
