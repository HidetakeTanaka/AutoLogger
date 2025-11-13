import json
from pathlib import Path

INPUT_FILE = "baselines/parser_output.json"          
OUTPUT_FILE = "baselines/results_heuristic.json"     


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


def choose_log_level(kind: str) -> str:
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

    # 1. Load parser output JSON
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    file_path = data.get("file", "UNKNOWN")
    functions = data.get("functions", [])

    logs = []

    # 2. Process functions
    for func in functions:
        func_name = func.get("name", "<unknown>")
        candidates = func.get("candidates", [])

        # If parser gave no candidates, guess start/end positions
        if not candidates:
            start = func.get("start_line")
            end = func.get("end_line")

            if start is not None:
                candidates.append({"kind": "entry", "line": start})
            if end is not None:
                candidates.append({"kind": "return", "line": end})

        # Create log entries
        for cand in candidates:
            line = cand.get("line")
            kind = cand.get("kind", "other")

            if line is None:
                continue

            logs.append({
                "line": line,
                "level": choose_log_level(kind),
                "message": build_log_message(func_name, kind),
                "kind": kind,
                "function": func_name
            })

    # 3. Write output JSON
    output = {
        "file": file_path,
        "baseline_type": "heuristic",
        "logs": logs
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Heuristic baseline completed.")
    print(f"Output saved to: {OUTPUT_FILE}")



if __name__ == "__main__":
    run_heuristic()