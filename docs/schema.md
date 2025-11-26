# AutoLogger JSON Schema (Integration Version)

This document describes the JSON formats used by all modules in AutoLogger:

- Parser (`parser/`)
- Baselines (`baselines/`)
- LLM (`llm/`)
- Dataset (`dataset/gold_logs/`)
- Evaluation (`eval/`)

---

## 1. Gold Logs (Ground Truth)

Location: `dataset/gold_logs/scriptX_gold.json`

Example:

```json
{
  "file": "script1.py",
  "logs": [
    {
      "line": 1,
      "kind": "entry",
      "level": "INFO",
      "message": "Entering to_celsius"
    },
    {
      "line": 3,
      "kind": "except",
      "level": "ERROR",
      "message": "Exception in to_celsius"
    }
  ]
}

