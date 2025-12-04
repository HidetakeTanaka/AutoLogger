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

### **1. Create a new conda environment**

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

### **2. Install dependencies from `requirements.txt`**

Make sure you are in the root of the repository (`AutoLogger/`):

#### macOS / Linux

```bash
cd path/to/AutoLogger
pip install -r requirements.txt
```

#### Windows (PowerShell)

```powershell
cd path/to/AutoLogger
pip install -r requirements.txt
```

---

### **3. Verify installation**

```bash
python --version
pip list
```

You should see packages such as `openai`, `transformers`, `nltk`, `sentence-transformers`, `numpy`, `torch`.

---

### **4. (Optional) Disable auto-activation of the base environment**

If `(base)` appears every time your terminal opens:

```bash
conda config --set auto_activate_base false
```

Activate manually when needed:

```bash
conda activate autologger_env
```

---

### **5. Deactivating the virtual environment**

```bash
conda deactivate
```

---

### **6. If terminal still auto-activates `(base)`**

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

## **1. Run the parser**

### macOS / Linux

```bash
cd path/to/AutoLogger
python3 parser/parser.py scripts/script31.py
```

### Windows

```powershell
cd path/to/AutoLogger
python parser/parser.py scripts/script31.py
```

---

## **2. Generate `script31_gold.json` using ChatGPT**

*(manual step)*

---

## **3. Create gold directory and move the file**

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

## **4. Copy candidates for baseline**

macOS/Linux:

```bash
cp scripts/script31.candidates.json baselines/parser_output.json
```

Windows:

```powershell
Copy-Item scripts/script31.candidates.json baselines/parser_output.json
```

---

## **5. Run heuristic baseline and evaluate**

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

## **1. Generate predictions**

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

## **2. Convert predictions**

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

## **3. Evaluate**

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

## **1. Generate predictions**

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

## **2. Convert predictions**

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

## **3. Evaluate**

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

## **1. Generate predictions**

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

## **2. Convert predictions**

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

## **3. Evaluate**

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

## **1. Generate predictions**

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
  -o dataset/raw/script31.flanbase.logs.json
}
```

---

## **2. Convert predictions**

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
  results/script31_flanbase.json
```

---

## **3. Evaluate**

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

## **1. Generate script list**

macOS/Linux:

```bash
ls scripts/*.py > evaluation_list.txt
```

Windows:

```powershell
Get-ChildItem scripts/*.py | ForEach-Object { $_.FullName } > evaluation_list.txt
```

---

## **2. Batch-run parser**

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

## **3. Batch-run LLM (example: GPT-4.1-mini)**

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

## **4. Count generated JSON files**

macOS/Linux:

```bash
find results -type f -name "*.json" | wc -l
```

Windows:

```powershell
(Get-ChildItem results -Filter *.json -Recurse).Count
```

---

## **5. Document any crashes or malformed outputs**

Required for the Monday evaluation summary.

---

