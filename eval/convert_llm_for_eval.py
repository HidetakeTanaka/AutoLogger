import json
import sys
import re
from pathlib import Path

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def infer_level_from_log_code(log_code: str) -> str:
    m = re.search(r"logging\.([a-zA-Z]+)\s*\(", log_code)
    if not m:
        return "INFO"
    return m.group(1).upper()

def map_kind(kind: str) -> str:
    # normalize to lower-case to be safe
    k = (kind or "").lower()

    # function entry
    if k in  ("func_entry", "entry"):
        return "entry"
    
    # returns
    if k in  ("before_return", "return_stmt", "return"):
        return "return"
    
    # exceptions / handlers
    if k in ("exception_handler_entry", "except", "exception"):
        return "exception"

    # default: treat as entry or generic event
    # depending on your policy; here we pick "entry" to match gold schema
    # return "entry" instead of return "event"
    return "entry"

def convert(llm_path: Path, out_path: Path):
    data = load_json(llm_path)
    file_name = data.get("file", "")

    logs_out = []
    for log in data["logs"]:
        line = log.get("lineno")
        kind_raw = log.get("kind", "")
        log_code = log.get("log_code", "")

        logs_out.append({
            "line": line,
            "kind": map_kind(kind_raw),
            "level": infer_level_from_log_code(log_code),
            "message": log_code
        })

    out = {
        "file": file_name,
        "logs": logs_out
    }

    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote converted LLM predictions to {out_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_llm_for_eval.py <llm_logs.json> <output.json>")
        sys.exit(1)

    llm_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    convert(llm_path, out_path)
