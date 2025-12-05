"""
autologger2.py

LLM integration module for the AutoLogger project.

This version:
- keeps the OpenAI provider as before (gpt-4.1-mini, gpt-5.1, ...)
- uses the HuggingFace Inference API for the 'flan' provider
  (google/flan-t5-*) and falls back to a heuristic decision when the
  API call fails (e.g., 404 or missing HUGGINGFACE_API_KEY).
"""


from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

try:
    import openai  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    openai = None  # type: ignore


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    """One potential log insertion point produced by the parser."""

    file: str
    id: int
    lineno: int
    col_offset: int = 0
    kind: str = "generic"
    function: Optional[str] = None
    class_name: Optional[str] = None
    code: Optional[str] = None
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)
    severity_hint: str = "INFO"
    vars_in_scope: List[str] = field(default_factory=list)
    why: Optional[str] = None

    @staticmethod
    def from_dict(data: Dict[str, Any], file_fallback: str) -> "Candidate":
        """Create a Candidate from a parser JSON dict."""
        return Candidate(
            file=data.get("file", file_fallback),
            id=int(data.get("id", data.get("candidate_id", 0))),
            lineno=int(data.get("line", data.get("lineno", 0))),
            col_offset=int(data.get("col_offset", data.get("indent", 0) or 0)),
            kind=str(data.get("kind", "generic")),
            function=data.get("function"),
            class_name=data.get("class_name"),
            code=data.get("code"),
            context_before=list(data.get("context_before") or []),
            context_after=list(data.get("context_after") or []),
            severity_hint=str(data.get("severity_hint", "INFO")).upper(),
            vars_in_scope=list(data.get("vars_in_scope") or []),
            why=data.get("why"),
        )


@dataclass
class LogPrediction:
    """Logging statement predicted by the LLM for a single candidate."""

    candidate_id: int
    lineno: int
    col_offset: int
    kind: str
    log_code: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "lineno": self.lineno,
            "col_offset": self.col_offset,
            "kind": self.kind,
            "log_code": self.log_code,
        }


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = (
    "You are an assistant that decides whether to insert Python logging statements "
    "for existing code and, if appropriate, writes concise, high-quality log lines.\n"
    "You receive a code snippet and metadata about a potential log position.\n"
    "Your task is to decide whether a log is useful at this position and, if so, "
    "return a single Python logging statement using the standard 'logging' module.\n"
    "\n"
    "You MUST return a JSON object with exactly the following keys:\n"
    '  {\"should_log\": <bool>, \"log_code\": <string> }\n'
    "- If you think a log should be inserted, set should_log=true and provide a "
    "single Python logging statement in log_code (e.g. logging.info(...)).\n"
    "- If you think a log is NOT needed, set should_log=false and use an empty "
    "string for log_code.\n"
    "- Use the suggested severity level if provided (DEBUG/INFO/WARNING/ERROR).\n"
    "- Use variables in scope when appropriate.\n"
    "- Do NOT include any comments, explanations, or extra text outside the JSON."
)


def build_user_prompt(candidate: Candidate) -> str:
    """Create a user prompt string for a single candidate."""
    lines: List[str] = []

    lines.append(f"Target file: {candidate.file}")
    if candidate.class_name:
        lines.append(f"Enclosing class: {candidate.class_name}")
    if candidate.function:
        lines.append(f"Enclosing function: {candidate.function}")
    lines.append(f"Candidate kind: {candidate.kind}")
    lines.append(f"Target line number: {candidate.lineno}")
    lines.append(f"Suggested severity: {candidate.severity_hint}")

    if candidate.why:
        lines.append(f"Reason for log: {candidate.why}")

    lines.append("\nCode at candidate:")
    lines.append(candidate.code or "<no code available>")

    if candidate.context_before:
        lines.append("\nContext before:")
        lines.extend(candidate.context_before)

    if candidate.context_after:
        lines.append("\nContext after:")
        lines.extend(candidate.context_after)

    if candidate.vars_in_scope:
        lines.append(
            "\nVariables in scope: " + ", ".join(candidate.vars_in_scope)
        )

    lines.append(
        "\nDecide whether a log statement is REALLY useful at this position.\n"
        "Most candidates should NOT be logged. Prefer should_log=false unless this log\n"
        "would add clear debugging value beyond existing information.\n"
        "Return ONLY a JSON object with these keys:\n"
        '  {\"should_log\": <bool>, \"log_code\": <string> }\n'
        "- should_log is true only if the log is clearly helpful, otherwise false.\n"
        "- log_code is the logging statement when should_log is true, otherwise \"\"."
    )

    return "\n".join(lines)



# ---------------------------------------------------------------------------
# LLM backends: OpenAI GPT + Flan-T5 (via HuggingFace Inference API)
# ---------------------------------------------------------------------------

def call_openai_chat(prompt: str, model: str) -> str:
    """Call an OpenAI chat model (e.g., gpt-4.1-mini, gpt-5.1).

    If the OpenAI client or API key is not available, or if any error occurs
    (e.g. insufficient_quota), this function returns a heuristic JSON decision
    instead of raising an exception.
    """
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if openai is None or not api_key:
        # fall back to heuristic if OpenAI not available
        return heuristic_decision_json(prompt)

    client = openai.OpenAI(api_key=api_key)  # type: ignore[attr-defined]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=200,
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        return text.strip()
    except Exception as e:
        # PRINT THE ERROR so we can see it!
        print(f"\n[ERROR] OpenAI Call Failed: {e}\n")
        return heuristic_decision_json(prompt)



def call_flan_t5_hf(prompt: str, model: str) -> str:
    """Call a Flan-T5 model via the (legacy) HuggingFace Inference API.

    Example model: 'google/flan-t5-large'.
    Requires env var HUGGINGFACE_API_KEY.

    If the request fails (e.g. 404, timeout, missing API key), this function
    returns a heuristic JSON decision instead of raising an exception.
    """

    hf_key = os.environ.get("HUGGINGFACE_API_KEY")
    if not hf_key:
        return heuristic_decision_json(prompt)

    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {
        "Authorization": f"Bearer {hf_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": f"{DEFAULT_SYSTEM_PROMPT}\n\nUSER PROMPT:\n{prompt}",
        "parameters": {
            "max_new_tokens": 120,
            "temperature": 0.2,
        },
    }

    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return heuristic_decision_json(prompt)

    # HF typically returns a list of dicts with "generated_text"
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and "generated_text" in first:
            return str(first["generated_text"]).strip()

    return heuristic_decision_json(prompt)


def call_llm(prompt: str, model: str, provider: str) -> str:
    """Unified entry point for all LLM providers.

    Returns the raw text output from the model (expected to be JSON).
    """
    provider = (provider or "openai").lower()

    if provider == "openai":
        return call_openai_chat(prompt, model=model)
    elif provider == "flan":
        return call_flan_t5_hf(prompt, model=model)
    else:
        # Unknown provider → fallback
        return heuristic_decision_json(prompt)




# ---------------------------------------------------------------------------
# JSON parsing & heuristic fallback
# ---------------------------------------------------------------------------


def heuristic_decision_json(prompt: str) -> str:
    """Fallback JSON decision when no LLM is available or the call fails.

    Very simple strategy:
      - Always log (should_log = true)
      - Use a generic log statement mentioning the function name.
      - Use the suggested severity level from the prompt if available,
        otherwise default to INFO.
    """
    
    func_name = "unknown"
    severity = "INFO"

    for line in prompt.splitlines():
        if line.startswith("Enclosing function:"):
            func_name = line.split(":", 1)[1].strip()
        if line.startswith("Suggested severity:"):
            sev = line.split(":", 1)[1].strip().upper()
            if sev in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
                severity = sev

    log_code = (
        f"logging.{severity.lower()}('[HEURISTIC] AutoLogger: reached candidate in function {func_name}')"
    )

    decision = {
        "should_log": True,
        "log_code": log_code,
    }
    return json.dumps(decision)


def parse_llm_decision(
    raw_output: str, candidate: Candidate
) -> Tuple[bool, str]:
    """Parse LLM output into (should_log, log_code).

    raw_output is expected to be a JSON object as a string, but we are defensive:
      - Strip markdown code fences.
      - Extract the first {...} block if needed.
      - On failure, fall back to the heuristic decision.
    """
    text = raw_output.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        # Remove lines starting and ending with ```
        lines = [
            line for line in text.splitlines()
            if not line.strip().startswith("```")
        ]
        text = "\n".join(lines).strip()

    # Try direct JSON parsing first
    def _try_parse(s: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(s)
        except Exception:
            return None

    data = _try_parse(text)

    # If that fails, try to locate a JSON object using a regex
    if data is None:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            data = _try_parse(match.group(0))

    # If parsing still failed, fall back to heuristic
    if data is None or not isinstance(data, dict):
        fallback = json.loads(heuristic_decision_json(build_user_prompt(candidate)))
        return bool(fallback.get("should_log", True)), str(
            fallback.get("log_code", "")
        )

    should_log = bool(data.get("should_log", True))
    log_code = str(data.get("log_code", "")).strip()

    # Basic sanitisation: if should_log is true but log_code is empty, fall back
    if should_log and not log_code:
        fallback = json.loads(heuristic_decision_json(build_user_prompt(candidate)))
        should_log = bool(fallback.get("should_log", True))
        log_code = str(fallback.get("log_code", "")).strip()

    return should_log, log_code


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def load_candidates(path: Path) -> List[Candidate]:
    """Load candidates from a *.candidates.json file."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        file_name = data.get("file", path.stem.replace(".candidates", "") + ".py")
        raw_candidates = data.get("candidates", [])
    elif isinstance(data, list):
        file_name = path.stem.replace(".candidates", "") + ".py"
        raw_candidates = data
    else:
        raise ValueError(f"Unexpected JSON structure in {path}")

    candidates: List[Candidate] = []
    for idx, cand_dict in enumerate(raw_candidates):
        if not isinstance(cand_dict, dict):
            continue
        candidate = Candidate.from_dict(cand_dict, file_fallback=file_name)
        if candidate.id == 0 and "id" not in cand_dict:
            candidate.id = idx
        candidates.append(candidate)

    return candidates


def generate_logs_for_candidates(
    candidates: Iterable[Candidate],
    model: str,
    provider: str,
    verbose: bool = False,
) -> List[LogPrediction]:
    """Run the LLM over all candidates and return predictions.

    IMPORTANT CHANGE:
      - We only add a LogPrediction when the LLM (or heuristic) returns
        should_log == True.
    """
    predictions: List[LogPrediction] = []

    for cand in candidates:
        prompt = build_user_prompt(cand)
        raw_output = call_llm(prompt, model=model, provider=provider)
        should_log, log_line = parse_llm_decision(raw_output, cand)

        if verbose:
            print(f"Candidate {cand.id} @ {cand.file}:{cand.lineno}")
            print("Prompt:")
            print(prompt)
            print("Raw LLM output:")
            print(raw_output)
            print(f"Parsed decision: should_log={should_log}, log_code={log_line}")
            print("-" * 80)

        if not should_log:
            # Skip this candidate entirely
            continue

        predictions.append(
            LogPrediction(
                candidate_id=cand.id,
                lineno=cand.lineno,
                col_offset=cand.col_offset,
                kind=cand.kind,
                log_code=log_line,
            )
        )

    return predictions


def write_predictions(
    predictions: List[LogPrediction],
    in_path: Path,
    out_path: Path,
    file_name: Optional[str] = None,
) -> None:
    """Write predictions to JSON in the agreed schema."""
    if file_name is None:
        file_name = in_path.stem.replace(".candidates", "") + ".py"

    payload = {
        "file": file_name,
        "logs": [p.to_dict() for p in predictions],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "AutoLogger LLM module with JSON yes/no decisions.\n\n"
            "Examples:\n"
            "  python autologger2.py sample1.candidates.json -o sample1.logs.json\n"
            "  python autologger2.py sample1.candidates.json --provider flan "
            "--model google/flan-t5-large\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "candidates_json",
        type=str,
        help="Path to *.candidates.json file produced by parser.py",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output path for logs JSON (default: <input>.logs.json)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4.1-mini",
        help=(
            "LLM model name.\n"
            "For provider=openai, examples: gpt-4.1-mini, gpt-4.1, gpt-5.1 (if available).\n"
            "For provider=flan, examples: google/flan-t5-base, google/flan-t5-large."
        ),
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        choices=["openai", "flan"],
        help="LLM provider to use: 'openai' or 'flan'.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print prompts and raw LLM outputs for debugging.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    in_path = Path(args.candidates_json)
    if not in_path.is_file():
        raise SystemExit(f"Input file not found: {in_path}")

    out_path = Path(args.output) if args.output else in_path.with_suffix(".logs.json")

    candidates = load_candidates(in_path)
    predictions = generate_logs_for_candidates(
        candidates,
        model=args.model,
        provider=args.provider,
        verbose=bool(args.verbose),
    )

    write_predictions(predictions, in_path=in_path, out_path=out_path)

    print(f"Wrote {len(predictions)} log predictions to {out_path}")


if __name__ == "__main__":
    main()
