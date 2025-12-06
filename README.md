# AutoLogger
Automatic log generation system combining Python AST analysis and LLM-based reasoning (HSRW Software Engineering Project in WS2025/26).



## Structure
# Part B — LLM Integration Engineer
## AutoLogger Project

### Role
This module is responsible for integrating Large Language Models (LLMs) into the AutoLogger
pipeline. The goal of this component is to automatically generate meaningful Python logging
statements at locations identified by the parser.

This part focuses on:
- LLM API integration
- Prompt engineering
- Handling multiple LLM providers
- Safe fallbacks if API calls fail
- Producing standardized logging output in JSON format

---

## Objective

The goal of this module is to:
1. Read candidate log locations from `.candidates.json` files.
2. Construct prompts for Large Language Models.
3. Generate Python logging statements (using OpenAI GPT or Flan-T5).
4. Extract valid `logging.*(...)` statements from LLM output.
5. Output a structured `.logs.json` file for evaluation.

---

## File Description

### `autologger.py`

This script:
- Reads parser output JSON
- Builds prompts for each candidate
- Calls an LLM backend (OpenAI GPT or Flan-T5)
- Extracts valid Python logging statements
- Writes the final predictions to a `.logs.json` output file

---

## Supported LLM Providers

The implementation currently supports two LLM backends:

### 1. OpenAI Chat Models
Examples:
- `gpt-4.1`
- `gpt-4.1-mini`
- `gpt-5.1` (if available)

Uses OpenAI’s Chat Completion API.

### 2. Flan-T5 (via HuggingFace Inference API)
Examples:
- `google/flan-t5-large`
- `google/flan-t5-base`

Uses HuggingFace’s cloud-hosted inference API.

### Design Highlights

Modular backend selection (--provider)
Robust fallback to prevent failure on quota/timeouts
Single-line logging extraction enforcement
Provider-agnostic architecture for future expansion
Compatible with baseline and evaluation modules

### Future Improvements

Add Claude, Gemini, and Mistral as optional providers.
Improve prompt tuning to utilise variables better.
Add caching for repeated prompts.
Support structured logging formats (JSON logs).

Author
Role: LLM Integration Engineer
Contribution: Design, development and integration of LLM backend for AutoLogger.

### Error Handling

If:

API keys are missing

API quota is exhausted

Provider is unreachable

The system falls back to a simple heuristic log:

logging.info("AutoLogger: reached candidate in function foo")

This ensures the system never crashes and always produces output.


---

## Setup Instructions

### Step 1 — Install Python dependencies

```bash
pip install openai requests

### Step 2
Set API keys
For OpenAI:

Windows:

set OPENAI_API_KEY=your_openai_key


Mac/Linux:

export OPENAI_API_KEY=your_openai_key

For Flan-T5:

Windows:

set HUGGINGFACE_API_KEY=your_huggingface_key


Mac/Linux:

export HUGGINGFACE_API_KEY=your_huggingface_key

### Step 3
How to Run

How to Run
Using OpenAI GPT:
python autologger.py sample1.candidates.json --provider openai --model gpt-4.1-mini

Using Flan-T5:
python autologger.py sample1.candidates.json --provider flan --model google/flan-t5-large


Output file:

sample1.logs.json

### Output Example

Output Format

The output format is:

{
  "file": "dataset/raw/sample1.py",
  "logs": [
    {
      "candidate_id": 0,
      "lineno": 2,
      "col_offset": 0,
      "kind": "func_entry",
      "log_code": "logging.debug('Entering foo with x=%s, y=%s', x, y)"
    }
  ]
}








