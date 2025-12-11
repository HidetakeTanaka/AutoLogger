# Evaluation for AutoLogger

This folder contains scripts to evaluate the quality of log placement.

## Input

- Gold logs: `dataset/gold_logs/*.json`
  - Format described in `dataset/README.md` and `docs/schema.md`.
- System predictions: a single JSON file (e.g. `results/baseline_heuristic.json`)
  - Format described in `docs/schema.md` under "System Output".

## Metrics

For each file and for all files combined we compute:

- **True Positives (TP)**: predicted log matches a gold log
  - same `kind`
  - line difference ≤ 2 (`|pred_line - gold_line| ≤ 2`)
- **False Positives (FP)**: predicted logs that do not match any gold log.
- **False Negatives (FN)**: gold logs that were not predicted by the system.

From these we compute:

- **Precision** = TP / (TP + FP)
- **Recall** = TP / (TP + FN)
- **F1-score** = harmonic mean of precision and recall.

## Usage

Example:

```bash
python eval/eval_positions.py dataset/gold_logs/ results/baseline_heuristic.json
