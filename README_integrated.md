# AutoLogger – Automatic Logging Insertion for Python Code
AutoLogger is an AI-assisted tool that automatically inserts Python logging statements
into source code. It combines **AST analysis**, **LLM-based reasoning**, and 
**baseline heuristics** to generate high-quality logging suggestions and evaluate them
against human-annotated gold standard data.

This project is inspired by **UniLog (ICSE 2024)** and developed as part of the
Software Engineering course at HSRW.



---


## Features
- Python **AST-based analysis** to extract candidate logging locations
- **Heuristic baseline** and **Random baseline** implementations
- **Multiple LLM backends:**
  - OpenAI GPT-4.1-mini
  - OpenAI GPT-5.1
  - Google Flan-T5 (base / large)
- **Unified evaluation pipeline with:**
  - True Positives (TP)
  - False Positives (FP)
  - False Negatives (FN)
  - Precision, Recall, F1-score
  - (Optional) Position accuracy metrics



---

# 1. Installation

## 1.1. Clone the Repository
```bash
git clone https://github.com/<your-username>/AutoLogger.git
cd AutoLogger

```



## 1.2. Create and Activate a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate     # macOS/Linux
venv\Scripts\activate        # Windows

```



## 1.3. Install Dependencies
```bash
pip install -r requirements.txt

```



## 1.4. Configure API Keys (we use OpenAI for GPT and HuggingFace for Flan-T5)
```bash
export OPENAI_API_KEY="your_key_here"
export HUGGINGFACE_API_KEY="your_key_here"

```



---

# 2. Project Structure

```bash
AutoLogger/
  ├── baselines/
  │     ├── baseline_heuristic.py
  │     ├── baseline_random.py
  │     └── results_*.json
  ├── parser/
  │     └── ast_parser.py
  ├── llm/
  │     ├── llm_openai.py
  │     ├── llm_flan.py
  │     └── llm_utils.py
  ├── dataset/
  │     ├── raw/                 # LLM output candidates
  │     └── gold/                # Human-annotated gold labels
  ├── results/
  ├── scripts/
  │     ├── run_eval_sample1.sh
  │     ├── run_eval_sample2.sh
  │     └── scriptXX.py
  └── README.md

```

---

# 3. Running Demo Evaluations
AutoLogger includes two demo scripts (sample1.py and sample2.py) to verify the full
pipeline.


## 3.1. Run Sample 1
```bash
cd scripts
./run_eval_sample1.sh

```


This will run the following proceduces...:
* Heuristic baseline
* Random baseline
* LLM (GPT-4.1-mini)
* LLM (GPT-5.1)
* LLM (Flan-T5 base)
* LLM (Flan-T5 large)

Outputs will be stored in:

```bash
baselines/
dataset/raw/
results/

```



## 3.2. Run Sample 2
```bash
./run_eval_sample2.sh

```
---

# 4. Understanding Evaluation Metrics
Each evaluation produces the following values:

**True Positives (TP):**<br>
The model inserted a log statement at a location that is also annotated in the gold labels.

**False Positives (FP):** <br>
The model inserted a log in a location that is not in the gold labels.

**False Negatives (FN)**: <br>
The model missed a gold-label location.

### Precision
```ini
Precision = TP / (TP + FP)
```
### Recall
```ini
Recall = TP / (TP + FN)
```
### F1-Score
```ini
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

All metrics are printed automatically in the console after each model/baseline finishes!

---

# 5. Output Files

## 5.1. Baseline outputs
```bash
baselines/results_heuristic.json
baselines/results_random.json

```

## 5.2. LLM raw predictions
```bash
dataset/raw/<filename>.candidates.logs.json

```

## 5.3. LLM converted predictions
```bash
results/llm_<model>_<script>.json

```

## 5.4. Final evaluation summaries
Printed in terminal and stored inside results/.
<br>

---

## 6. Extending the Evaluation to Larger Datasets
1. Place new Python source files inside:

```bash
dataset/source/
```

2. Create corresponding gold-label log files in:

```bash
dataset/gold/
```

3. Run the full evaluation:
```bash
./scripts/run_eval_dataset.sh
```
<br>

# 7. Troubleshooting
Q1. If no API key found like this below?: 
```bash
openai.error.AuthenticationError: No API key provided.

```

A1. Add your API key:
```bash
export OPENAI_API_KEY="your_key_here"
```
<br>
Q2. If HuggingFace model not available?<br>
A2. Install additional packages:

```bash
pip install transformers accelerate
```
<br>
Q3. If UTF-8 encoding issues on Windows? <br>
A3. Use this code below:

```bash
export PYTHONUTF8=1
```

---

# 8. Authors
Developed by Group 7 (Software Engineering WS2025/26, HSRW):

A: AST Parser Developer: Hidetake Tanaka(34254)

B: LLM Integration: Khushi

C: Baseline Implementations: Mithila

D: Dataset & Integration Testing: Zarin

---

# 9. License
MIT License.