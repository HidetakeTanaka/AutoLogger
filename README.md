# AutoLogger – AI-Assisted Automatic Logging for Python

AutoLogger is an AI-assisted framework for **automatic log position selection** in Python source code.
It combines **AST-based static analysis**, **baseline heuristics**, and **large language models (LLMs)** to suggest logging positions and evaluate them against **manually curated gold annotations**.

This project is inspired by **UniLog (ICSE 2024)** and was developed as part of the
**Software Engineering course at Hochschule Rhein-Waal (WS 2025/26)**.

---

## Key Features

* AST-based extraction of candidate logging positions
* Heuristic and random baseline implementations
* LLM-based log position selection:

  * OpenAI GPT-4.1-mini
  * OpenAI GPT-5.1
  * Google Flan-T5 (base / large)
* Unified **position-only evaluation pipeline**

  * TP / FP / FN
  * Precision, Recall, F1 (macro & micro)
* Cross-platform reproducibility (Windows / macOS / Linux)
* Fully documented gold annotation policy and JSON schema

---

## Installation & Environment Setup

**Using a virtual environment is mandatory!**

AutoLogger is developed and evaluated using **Conda (Python 3.11)**.
Please follow the unified setup guide: **`docs/environment_setup.md`** 

This guide covers:

* Windows / macOS / Linux
* API key setup (OpenAI & HuggingFace)
* Cloud Resilience Lab compatibility

---

## Project Structure

```text
AutoLogger/
├── baselines/
│   ├── baseline_heuristic.py
│   ├── baseline_random.py
│   ├── *.json                    # baseline outputs
├── dataset/
│   ├── gold_logs/
│   │    ├── gold_logs_scriptXX/  # per-script gold annotations
│   └── raw/                      # sample1.py, sample2.py and FLAN-T5 outputs
├── docs/
│   ├── environment_setup.md
│   ├── evaluation_guide.md
│   ├── handwriting_goldjson_guide.md
│   └── schema.md
├── eval/
│   ├── convert_llm_for_eval.py
│   ├── eval_message_quality.py   
│   └── eval_positions.py
├── llm/
│   └── autologger.py
├── parser/
│   └── parser.py
├── results/
│   └── *.json                    # evaluation outputs
├── scripts/
│   └── scriptXX.py               # input programs
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Evaluation Workflow (High-Level)

1. **Parse source code** to extract candidate log positions
2. **Manually create gold annotations** from candidates
3. **Run baseline or LLM-based selection**
4. **Evaluate predicted positions** against gold annotations

Detailed, step-by-step instructions are provided in: **`docs/evaluation_guide.md`** 

---

## Gold Annotation Policy

Gold annotations are **manually written** and **strictly constrained** to parser-generated candidates.

* Gold files are **not generated automatically**
* LLMs may assist annotation, but final decisions are human-defined
* This ensures fair and reproducible evaluation

Detailed rules, examples, and formatting guidelines are documented in: **`docs/handwriting_goldjson_guide.md`** 

---

## JSON Schema

All intermediate and final JSON files follow a shared schema across modules:

* Parser output
* Baseline predictions
* LLM predictions
* Gold annotations
* Evaluation inputs

The authoritative schema is defined in: **`docs/schema.md`** 

---

## Example Commands

### Run parser

```bash
python parser/parser.py scripts/script31.py
```

### Run GPT-4.1-mini

```bash
python llm/autologger2.py \
  scripts/script31.candidates.json \
  --provider openai \
  --model gpt-4.1-mini
```

### Run evaluation

```bash
python eval/eval_positions.py \
  dataset/gold_logs/gold_logs_script31 \
  results/llm_gpt41mini_script31.json
```

---

## Evaluation Metrics

AutoLogger evaluates **log position accuracy only**.

* **True Positive (TP)**: predicted position exists in gold
* **False Positive (FP)**: predicted position not in gold
* **False Negative (FN)**: gold position not predicted

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1-score  = 2 * (Precision * Recall) / (Precision + Recall)
```

Both **macro-averaged** and **micro-averaged** metrics are reported.

---

## Authors & Contributions

Developed by **Group 7 (Software Engineering WS 2025/26, HSRW)**:

* **Hidetake Tanaka (34254)** — AST parser, evaluation pipeline, integration, coordination
* **Khushi Trivedi (35726)** — LLM integration, runtime validation, Cloud Resilience Lab testing
* **Farhana Easmin Mithila (32050)** — Baseline implementations
* **Farjana Akter (33565)** — Evaluation framework and dataset coordination

---

## License

MIT License.

---