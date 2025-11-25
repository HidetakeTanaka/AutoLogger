import json
import os
import sys
from typing import Dict, List, Any, Tuple


def load_gold_logs(gold_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    """Load all gold log files from a directory into a dict: file -> list of logs."""
    gold_by_file: Dict[str, List[Dict[str, Any]]] = {}

    for name in os.listdir(gold_dir):
        if not name.endswith("_gold.json"):
            continue
        path = os.path.join(gold_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        file_name = data["file"]
        gold_by_file[file_name] = data.get("logs", [])

    return gold_by_file


def load_predictions(pred_file: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load system predictions from a JSON file.

    Supports two formats:

    1) Aggregated (multiple files):

       {
         "files": [
           {
             "file": "script1.py",
             "logs": [ ... ]
           },
           {
             "file": "script2.py",
             "logs": [ ... ]
           }
         ]
       }

    2) Single-file baseline output ( heuristic baseline writes):

       {
         "file": "script1.py",
         "baseline_type": "heuristic",
         "logs": [ ... ]
       }
    """
    with open(pred_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    pred_by_file: Dict[str, List[Dict[str, Any]]] = {}

    # Case 1: {"files": [ { "file": ..., "logs": [...] }, ... ]}
    if isinstance(data, dict) and "files" in data:
        for file_entry in data.get("files", []):
            file_name = file_entry["file"]
            pred_by_file[file_name] = file_entry.get("logs", [])

    # Case 2: {"file": "...", "logs": [...]}  (single-file baseline output)
    elif isinstance(data, dict) and "file" in data and "logs" in data:
        file_name = data["file"]
        pred_by_file[file_name] = data.get("logs", [])

    else:
        print("Unsupported prediction JSON format in", pred_file, file=sys.stderr)

    return pred_by_file


def match_logs(
    gold_logs: List[Dict[str, Any]],
    pred_logs: List[Dict[str, Any]],
    line_tolerance: int = 2,
) -> Tuple[int, int, int]:
    """
    Match predicted logs to gold logs.

    Returns:
      TP, FP, FN
    """
    gold_matched = [False] * len(gold_logs)
    tp = 0
    fp = 0

    for pred in pred_logs:
        pred_line = pred.get("line")
        pred_kind = pred.get("kind")
        if pred_line is None or pred_kind is None:
            # Skip malformed predictions
            continue

        found = False

        for i, gold in enumerate(gold_logs):
            if gold_matched[i]:
                continue
            gold_line = gold["line"]
            gold_kind = gold["kind"]

            if gold_kind == pred_kind and abs(pred_line - gold_line) <= line_tolerance:
                gold_matched[i] = True
                tp += 1
                found = True
                break

        if not found:
            fp += 1

    fn = gold_matched.count(False)
    return tp, fp, fn


def compute_metrics(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp > 0 else 0.0
    recall = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall > 0
        else 0.0
    )
    return precision, recall, f1


def main():
    if len(sys.argv) != 3:
        print("Usage: python eval_positions.py <gold_dir> <pred_file>")
        sys.exit(1)

    gold_dir = sys.argv[1]
    pred_file = sys.argv[2]

    gold_logs = load_gold_logs(gold_dir)
    pred_logs = load_predictions(pred_file)

    total_tp = total_fp = total_fn = 0

    for file_name, gold in gold_logs.items():
        pred = pred_logs.get(file_name, [])
        tp, fp, fn = match_logs(gold, pred)
        total_tp += tp
        total_fp += fp
        total_fn += fn

    precision, recall, f1 = compute_metrics(total_tp, total_fp, total_fn)

    print("==== AutoLogger Evaluation ====")
    print(f"TP = {total_tp}, FP = {total_fp}, FN = {total_fn}")
    print(f"Precision = {precision:.3f}")
    print(f"Recall    = {recall:.3f}")
    print(f"F1-score  = {f1:.3f}")


if __name__ == "__main__":
    main()

