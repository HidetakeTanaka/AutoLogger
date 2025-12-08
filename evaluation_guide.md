# **AutoLogger Evaluation Guide**

### *Cross-Platform Instructions (macOS/Linux + Windows PowerShell)*

### *Version: Final Evaluation Dataset Workflow*

---

# **0. Environment & Credentials Setup**

---

## **0-A. Set Your API Keys**

### macOS / Linux

```bash
export OPENAI_API_KEY="yourkey"
export HUGGINGFACE_API_KEY="yourkey"
```

### Windows (PowerShell)

```powershell
$Env:OPENAI_API_KEY = "yourkey"
$Env:HUGGINGFACE_API_KEY = "yourkey"
```

---

## **0-B. Set up the Virtual Environment (Conda)**

Before running any evaluation steps, create and activate a clean Python environment and install all project dependencies.

This ensures:

* reproducible evaluation
* isolation from system Python
* correct versions of `transformers`, `numpy`, `torch`, etc.

---

### **0-1. Create a new conda environment**

#### macOS / Linux

```bash
conda create -n autologger_env python=3.11 -y
conda activate autologger_env
```

#### Windows (PowerShell)

```powershell
conda create -n autologger_env python=3.11 -y
conda activate autologger_env
```

---

### **0-2. Install dependencies from `requirements.txt`**

Make sure you are in the root of the repository (`AutoLogger/`):

#### macOS / Linux

```bash
cd path/to/AutoLogger (Use your path to "AutoLogger"!!)
pip install -r requirements.txt
```

#### Windows (PowerShell)

```powershell
cd path/to/AutoLogger (Use your path to "AutoLogger"!!)
pip install -r requirements.txt
```

---

### **0-3. Verify installation**

```bash
python --version
pip list
```

You should see packages such as `openai`, `transformers`, `nltk`, `sentence-transformers`, `numpy`, `torch`.

---

### **0-4. (Optional) Disable auto-activation of the base environment**

If `(base)` appears every time your terminal opens:

```bash
conda config --set auto_activate_base false
```

Activate manually when needed:

```bash
conda activate autologger_env
```

---

### **0-5. Deactivating the virtual environment**

```bash
conda deactivate
```

---

### **0-6. If terminal still auto-activates `(base)`**

Check `.zshrc`:

```bash
cat ~/.zshrc | grep conda
```

Remove extra initialization lines if needed.

---

# **Environment Ready — Proceed to Evaluation Steps**

You may now continue with:

* I. Baseline Evaluation (Heuristic)
* II. Random Baseline
* III. GPT-4.1-mini Evaluation
* IV. GPT-5.1 Evaluation
* V. Flan Models
* VI. Runtime Stability Testing

---

# **I. Baseline Evaluation — Heuristic vs Gold**

---

## **I-1. Run the parser**

### macOS / Linux

```bash
cd path/to/AutoLogger (Use your path to "AutoLogger"!!)
python3 parser/parser.py scripts/script31.py
```

### Windows

```powershell
cd path/to/AutoLogger (Use your path to "AutoLogger"!!)
python parser/parser.py scripts/script31.py
```

---

## **I-2. Generate `script31_gold.json` using ChatGPT**

*(manual step)*
Please generate new gold.json using ChatGPT using the following prompt.
After that copy and paste it into the file "script.._gold.json" in the folder "dataset/gold_logs".


Here’s a ready-to-use English prompt you can give to ChatGPT:

---

Using the following two JSON inputs:

1. **`candidates.json`** – a list of logging candidates extracted from a Python script.
2. **`script31_gold.json`** – an example of the desired gold annotation format:

```json
{
  "file": "script31.py",
  "logs": [
    {
      "line": 36,
      "kind": "entry",
      "level": "DEBUG",
      "message": "Entering QuizAttempt.is_suspicious"
    },
    {
      "line": 41,
      "kind": "return",
      "level": "INFO",
      "message": "Returning suspicious flag in QuizAttempt.is_suspicious"
    },
    {
      "line": 76,
      "kind": "entry",
      "level": "DEBUG",
      "message": "Entering load_attempts"
    },
    {
      "line": 99,
      "kind": "exception",
      "level": "ERROR",
      "message": "Failed to parse an attempt entry in load_attempts"
    },
    {
      "line": 100,
      "kind": "return",
      "level": "INFO",
      "message": "Returning parsed attempts from load_attempts"
    },
    {
      "line": 111,
      "kind": "entry",
      "level": "DEBUG",
      "message": "Entering summarize_user"
    },
    {
      "line": 118,
      "kind": "return",
      "level": "INFO",
      "message": "Returning user summary in summarize_user"
    },
    {
      "line": 128,
      "kind": "entry",
      "level": "DEBUG",
      "message": "Entering find_suspicious_users"
    },
    {
      "line": 133,
      "kind": "return",
      "level": "INFO",
      "message": "Returning list of suspicious users"
    },
    {
      "line": 137,
      "kind": "entry",
      "level": "DEBUG",
      "message": "Entering interactive_menu"
    },
    {
      "line": 144,
      "kind": "exception",
      "level": "ERROR",
      "message": "Failed to load attempts in interactive_menu"
    },
    {
      "line": 145,
      "kind": "return",
      "level": "INFO",
      "message": "Aborting interactive_menu after load failure"
    },
    {
      "line": 171,
      "kind": "exception",
      "level": "ERROR",
      "message": "Unexpected error in interactive_menu loop"
    },
    {
      "line": 182,
      "kind": "entry",
      "level": "DEBUG",
      "message": "Entering main"
    }
  ]
}
```

I want you to construct a new **`gold.json`** file for the **target script** described in `candidates.json`.

Please:

1. **Read `candidates.json`** and use it as the source of possible log locations. Each candidate contains (at least) fields like:

   * `file`
   * `line` (or `lineno`)
   * `kind` (e.g., `func_entry`, `before_return`, `except`, etc.)
   * `function`
   * `class_name` (may be `null`)
   * `severity_hint` (e.g., `DEBUG`, `INFO`, `ERROR`)

2. **Use `script31_gold.json` as the style and structure reference**:

   * Similar logging density (not necessarily every candidate must become a log).
   * Similar semantic patterns for messages, such as:

     * `"Entering <Class>.<function>"` for function entries.
     * `"Returning <value/summary> from <function>"` for returns.
     * `"Failed to <action> in <function>"` or `"Unexpected error in <function>"` for exceptions.

3. **Produce a single JSON object** with this exact structure:

```json
{
  "file": "<SCRIPT_NAME>.py",
  "logs": [
    {
      "line": <line_number>,
      "kind": "<entry|return|exception|other>",
      "level": "<DEBUG|INFO|WARNING|ERROR>",
      "message": "<concise, human-readable log message>"
    }
  ]
}
```

Where:

* `"file"` is set to the script file name from `candidates.json` (without any leading directory like `scripts/` unless the example uses it).
* `"logs"` is an array of selected log points derived from `candidates.json`.

4. **Mapping guidelines** (from candidate fields to `logs` entries):

* If candidate `kind` is:

  * `func_entry` → `"kind": "entry"`, `"level"` usually `"DEBUG"`, message `"Entering <Class>.<function>"` or `"Entering <function>"` if no class.
  * `before_return` → `"kind": "return"`, `"level"` usually `"INFO"`, message like `"Returning <summary> from <function>"`.
  * `except` / `exception` → `"kind": "exception"`, `"level"` usually `"ERROR"`, message like `"Failed to <action> in <function>"` or `"Unexpected error in <function>"`.
  * Other kinds may be mapped to `"kind": "other"` with an appropriate level and message if you decide they are useful.

* Use the candidate’s `line` (or `lineno`) as the `"line"` field.

* Use `severity_hint` as a suggestion for `"level"`, but keep it consistent with the example if needed.

5. **Content and style requirements**:

* Messages must be:

  * Clear and human-readable.
  * Consistent with `script31_gold.json` style.
  * Specific to the function/class when possible (e.g., `QuizAttempt.is_suspicious`, `load_attempts`, `interactive_menu`, `main`).

* You **do not** need to include every candidate; choose a reasonable subset that covers:

  * Key function entries.
  * Important returns.
  * Exception paths and error-prone areas.
  * Major top-level workflows (like `main`-style functions).

6. **Output rules**:

* **Only output the final `gold.json` object.**
* Do **not** include explanations, comments, or any additional text.
* Ensure the JSON is valid and can be parsed by a standard JSON parser.

---

(Then I will paste `candidates.json` below this prompt.)



---

## **I-3. Create gold directory and move the file**

### macOS / Linux

```bash
mkdir -p dataset/gold_logs/gold_logs_script31
mv dataset/gold_logs/script31_gold.json dataset/gold_logs/gold_logs_script31/
```

### Windows

```powershell
mkdir -Force dataset/gold_logs/gold_logs_script31 | Out-Null
Move-Item dataset/gold_logs/script31_gold.json dataset/gold_logs/gold_logs_script31/

```

---

## **I-4. Copy candidates for baseline**

macOS/Linux:

```bash
cp scripts/script31.candidates.json baselines/parser_output.json
```

Windows:

```powershell
Copy-Item scripts/script31.candidates.json baselines/parser_output.json
```

---

## **I-5. Run heuristic baseline and evaluate**

macOS/Linux:

```bash
python3 baselines/baseline_heuristic.py
cp baselines/results_heuristic.json results/baseline_script31.json

python3 eval/eval_positions.py \
  dataset/gold_logs/gold_logs_script31 \
  results/baseline_script31.json
```

Windows:

```powershell
python baselines/baseline_heuristic.py
Copy-Item baselines/results_heuristic.json results/baseline_script31.json

python eval/eval_positions.py `
  dataset/gold_logs/gold_logs_script31 `
  results/baseline_script31.json
```

---

# **II. Baseline Evaluation — Random vs Gold**

Steps 1–4 are identical to Section I.

### macOS/Linux:

```bash
python3 baselines/baseline_random.py
cp baselines/results_random.json results/baseline_random_script31.json

python3 eval/eval_positions.py \
  dataset/gold_logs/gold_logs_script31 \
  results/baseline_random_script31.json
```

### Windows:

```powershell
python baselines/baseline_random.py
Copy-Item baselines/results_random.json results/baseline_random_script31.json

python eval/eval_positions.py `
  dataset/gold_logs/gold_logs_script31 `
  results/baseline_random_script31.json
```

---

# **III. GPT-4.1-mini Evaluation**

---

## **III-1. Generate predictions**

#### Optional: Measure LLM Runtime (Recommended for Final Report)

#### To compare runtime performance across different LLMs (e.g., GPT-4.1-mini, GPT-5.1, Flan-T5-base/large), you should record the execution time for each model when generating predictions.

#### This can be done by prefixing the command with time (macOS/Linux) or Measure-Command (Windows PowerShell).

---
macOS/Linux:

```bash
time python3 llm/autologger2.py \
  scripts/script31.candidates.json \
  --provider openai \
  --model gpt-4.1-mini
```

Windows:

```powershell
Measure-Command {
  python llm/autologger2.py `
    scripts/script31.candidates.json `
    --provider openai `
    --model gpt-4.1-mini
}
```

---

## **III-2. Convert predictions**

macOS/Linux:

```bash
python3 eval/convert_llm_for_eval.py \
  scripts/script31.candidates.logs.json \
  results/llm_gpt41mini_script31.json
```

Windows:

```powershell
python eval/convert_llm_for_eval.py `
  scripts/script31.candidates.logs.json `
  results/llm_gpt41mini_script31.json
```

---

## **III-3. Evaluate**

macOS/Linux:

```bash
python3 eval/eval_positions.py \
  dataset/gold_logs/gold_logs_script31 \
  results/llm_gpt41mini_script31.json
```

Windows:

```powershell
python eval/eval_positions.py `
  dataset/gold_logs/gold_logs_script31 `
  results/llm_gpt41mini_script31.json
```

---

# **IV. GPT-5.1 Evaluation**

Same commands as GPT-4.1-mini, but replace model:

```
--model gpt-5.1
```

Evaluation identical.
---

## **IV-1. Generate predictions**

#### Optional: Measure LLM Runtime (Recommended for Final Report)

#### To compare runtime performance across different LLMs (e.g., GPT-4.1-mini, GPT-5.1, Flan-T5-base/large), you should record the execution time for each model when generating predictions.

#### This can be done by prefixing the command with time (macOS/Linux) or Measure-Command (Windows PowerShell).

---

macOS/Linux:

```bash
time python3 llm/autologger2.py \
  scripts/script31.candidates.json \
  --provider openai \
  --model gpt-5.1

```

Windows:

```powershell
Measure-Command {
  python llm/autologger2.py `
    scripts/script31.candidates.json `
    --provider openai `
    --model gpt-5.1
}
```

---

## **IV-2. Convert predictions**

macOS/Linux:

```bash
python3 eval/convert_llm_for_eval.py \
  scripts/script31.candidates.logs.json \
  results/llm_gpt51_script31.json
```

Windows:

```powershell
python eval/convert_llm_for_eval.py `
  scripts/script31.candidates.logs.json `
  results/llm_gpt51_script31.json
```

---

## **IV-3. Evaluate**

macOS/Linux:

```bash
python3 eval/eval_positions.py \
  dataset/gold_logs/gold_logs_script31 \
  results/llm_gpt51_script31.json
```

Windows:

```powershell
python eval/eval_positions.py `
  dataset/gold_logs/gold_logs_script31 `
  results/llm_gpt51_script31.json
```

---

# **V. Flan-T5-base Evaluation**

---

## **V-1. Generate predictions**

#### Optional: Measure LLM Runtime (Recommended for Final Report)

#### To compare runtime performance across different LLMs (e.g., GPT-4.1-mini, GPT-5.1, Flan-T5-base/large), you should record the execution time for each model when generating predictions.

#### This can be done by prefixing the command with time (macOS/Linux) or Measure-Command (Windows PowerShell).
---

macOS/Linux:

```bash
time python3 llm/autologger2.py scripts/script31.candidates.json \
  --provider flan \
  --model google/flan-t5-base \
  -o dataset/raw/script31.flanbase.logs.json
```

Windows:

```powershell
Measure-Command {
 python llm/autologger2.py scripts/script31.candidates.json `
  --provider flan `
  --model google/flan-t5-base `
  -o dataset/raw/script31.flanbase.logs.json
}
```

---

## **V-2. Convert predictions**

macOS/Linux:

```bash
python3 eval/convert_llm_for_eval.py \
  dataset/raw/script31.flanbase.logs.json \
  results/script31_flanbase.json
```

Windows:

```powershell
python eval/convert_llm_for_eval.py `
  dataset/raw/script31.flanbase.logs.json `
  results/script31_flanbase.json
```

---

## **V-3. Evaluate**

macOS/Linux:

```bash
python3 eval/eval_positions.py \
  dataset/gold_logs/gold_logs_script31 \
  results/script31_flanbase.json
```

Windows:

```powershell
python eval/eval_positions.py `
  dataset/gold_logs/gold_logs_script31 `
  results/script31_flanbase.json
```

---

# **VI. Flan-T5-large Evaluation**

Same as Flan-T5-base, but replace:

```
--model google/flan-t5-large
```

## **VI-1. Generate predictions**

#### Optional: Measure LLM Runtime (Recommended for Final Report)

#### To compare runtime performance across different LLMs (e.g., GPT-4.1-mini, GPT-5.1, Flan-T5-base/large), you should record the execution time for each model when generating predictions.

#### This can be done by prefixing the command with time (macOS/Linux) or Measure-Command (Windows PowerShell).

---
macOS/Linux:

```bash
time python3 llm/autologger2.py \
  scripts/script31.candidates.json \
  --provider flan \
  --model google/flan-t5-large \
  -o dataset/raw/script31.flanlarge.logs.json

```

Windows:

```powershell
Measure-Command {
 python llm/autologger2.py scripts/script31.candidates.json `
  --provider flan `
  --model google/flan-t5-large `
  -o dataset/raw/script31.flanlarge.logs.json
}
```

---

## **VI-2. Convert predictions**

macOS/Linux:

```bash
python3 eval/convert_llm_for_eval.py \
  dataset/raw/script31.flanlarge.logs.json \
  results/script31_flanlarge.json
```

Windows:

```powershell
python eval/convert_llm_for_eval.py `
  dataset/raw/script31.flanlarge.logs.json `
  results/script31_flanlarge.json
```

---

## **VI-3. Evaluate**

macOS/Linux:

```bash
python3 eval/eval_positions.py \
  dataset/gold_logs/gold_logs_script31 \
  results/script31_flanlarge.json
```

Windows:

```powershell
python eval/eval_positions.py `
  dataset/gold_logs/gold_logs_script31 `
  results/script31_flanlarge.json
```



---

# **VII. Runtime Stability Test (Optional)**

---

## **VII-1. Generate script list**

macOS/Linux:

```bash
ls scripts/*.py > evaluation_list.txt
```

Windows:

```powershell
Get-ChildItem scripts/*.py | ForEach-Object { $_.FullName } > evaluation_list.txt
```

---

## **VII-2. Batch-run parser**

macOS/Linux:

```bash
while read file; do
  echo "Parsing $file"
  python3 parser/parser.py "$file"
done < evaluation_list.txt
```

Windows:

```powershell
Get-Content evaluation_list.txt | ForEach-Object {
    Write-Host "Parsing $_"
    python parser/parser.py $_
}
```

---

## **VII-3. Batch-run LLM (example: GPT-4.1-mini)**

macOS/Linux:

```bash
while read file; do
  json="${file%.py}.candidates.json"
  echo "Running LLM on $json"
  python3 autologger.py "$json" --provider openai --model gpt-4.1-mini
done < evaluation_list.txt
```

Windows:

```powershell
Get-Content evaluation_list.txt | ForEach-Object {
    $json = $_ -replace ".py$", ".candidates.json"
    Write-Host "Running LLM on $json"
    python autologger.py $json --provider openai --model gpt-4.1-mini
}
```

---

## **VII-4. Count generated JSON files**

macOS/Linux:

```bash
find results -type f -name "*.json" | wc -l
```

Windows:

```powershell
(Get-ChildItem results -Filter *.json -Recurse).Count
```

---

## **VII-5. Document any crashes or malformed outputs**

Required for the Monday evaluation summary.

---

---

# **Ⅷ. How to Analyze Our Evaluation Results**

---

### *Explanation of Macro/Micro averages + how to calculate in Google Sheets*

We used a Google spreadsheet to record the evaluation: <link>
---

## **Ⅷ-1. Macro vs Micro — What’s the difference?**

| Type              | Meaning                                                                                                            | How it’s calculated                |
| ----------------- | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------- |
| **Macro Average** | Treat each script equally. Calculate F1 for each script, then take the simple average.                             | Average(F1_list)                   |
| **Micro Average** | Treat each *log event* equally. Sum TP/FP/FN across all scripts, then compute precision/recall/F1 from the totals. | Use (TP_total, FP_total, FN_total) |

 **Macro = per-script fairness**
 **Micro = overall performance fairness**

Both are needed for a complete evaluation.

---

#  **Ⅷ-2. For the final project, what we should compute (100 scripts)**

For each model:

* **Macro Precision / Macro Recall / Macro F1**
* **Micro Precision / Micro Recall / Micro F1**

This gives a statistically solid comparison across the entire dataset.

You already did Script26–50 — great work!
The other teammates (Script1–25, 51–75, 76–100) will fill the rest.

---

#  **Ⅷ-3. How to calculate in Google Sheets (simple formulas)**

Assume your sheet looks like this:

| Script | System | TP | FP | FN | Precision | Recall | F1 |
| ------ | ------ | -- | -- | -- | --------- | ------ | -- |

Example row:

```
Script26 | Heuristic | 24 | 8 | 3 | 0.750 | 0.889 | 0.814
Script26 | GPT-4.1   | 15 | 7 | 12 | 0.682 | 0.556 | 0.612
```

---

##  **A. Macro F1 (simple average across scripts)**

Formula:

```gs
=AVERAGE(FILTER(H:H, B:B="Heuristic"))
```

(Assuming column H = F1)

---

##  **B. Micro averages (sum TP/FP/FN first)**

### 1. Total TP for a model:

```gs
=SUM(FILTER(C:C, B:B="Heuristic"))
```

### 2. Total FP:

```gs
=SUM(FILTER(D:D, B:B="Heuristic"))
```

### 3. Total FN:

```gs
=SUM(FILTER(E:E, B:B="Heuristic"))
```

---

##  Micro Precision

```gs
= TP_total / (TP_total + FP_total)
```

---

##  Micro Recall

```gs
= TP_total / (TP_total + FN_total)
```

---

##  Micro F1

```gs
= 2 * A * B / (A + B)
```

(where A = Micro Precision, B = Micro Recall)

---

#  **Ⅷ-4. What the final summary table should look like**

For each model:

| Model | Macro P | Macro R | Macro F1 | Micro P | Micro R | Micro F1 |
| ----- | ------- | ------- | -------- | ------- | ------- | -------- |

With 100 scripts, this gives a strong statistical basis for comparison.

---
