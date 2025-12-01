#!/usr/bin/env bash
set -e

# ================================
# AutoLogger - Full Pipeline
# ================================
# NOTE: This is a skeleton. You will fill it later
# when parser, baselines, and LLM modules are ready.

# 1. Run parser
# python parser/parser.py dataset/raw_scripts/ > results/parser_output.json

# 2. Run baseline heuristic
# python baselines/baseline_heuristic.py results/parser_output.json > results/baseline_heuristic.json

# 3. Run random baseline
# python baselines/baseline_random.py results/parser_output.json > results/baseline_random.json

# 4. Run LLM-based autologger
# python autologger/autologger.py results/parser_output.json > results/llm_logs.json

# 5. Evaluate baseline heuristic
# python eval/eval_positions.py dataset/gold_logs/ results/baseline_heuristic.json

# 6. Evaluate random baseline
# python eval/eval_positions.py dataset/gold_logs/ results/baseline_random.json

# 7. Evaluate LLM logs
# python eval/eval_positions.py dataset/gold_logs/ results/llm_logs.json
