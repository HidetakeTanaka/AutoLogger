import json
import random
from pathlib import Path


INPUT_FILE = "baselines/parser_output.json"
OUTPUT_FILE = "baselines/results_random.json"

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


def normalize_kind(raw_kind: str) -> str:
    """Match the same mapping used in the heuristic baseline."""
    if raw_kind == "func_entry":
        return "entry"
    if raw_kind == "before_return":
        return "return"
    return raw_kind  # "except" stays the same


def run_random_baseline():
    input_path = Path(INPUT_FILE)
    output_path = Path(OUTPUT_FILE)

    # Load parser output
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    file_path = Path(data.get("file", "UNKNOWN")).name
    candidates = data.get("candidates", [])

    logs = []

    # Fix seed so random baseline is reproducible
    random.seed(42)

    # Probability that we insert a log at each candidate
    probability = 0.30    # 30% chance

    for cand in candidates:
        raw_kind = cand.get("kind", "other")
        kind = normalize_kind(raw_kind)
        line = cand.get("line")
        func_name = cand.get("function", "<unknown>")

        # Skip if line is missing
        if line is None:
            continue

        # Randomly decide whether to insert a log here
        if random.random() <= probability:
            level = random.choice(LOG_LEVELS)
            message = f"Random log at line {line} in {func_name}"

            logs.append({
                "line": line,
                "level": level,
                "message": message,
                "kind": kind,
                "function": func_name,
            })

    # Build output JSON
    output = {
        "file": file_path,
        "baseline_type": "random",
        "seed": 42,
        "probability": probability,
        "logs": logs,
    }

    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("Random baseline completed.")
    print(f"Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    run_random_baseline()
