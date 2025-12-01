# parser.py(AST Parser for AutoLogger) – README

This document explains how to use the AST parser (`parser.py`) in the AutoLogger project.
It provides example commands, usage in Python code, and an overview of the data format returned by the parser.

---

## Overview

The AST parser detects candidate positions in Python code where logging statements could be inserted.
It outputs structured `LoggingCandidate` objects (or JSON via CLI) that are used by:

* LLM Integration module
* Baseline heuristic module
* Dataset generation module

Main API:

```python
from parser import extract_candidates
```

CLI usage:

```bash
python3 parser/parser.py <file.py>
```

---

## Recommended file location

This README should be placed inside the `parser/` directory:

```
AutoLogger/
  parser/
    parser.py
    schema.py
    README.md   ← place this file here
```

This makes it easy for team members to find documentation close to the module.

---

## CLI Usage (Terminal)

Use the parser directly from the terminal to generate `.candidates.json` files.

### Example:

```bash
cd AutoLogger
python3 parser/parser.py dataset/raw/sample1.py
python3 parser/parser.py dataset/raw/sample2.py
```

Example output:

```
✅ Parsed sample2.py -> sample2.candidates.json
Found 9 candidates in sample2.py
```

The generated JSON file will appear next to the source file:

```
dataset/raw/sample2.candidates.json
```

---

## Python API Usage (For LLM / Baseline modules)

You can use the parser programmatically:

```python
from parser import extract_candidates

source = open("dataset/raw/sample1.py").read()
candidates = extract_candidates(source, file_path="sample1.py")

for c in candidates:
    print(c.kind, c.line, c.code)
```

This returns a list of `LoggingCandidate` objects.

---

## Output Structure (LoggingCandidate)

Each candidate has the following fields:

```json
{
  "kind": "func_entry",           // type of candidate
  "line": 10,
  "end_line": 10,
  "function": "process_data",
  "class_name": null,
  "code": "def process_data(x):",
  "vars_in_scope": ["x", "result"],
  "why": "function entry",
  "severity_hint": "DEBUG"
}
```

These fields are consumed by:

* LLM prompts
* Baseline heuristic placement rules
* Evaluation scripts

---

## Candidate Types

The parser currently detects:

* **func_entry** → First executable line in a function
* **before_return** → Before a return statement
* **except** → First line inside an except block

Future improvements: loop entry, after-call, more exception types

---

## Extending the Parser

The parser can be extended by adding more `visit_*` methods in `parser.py`, such as:

* `visit_For`
* `visit_While`
* `visit_Call`

To add a new candidate type:

1. Implement a visitor method
2. Create a new `LoggingCandidate` object
3. Append it to `self.candidates`

---

## Contribution Guide

Before opening a Pull Request:

1. Make sure the parser runs correctly:

   ```bash
   python3 parser/parser.py dataset/raw/sample1.py
   ```
2. Confirm that `.candidates.json` files are generated without errors
3. Update your feature branch from `main`
4. Only delete branches you created yourself

---

## Notes

If you have any questions about using or extending the parser, contact the AST developer: 
Hidetake.Tanaka@hsrw.org


---

This README will help LLM, baseline, and dataset teammates integrate the parser smoothly!
