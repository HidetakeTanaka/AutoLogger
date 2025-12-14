# AutoLogger – Cross-Platform Virtual Environment Setup Guide
(Conda + Terminal / PowerShell)

For **Windows, macOS, and Linux** users

---

## Goal of This Guide

This guide ensures that **everyone on the team uses the same Python environment**, so that:

- LLM evaluations produce identical results across machines
- dependencies do not conflict (`transformers`, `numpy`, `torch`, etc.)
- AutoLogger runs consistently for **baseline**, **GPT models**, and **Flan models**
- evaluation results (Precision / Recall / F1) are **reproducible and comparable**
- the system can be executed reliably on **university-managed machines**
  (e.g., Cloud Resilience Lab)

**Using a virtual environment is mandatory for scientific validity.**

---

## Step 1 — Install Anaconda or Miniconda (All OS)

If conda is not installed yet:

Download **Miniconda (recommended)**  
https://docs.conda.io/en/latest/miniconda.html

Install it and **restart your shell**:

- Windows → PowerShell
- macOS / Linux → Terminal

---

## Step 2 — Create the AutoLogger Conda Environment

Run the following command (same on all OS):

```bash
conda create -n autologger_env python=3.11 -y
````

Activate the environment:

```bash
conda activate autologger_env
```

You should now see something like:

```text
(autologger_env) ...
```

If not → **stop and fix this first**.

---

## Step 3 — Navigate to the AutoLogger Repository

Move into your cloned AutoLogger project folder.

### Windows example

```powershell
cd C:\Users\yourname\Documents\GitHub\AutoLogger
```

### macOS / Linux examples

```bash
cd ~/Documents/GitHub/AutoLogger
cd ~/Desktop/AutoLogger
```

---

## Step 4 — Install Required Python Packages

Make sure `requirements.txt` exists, then run:

```bash
pip install -r requirements.txt
```

This installs all required dependencies, including:

* openai
* transformers
* accelerate
* torch
* numpy
* sentencepiece
* nltk
* rich
* requests
* jsonschema
* tqdm
* sentence-transformers (optional)

Do **not** install packages outside the conda environment.

---

## Step 5 — Verify the Environment

### Check Python version

```bash
python --version
```

Must be:

```text
Python 3.11.x
```

### Check installed packages

```bash
pip list
```

You should see (at least):

* openai
* transformers
* torch
* numpy
* sentencepiece
* accelerate
* tqdm
* rich

If something is missing:

```bash
pip install <package-name>
```

---

## Step 6 — Set API Keys (OS-specific)

### Windows (PowerShell)

```powershell
$Env:OPENAI_API_KEY = "yourkey"
$Env:HUGGINGFACE_API_KEY = "yourkey"
```

Verify:

```powershell
echo $Env:OPENAI_API_KEY
echo $Env:HUGGINGFACE_API_KEY
```

### macOS / Linux (Terminal)

```bash
export OPENAI_API_KEY="yourkey"
export HUGGINGFACE_API_KEY="yourkey"
```

Verify:

```bash
echo $OPENAI_API_KEY
echo $HUGGINGFACE_API_KEY
```

---

## Step 7 — Run AutoLogger Commands

From here on, **follow `evaluation_guide.md`**.

### Example — Run parser

```bash
python parser/parser.py scripts/script31.py
```

### Example — Run GPT-4.1-mini

```bash
python llm/autologger2.py \
  scripts/script31.candidates.json \
  --provider openai \
  --model gpt-4.1-mini
```

### Example — Run evaluation

```bash
python eval/eval_positions.py \
  dataset/gold_logs/gold_logs_script31 \
  results/llm_gpt41mini_script31.json
```

All commands now run inside the **controlled conda environment**.

---

## Why Virtual Environments Are Mandatory

Without a virtual environment, you may encounter:

* mismatched versions of `transformers`, `torch`, or `numpy`
* Flan model loading failures
* inconsistent LLM behavior
* parser / gold.json mismatches
* non-reproducible Precision / Recall / F1 scores
* OS default Python versions breaking execution
  (Windows: 3.7/3.8, macOS: system Python)

This breaks **cross-platform reproducibility** and invalidates evaluation results.

---

## Optional — Disable Auto-Activation of Base Environment

If your shell always starts with `(base)`:

```bash
conda config --set auto_activate_base false
```

Restart your shell.

---

## Deactivate the Environment (When Finished)

```bash
conda deactivate
```

---

## Final Notes

* Always activate `autologger_env` before running any script
* Never mix system Python with conda Python
* If results differ across machines → **check the environment first**

```

---
