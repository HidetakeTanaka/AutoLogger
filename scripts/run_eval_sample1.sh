#!/usr/bin/env bash
set -euo pipefail

# Always run from the project root (AutoLogger)
ROOT_DIR="$(cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "========================================"
echo " Running evaluation for sample1.py"
echo " Project root: $ROOT_DIR"
echo "========================================"
echo

RAW_DIR="dataset/raw"
BASELINES_DIR="baselines"
RESULTS_DIR="results"
GOLD_ALL_DIR="dataset/gold_logs"
GOLD_SAMPLE1_DIR="dataset/gold_logs_sample1"
EVAL_SCRIPT="eval/eval_positions.py"

mkdir -p "$RESULTS_DIR"
mkdir -p "$GOLD_SAMPLE1_DIR"

# Make sure we have a sample1-only gold folder
cp "$GOLD_ALL_DIR/sample1_gold.json" "$GOLD_SAMPLE1_DIR/sample1_gold.json"

########################################
# 1) Heuristic baseline
########################################
echo ">>> [1/6] Heuristic baseline (sample1)"

cp "$RAW_DIR/sample1.candidates.json" "$BASELINES_DIR/parser_output.json"
python3 "$BASELINES_DIR/baseline_heuristic.py"
cp "$BASELINES_DIR/results_heuristic.json" "$RESULTS_DIR/baseline_sample1.json"

python3 "$EVAL_SCRIPT" "$GOLD_SAMPLE1_DIR" "$RESULTS_DIR/baseline_sample1.json"
echo

########################################
# 2) Random baseline
########################################
echo ">>> [2/6] Random baseline (sample1)"

cp "$RAW_DIR/sample1.candidates.json" "$BASELINES_DIR/parser_output.json"
python3 "$BASELINES_DIR/baseline_random.py"
cp "$BASELINES_DIR/results_random.json" "$RESULTS_DIR/baseline_random_sample1.json"

# Optional path normalization
sed -i '' 's|"dataset/raw/sample1.py"|"sample1.py"|' "$RESULTS_DIR/baseline_random_sample1.json" || true

python3 "$EVAL_SCRIPT" "$GOLD_SAMPLE1_DIR" "$RESULTS_DIR/baseline_random_sample1.json"
echo

########################################
# Helper function for LLM runs
########################################
run_llm() {
  local provider="$1"   # "openai" or "flan"
  local model="$2"      # e.g. "gpt-4.1-mini" or "google/flan-t5-base"
  local out_json="$3"   # results file path

  echo ">>> Running LLM ($provider, $model) on sample1"

  # 1) Generate predictions
  python3 autologger.py \
    "$RAW_DIR/sample1.candidates.json" \
    --provider "$provider" \
    --model "$model"

  # 2) Convert to eval format
  python3 eval/convert_llm_for_eval.py \
    "$RAW_DIR/sample1.candidates.logs.json" \
    "$out_json"

  # 3) Evaluate
  python3 "$EVAL_SCRIPT" "$GOLD_SAMPLE1_DIR" "$out_json"
  echo
}

########################################
# 3) LLM: gpt-4.1-mini
########################################
echo ">>> [3/6] LLM (gpt-4.1-mini, OpenAI)"
run_llm "openai" "gpt-4.1-mini" "$RESULTS_DIR/llm_gpt41mini_sample1.json"

########################################
# 4) LLM: gpt-5.1
########################################
echo ">>> [4/6] LLM (gpt-5.1, OpenAI)"
run_llm "openai" "gpt-5.1" "$RESULTS_DIR/llm_gpt51_sample1.json"

########################################
# 5) LLM: flan-t5-base
########################################
echo ">>> [5/6] LLM (flan-t5-base, HuggingFace)"
run_llm "flan" "google/flan-t5-base" "$RESULTS_DIR/flan_t5base_sample1.json"

########################################
# 6) LLM: flan-t5-large
########################################
echo ">>> [6/6] LLM (flan-t5-large, HuggingFace)"
run_llm "flan" "google/flan-t5-large" "$RESULTS_DIR/flan_t5large_sample1.json"

echo "========================================"
echo " All sample1 evaluations finished."
echo " Check JSON files under: $RESULTS_DIR"
echo "========================================"
