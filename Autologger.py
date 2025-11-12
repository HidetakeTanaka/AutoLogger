"""
AutoLogger - LLM Integration Module
Author: Khushi (LLM Integration Engineer)
Date: Nov 9–13 Implementation Phase
Description:
Reads AST parser output (JSON), calls an LLM to generate log messages,
and saves structured JSON output for integration with AutoLogger system.
"""

import json
import openai  # Replace with your actual LLM API
from typing import List, Dict

# === LLM Call Function ===
def call_llm(prompt: str, model: str = "gpt-4-turbo") -> str:
    """Send prompt to the LLM and return text output."""
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Error] LLM request failed: {e}")
        return "[]"

# === Prompt Construction ===
def build_prompt(func_name: str, context: str, candidates: List[Dict]) -> str:
    """Create structured prompt for LLM to generate logs."""
    return f"""
You are a software logging assistant.

Write short and meaningful log messages for a Python function.
Function name: {func_name}
Function context:
{context}

Candidate log points (as JSON list):
{json.dumps(candidates, indent=2)}

Return ONLY a JSON array with fields:
- line (int)
- level ("info", "warning", or "error")
- message (string)
"""

# === Main Function ===
def generate_logs(input_json: str, output_json: str):
    """Generate logging statements from parsed code context using LLM."""
    with open(input_json, "r") as f:
        parsed_data = json.load(f)

    file_name = parsed_data["file"]
    logs_output = {"file": file_name, "logs": []}

    for func in parsed_data.get("functions", []):
        func_name = func["name"]
        context = func.get("context", "")
        candidates = func.get("candidates", [])

        prompt = build_prompt(func_name, context, candidates)
        print(f"🔹 Generating logs for function: {func_name}")

        llm_response = call_llm(prompt)

        try:
            llm_logs = json.loads(llm_response)
            for log_item in llm_logs:
                logs_output["logs"].append(log_item)
        except json.JSONDecodeError:
            print(f"[Warning] Invalid JSON from LLM for function {func_name}")

    with open(output_json, "w") as f:
        json.dump(logs_output, f, indent=2)

    print(f"✅ Logs generated successfully → {output_json}")

# === CLI Support ===
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AutoLogger LLM Integration")
    parser.add_argument("--input", required=True, help="Path to parser output JSON")
    parser.add_argument("--output", required=True, help="Path to save LLM logs JSON")
    args = parser.parse_args()

    generate_logs(args.input, args.output)
