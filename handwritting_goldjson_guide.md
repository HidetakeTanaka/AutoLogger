# AutoLogger Gold Annotation Guidelines  
## _Manual creation of `gold.json` from `candidate.json`_

This document explains how to **manually write `gold.json` files** from `candidate.json` files for the AutoLogger project.

The goals...:

- Keep the **JSON format exactly consistent** with the existing example `script31_gold.json`.
- **Write a log entry for (almost) every candidate** in `candidate.json`.
- Use **clear, human-readable log messages** that a real developer would find useful.  
  (You may use an AI assistant to help draft messages.)

---

## 1. Target `gold.json` format

Each `gold.json` file must follow this structure:

```json
{
  "file": "<SCRIPT_NAME>.py",
  "logs": [
    {
      "line": <line_number>,
      "kind": "<entry|return|exception>",
      "level": "<DEBUG|INFO|ERROR|WARNING>",
      "message": "<human-readable log message>"
    }
  ]
}
```

### 1.1. `file`

* Use just the **basename** of the Python file (no path):

  ```json
  "file": "script31.py"
  ```

### 1.2. `logs` array

Each element in `logs` corresponds to **one logging statement** that you consider “gold” (ground truth).

Fields:

* `line`

  * The **line number** in the Python source where the log should be inserted.
  * **Use the `line` from the corresponding candidate** (do not adjust it manually).

* `kind`
  One of:

  * `"entry"` – function entry log
  * `"return"` – log for a return / result
  * `"exception"` – log in an exception handler (error path)

* `level`
  One of:

  * `"DEBUG"`
  * `"INFO"`
  * `"WARNING"`
  * `"ERROR"`

* `message`

  * A concise, human-readable English log message.
  * Should include the function and/or class name when helpful.

---

## 2. Input: `candidate.json` recap

A `candidate.json` looks roughly like:

```jsonc
{
  "file": "scripts/script31.py",
  "candidates": [
    {
      "kind": "func_entry",
      "line": 36,
      "end_line": 36,
      "function": "is_suspicious",
      "class_name": "QuizAttempt",
      "code": "def is_suspicious(self, threshold: float = 0.8) -> bool:",
      "vars_in_scope": ["self", "threshold"],
      "why": "function entry",
      "severity_hint": "DEBUG"
    },
    {
      "kind": "return_stmt",
      "line": 41,
      "end_line": 41,
      "function": "is_suspicious",
      "class_name": "QuizAttempt",
      "code": "return self.score_ratio > threshold",
      "vars_in_scope": ["self", "threshold"],
      "why": "return statement",
      "severity_hint": "INFO"
    },
    {
      "kind": "exception_handler_entry",
      "line": 99,
      "end_line": 99,
      "function": "load_attempts",
      "class_name": null,
      "code": "except ...",
      "vars_in_scope": ["attempts", "path", "raw", "score", "duration", "max_score"],
      "why": "exception handler entry",
      "severity_hint": "ERROR"
    }
  ]
}
```

You will manually turn **each candidate** (or almost each) into a log entry in `gold.json`.

---

## 3. Overall workflow

For each `scriptXX.py`:

1. Open `scriptXX.candidates.json`.
2. For **each candidate** in `"candidates"`:

   1. Decide the `kind` (`entry` / `return` / `exception`) for `gold.json`.
   2. Decide the `level` (`DEBUG` / `INFO` / `ERROR` / `WARNING`).
   3. Write a **message** that fits the function and context.
3. Collect all log entries into:

   ```json
   {
     "file": "scriptXX.py",
     "logs": [ ... ]
   }
   ```

### Important rule!

> **By default, create a `logs` entry for every candidate** in `candidate.json`.

You may only skip a candidate if it is **clearly trivial and useless** (e.g., a pure getter with no logic). However, this should be rare!

---

## 4. Mapping from candidate kinds to `gold.kind`

Use the following mapping when converting from `candidate.kind` to `gold.kind`:

| `candidate.kind`                         | `gold.kind`   |
| ---------------------------------------- | ------------- |
| `"func_entry"`                           | `"entry"`     |
| `"before_return"` / `"return_stmt"`      | `"return"`    |
| `"except"` / `"exception_handler_entry"` | `"exception"` |

If additional candidate kinds appear later, map them to whichever of `"entry"`, `"return"`, or `"exception"` is closest — and keep this mapping consistent for all scripts.

---

## 5. Choosing `level`

Use these default rules unless `severity_hint` says otherwise:

1. **Function entry logs**

   * `gold.kind == "entry"`
   * → `level = "DEBUG"`

2. **Return / result logs**

   * `gold.kind == "return"`
   * → `level = "INFO"`

3. **Exception / error logs**

   * `gold.kind == "exception"`
   * → `level = "ERROR"`

4. **Warnings (optional)**

   * Use `"WARNING"` only if the candidate corresponds to a degraded but not fatal case
     (e.g., invalid input that is skipped but does not crash the program).
   * If unsure, prefer `"ERROR"` for exception handlers and `"INFO"` for normal returns.

If a candidate has `severity_hint`, you may use it as a suggestion, but keep the overall scheme above consistent.

---

## 6. Writing `message` – style guide

You may use an AI assistant to help draft messages, but keep them:

* Concise
* Consistent
* Meaningful for debugging

### 6.1. Function entry logs (`kind: "entry"`)

**Pattern:**

* With class:
  `Entering <ClassName>.<function_name>`
* Without class:
  `Entering <function_name>`

**Examples:**

```json
{
  "line": 36,
  "kind": "entry",
  "level": "DEBUG",
  "message": "Entering QuizAttempt.is_suspicious"
}
```

```json
{
  "line": 76,
  "kind": "entry",
  "level": "DEBUG",
  "message": "Entering load_attempts"
}
```

### 6.2. Return logs (`kind: "return"`)

Return logs should describe **what is being returned**.

**Pattern:**

* With class:
  `Returning <something> in <ClassName>.<function_name>`
* Without class:
  `Returning <something> in <function_name>`

`<something>` should be a short description of the returned value or meaning, e.g.:

* `suspicious flag`
* `user summary`
* `list of suspicious users`
* `parsed attempts`
* `result`
* `score ratio`

**Examples:**

```json
{
  "line": 41,
  "kind": "return",
  "level": "INFO",
  "message": "Returning suspicious flag in QuizAttempt.is_suspicious"
}
```

```json
{
  "line": 100,
  "kind": "return",
  "level": "INFO",
  "message": "Returning parsed attempts from load_attempts"
}
```

```json
{
  "line": 118,
  "kind": "return",
  "level": "INFO",
  "message": "Returning user summary in summarize_user"
}
```

If you’re not sure what the value is, you can fall back to a generic description:

* `"Returning result in <function_name>"`

But descriptive names are preferred.

### 6.3. Exception logs (`kind: "exception"`)

Exception logs should clearly describe:

* **What failed** (operation / function)
* **Where** (function name)

**Pattern:**

* `Failed to <do something> in <function_name>`
* `Error while <doing something> in <function_name>`
* `Unexpected error in <function_name>`

**Examples:**

```json
{
  "line": 99,
  "kind": "exception",
  "level": "ERROR",
  "message": "Failed to parse an attempt entry in load_attempts"
}
```

```json
{
  "line": 144,
  "kind": "exception",
  "level": "ERROR",
  "message": "Failed to load attempts in interactive_menu"
}
```

```json
{
  "line": 171,
  "kind": "exception",
  "level": "ERROR",
  "message": "Unexpected error in interactive_menu loop"
}
```

If you are unsure what exactly failed, use a generic but meaningful phrase such as:

* `"Unexpected error in <function_name>"`

---

## 7. Line number rules

* **Always use** `candidate.line` as the `line` in `gold.json`.
* Do **not** adjust the line number manually, even if you personally would prefer to log on a slightly different line.
* The instrumentation and evaluation scripts depend on this alignment.

Example mapping:

```jsonc
// candidate
{
  "kind": "func_entry",
  "line": 36,
  "function": "is_suspicious",
  "class_name": "QuizAttempt",
  ...
}

// gold
{
  "line": 36,
  "kind": "entry",
  "level": "DEBUG",
  "message": "Entering QuizAttempt.is_suspicious"
}
```

---

## 8. Coverage rule: which candidates get logs?

> **Default rule: write a `gold` log for every candidate found in `candidate.json`.**

That means:

* Every `func_entry` → one `entry` log.
* Every `return_stmt` / `before_return` → one `return` log.
* Every `exception_handler_entry` / `except` → one `exception` log.

Only skip a candidate when:

* The function or code is clearly trivial **and** a real developer would almost never log there
  (e.g., a tiny getter with no logic at all).
* These should be rare exceptions; document them in comments if needed.

---

## 9. Example: from candidates to gold

Given these candidates (simplified):

```jsonc
{
  "file": "scripts/script31.py",
  "candidates": [
    {
      "kind": "func_entry",
      "line": 36,
      "function": "is_suspicious",
      "class_name": "QuizAttempt"
    },
    {
      "kind": "return_stmt",
      "line": 41,
      "function": "is_suspicious",
      "class_name": "QuizAttempt"
    },
    {
      "kind": "func_entry",
      "line": 76,
      "function": "load_attempts",
      "class_name": null
    },
    {
      "kind": "exception_handler_entry",
      "line": 99,
      "function": "load_attempts",
      "class_name": null
    },
    {
      "kind": "return_stmt",
      "line": 100,
      "function": "load_attempts",
      "class_name": null
    }
  ]
}
```

A valid `gold.json` is:

```json
{
  "file": "script31.py",
  "logs": [
    {
      "line": 36,
      "kind": "entry",
      "level": "DEBUG",
      "message": "Entering QuizAttempt.is_suspicious"
    },
    {
      "line": 41,
      "kind": "return",
      "level": "INFO",
      "message": "Returning suspicious flag in QuizAttempt.is_suspicious"
    },
    {
      "line": 76,
      "kind": "entry",
      "level": "DEBUG",
      "message": "Entering load_attempts"
    },
    {
      "line": 99,
      "kind": "exception",
      "level": "ERROR",
      "message": "Failed to parse an attempt entry in load_attempts"
    },
    {
      "line": 100,
      "kind": "return",
      "level": "INFO",
      "message": "Returning parsed attempts from load_attempts"
    }
  ]
}
```

This matches the previously generated `script31_gold.json` format.

---

## 10. Practical tips

* You **can and should** use an AI assistant to help draft `message` texts:

  * Provide the function name, class name, and candidate code.
  * Ask for a short log message following the patterns in this guide.
* Keep naming **consistent** across the file:

  * Use the exact function names in messages (`load_attempts`, `interactive_menu`, etc.).
  * Use similar phrasing for similar roles (`Returning <thing> in <function>`).
* If you are unsure between two messages, prefer the one that:

  * Mentions the function name.
  * Makes it clear what is happening (what is being returned / what failed).

---
