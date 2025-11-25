import json
from pathlib import Path

INPUT_FILE = "baselines/parser_output.json"
OUTPUT_FILE = "baselines/results_heuristic.json"


def normalize_kind(raw_kind: str) -> str:
    """Map parser kinds to simpler kinds used by the baseline."""
    if raw_kind == "func_entry":
        return "entry"
    if raw_kind == "before_return":
        return "return"
    # "except" and others we leave as-is
    return raw_kind


def build_log_message(function_name: str, kind: str) -> str:
    if kind == "entry":
        return f"Entering {function_name}"
    elif kind == "return":
        return f"Exiting {function_name}"
    elif kind == "except":
        return f"Exception in {function_name}"
    elif kind == "io":
        return f"I/O operation in {function_name}"
    else:
        return f"Event in {function_name}"


def choose_log_level(kind: str, severity_hint: str | None = None) -> str:
    """Use severity_hint from parser if possible, otherwise simple rules."""
    if severity_hint in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        return severity_hint

    if kind == "entry":
        return "INFO"
    if kind == "return":
        return "DEBUG"
    if kind == "except":
        return "ERROR"
    if kind == "io":
        return "INFO"
    return "INFO"


def run_heuristic():
    input_path = Path(INPUT_FILE)
    output_path = Path(OUTPUT_FILE)

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    file_path = data.get("file", "UNKNOWN")
    candidates = data.get("candidates", [])

    logs = []

    # We now loop directly over the parser's candidates
    for cand in candidates:
        raw_kind = cand.get("kind", "other")
        kind = normalize_kind(raw_kind)
        line = cand.get("line")
        if line is None:
            continue

        func_name = cand.get("function", "<unknown>")
        severity_hint = cand.get("severity_hint")

        logs.append({
            "line": line,
            "level": choose_log_level(kind, severity_hint),
            "message": build_log_message(func_name, kind),
            "kind": kind,
            "function": func_name,
        })

    output = {
        "file": file_path,
        "baseline_type": "heuristic",
        "logs": logs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("Heuristic baseline completed.")
    print(f"Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    run_heuristic()
