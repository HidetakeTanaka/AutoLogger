# **AutoLogger – Windows Virtual Environment Setup Guide (Conda + PowerShell)**

### *For Team Members Using Windows*

---

##  **Goal of This Guide**

This guide ensures that **everyone on the team uses the same Python environment**, so that:

* LLM evaluations produce identical results across machines
* dependencies do not break (transformers, numpy, torch, etc.)
* AutoLogger runs consistently for **baseline**, **GPT models**, and **Flan models**

---

#  **Step 1 — Install Anaconda or Miniconda**

If you haven’t installed conda yet:

Download Miniconda (recommended):
[https://docs.conda.io/en/latest/miniconda.html](https://docs.conda.io/en/latest/miniconda.html)

Install and restart PowerShell.

---

# **Step 2 — Create the AutoLogger Virtual Environment**

Run this in PowerShell:

```powershell
conda create -n autologger_env python=3.11 -y
```

Activate the environment:

```powershell
conda activate autologger_env
```

You should now see:

```
(autologger_env) PS C:\Users\yourname\...>
```

If not → something is wrong.

---

# **Step 3 — Navigate to the AutoLogger Repository**

Move into your project directory:

```powershell
cd path\to\AutoLogger (Use your path to "AutoLogger"!!)
```

Example:

```powershell
cd C:\Users\zarin\Desktop\PROJECT\AutoLogger
```

---

#  **Step 4 — Install All Required Packages**

Make sure `requirements.txt` exists in the AutoLogger folder, then run:

```powershell
pip install -r requirements.txt
```

This installs:

* openai
* transformers
* accelerate
* sentencepiece
* numpy
* torch
* nltk
* rich
* requests
* jsonschema
* sentence-transformers (optional)

---

#  **Step 5 — Verify the Environment**

Check the Python version:

```powershell
python --version
```

It **must** be:

```
Python 3.11.x
```

Check installed packages:

```powershell
pip list
```

You should see:

* openai
* transformers
* torch
* numpy
* sentencepiece
* accelerate
* tqdm
* rich

If anything is missing → install manually:

```powershell
pip install <package-name>
```

---

#  **Step 6 — Set Your API Keys (OpenAI / HuggingFace)**

```powershell
$Env:OPENAI_API_KEY = "yourkey"
$Env:HUGGINGFACE_API_KEY = "yourkey"
```

To verify:

```powershell
echo $Env:OPENAI_API_KEY
echo $Env:HUGGINGFACE_API_KEY
```

---

#  **Step 7 — Run AutoLogger Commands Normally**

## Now follow "evaluation_guide.md" carefully!

Example: run parser

```powershell
python parser/parser.py scripts/script31.py
```

Run GPT model:

```powershell
python llm/autologger2.py `
  scripts/script31.candidates.json `
  --provider openai `
  --model gpt-4.1-mini
```

Run evaluation:

```powershell
python eval/eval_positions.py `
  dataset/gold_logs/gold_logs_script31 `
  results/llm_gpt41mini_script31.json
```

Everything now runs inside the controlled environment.
No dependency conflicts, no version mismatches.

---

#  **Why Virtual Environments Are Mandatory**

Without a virtual environment, you may experience:

* different transformers / numpy / torch versions
* LLM calls failing
* parser and evaluation mismatching
* non-reproducible Precision/Recall/F1
* unexpected Python versions (Windows often defaults to Python 3.7 or 3.8)

This breaks team evaluation consistency.

---

#  Optional — Disable Auto-Activation of Base Environment

If PowerShell always shows `(base)`, disable:

```powershell
conda config --set auto_activate_base false
```

---

# ⛔ Deactivate the Environment (When You're Finished)

```powershell
conda deactivate
```

---