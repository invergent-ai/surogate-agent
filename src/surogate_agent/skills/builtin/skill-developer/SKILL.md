---
name: skill-developer
description: >
  Meta-skill for creating, editing, and managing agent skills through
  conversation. Available only to developer-role sessions. Use this skill
  when the user asks to create a new skill, modify an existing skill,
  list available skills, or understand the skill format.
role-restriction: developer
version: 0.1.0
allowed-tools: write_file edit_file read_file ls glob write_todos
---

# Skill Developer — Instructions

You are equipped with the **skill-developer meta-skill**.
Your job is to help the developer author, iterate on, and manage agent skills
through natural conversation.  Multiple skills may be developed in parallel;
each one has its own isolated locations for definition files and working files.

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
├── prompt.md          ← optional: reusable prompt template
├── schema.json        ← optional: expected input/output structure
└── config.yaml        ← optional: tunable parameters
```

Helper files are never loaded automatically — SKILL.md explicitly tells the
agent to `read_file("prompt.md")` etc.

### SKILL.md format

```markdown
---
name: <kebab-case-name>
description: <one or two sentences, max 1024 chars>
role-restriction: developer | user   # omit to allow all roles
version: 0.1.0
allowed-tools: tool_name other_tool   # space-delimited string
---

# Skill Title

Instructions the agent follows when this skill is active.
```

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
Call `write_todos`:
- [ ] Draft SKILL.md body (iterate in workspace if complex)
- [ ] Write final SKILL.md to skills directory
- [ ] Write finalized helper files to skills directory
- [ ] Confirm with developer

### Step 4 — Write the skill definition
Once the draft is ready, write to the **skills** directory (not workspace):

```
write_file  skills/<skill-name>/SKILL.md
write_file  skills/<skill-name>/prompt.md    ← only finalized helpers
```

**Binary / external helper files (templates, images, data files, etc.):**
If any such file exists in `workspace/<skill-name>/` and is required by the skill,
**copy it directly into `skills/<skill-name>/` without asking the developer**.
This is always the correct action — the developer chose to build the skill around it.
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
  [write_file: skills/csv-to-report/SKILL.md]       ← skill definition
  [write_file: skills/csv-to-report/prompt.md]      ← finalized template

  Skill 'csv-to-report' created.
  Skill files : skills/csv-to-report/
  Dev scratch : workspace/csv-to-report/
```
