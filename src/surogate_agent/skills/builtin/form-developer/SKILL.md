---
name: form-developer
description: >
  Generates formio.js JSON form schemas from natural-language descriptions.
  Used by skill-developer to embed user-input forms in skills that require
  structured data collection.
role-restriction: developer
version: 0.1.0
allowed-tools: write_file read_file
---

# Form Developer

You are equipped with the **form-developer** skill.  Your job is to produce
valid **formio.js v4 JSON schemas** from natural-language field descriptions
and to save them as `.json` helper files inside the target skill.

---

## Output format

Every schema you produce is a JSON object with a single top-level key:

```json
{ "components": [ ...component objects... ] }
```

Save it as `skills/<skill-name>/<form-name>.json` using `write_file`.  The
filename must be kebab-case and end with `.json` (e.g. `input-form.json`).

---

## Component reference

### Text fields

```json
{ "type": "textfield", "key": "firstName", "label": "First Name",
  "placeholder": "Enter your first name",
  "validate": { "required": true, "minLength": 1, "maxLength": 255 } }

{ "type": "textarea", "key": "notes", "label": "Notes", "rows": 4,
  "validate": { "required": false } }

{ "type": "email", "key": "email", "label": "Email Address",
  "validate": { "required": true } }

{ "type": "phoneNumber", "key": "phone", "label": "Phone Number" }

{ "type": "password", "key": "secret", "label": "Password" }
```

### Numeric

```json
{ "type": "number", "key": "quantity", "label": "Quantity",
  "validate": { "required": true, "min": 0, "max": 9999 } }

{ "type": "currency", "key": "amount", "label": "Amount (USD)",
  "currency": "USD", "validate": { "required": true, "min": 0 } }
```

### Date / time

```json
{ "type": "datetime", "key": "dueDate", "label": "Due Date",
  "format": "yyyy-MM-dd", "enableTime": false,
  "validate": { "required": true } }

{ "type": "datetime", "key": "meetingAt", "label": "Meeting Time",
  "format": "yyyy-MM-dd HH:mm", "enableTime": true }
```

### Selection

```json
{ "type": "select", "key": "priority", "label": "Priority",
  "dataSrc": "values",
  "data": { "values": [
    { "label": "Low",    "value": "low"    },
    { "label": "Medium", "value": "medium" },
    { "label": "High",   "value": "high"   }
  ]},
  "validate": { "required": true } }

{ "type": "radio", "key": "decision", "label": "Decision",
  "values": [
    { "label": "Yes", "value": "yes" },
    { "label": "No",  "value": "no"  }
  ],
  "inline": true,
  "validate": { "required": true } }

{ "type": "selectboxes", "key": "tags", "label": "Tags",
  "values": [
    { "label": "Urgent",   "value": "urgent"   },
    { "label": "Review",   "value": "review"   },
    { "label": "Approved", "value": "approved" }
  ] }
```

### Boolean

```json
{ "type": "checkbox", "key": "agree", "label": "I confirm the data above is correct",
  "validate": { "required": true } }
```

### File upload

**Always set `"storage": "base64"`** — this encodes the file in the browser and
includes it in the form submission.  The server decodes it, saves it to the
session's input-files folder, and returns the workspace path in `form_data`.

```json
{ "type": "file", "key": "attachments", "label": "Attachments",
  "storage": "base64", "multiple": true,
  "validate": { "required": false } }

{ "type": "file", "key": "document", "label": "Upload Document",
  "storage": "base64", "multiple": false,
  "validate": { "required": true } }
```

After submission the agent receives the saved paths in `form_data["key"]`
(e.g. `["sessions/<id>/report.pdf"]`) and can read or process those files
exactly like files uploaded through `request_files`.

### Layout

Use `columns` to place fields side-by-side.  Column `width` values must sum
to 12 (Bootstrap grid units):

```json
{ "type": "columns", "key": "nameCols",
  "columns": [
    { "width": 6, "components": [
        { "type": "textfield", "key": "firstName", "label": "First Name" }
    ]},
    { "width": 6, "components": [
        { "type": "textfield", "key": "lastName",  "label": "Last Name"  }
    ]}
  ] }
```

Use `panel` to group related fields under a titled section:

```json
{ "type": "panel", "key": "contactPanel", "title": "Contact Details",
  "components": [
    { "type": "email",       "key": "email", "label": "Email" },
    { "type": "phoneNumber", "key": "phone", "label": "Phone" }
  ] }
```

Use `htmlelement` for static labels, headings, or instructions:

```json
{ "type": "htmlelement", "key": "intro", "tag": "p",
  "className": "text-muted",
  "content": "Please complete all required fields before submitting." }
```

---

## Validation reference

Every component accepts a `validate` object:

| Field | Type | Meaning |
|-------|------|---------|
| `required` | bool | Field must have a value |
| `minLength` | int | Min string length |
| `maxLength` | int | Max string length |
| `min` | number | Minimum numeric value |
| `max` | number | Maximum numeric value |
| `pattern` | string | JS regex pattern (without slashes) |
| `custom` | string | JS expression: `valid = value > 0 ? true : 'Must be positive'` |

---

## Complete example — calculator form

```json
{
  "components": [
    {
      "type": "htmlelement",
      "key": "instructions",
      "tag": "p",
      "content": "Enter two numbers to calculate their sum."
    },
    {
      "type": "columns",
      "key": "numberCols",
      "columns": [
        {
          "width": 6,
          "components": [{
            "type": "number",
            "key": "numberA",
            "label": "First number",
            "validate": { "required": true }
          }]
        },
        {
          "width": 6,
          "components": [{
            "type": "number",
            "key": "numberB",
            "label": "Second number",
            "validate": { "required": true }
          }]
        }
      ]
    }
  ]
}
```

---

## Rules

- Every component **must** have a unique `key` in camelCase (used as the
  submitted data field name — the agent reads `form_data["key"]` after submit).
- Use `"validate": { "required": true }` on fields the skill needs; leave
  others optional.
- File-upload components **must** include `"storage": "base64"` — any other
  storage mode will not work in this environment.
- Do **not** add a submit button component — the UI provides its own.
- After generating the schema, save it with `write_file` to
  `skills/<skill-name>/<form-name>.json` and tell the caller the filename.
- Output compact, valid JSON — no trailing commas, no comments.
