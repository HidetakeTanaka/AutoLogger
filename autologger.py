"""
autologger.py

LLM integration module for the AutoLogger project.

This script reads parser output JSON files like `sample1.candidates.json`,
sends each candidate logging position to an LLM (OpenAI GPT or Flan-T5 via
HuggingFace Inference API) to generate a concrete logging statement, and
writes out a new JSON file that other components can consume.

Expected input JSON schema (from parser)
----------------------------------------
Example:

{
  "file": "dataset/raw/sample1.py",
  "candidates": [
    {
      "kind": "func_entry",
      "line": 2,
      "end_line": 2,
      "function": "foo",
      "class_name": null,
      "code": "def foo(x, y):",
      "vars_in_scope": ["result", "x", "y"],
      "why": "function entry",
      "severity_hint": "DEBUG"
    },
    {
      "kind": "before_return",
      "line": 4,
      "end_line": 4,
      "function": "foo",
      "class_name": null,
      "code": "return result",
      "vars_in_scope": ["result", "x", "y"],
      "why": "before return",
      "severity_hint": "INFO"
    }
  ]
}

Output JSON schema (produced by this script)
--------------------------------------------
{
  "file": "dataset/raw/sample1.py",
  "logs": [
    {
      "candidate_id": 0,
      "lineno": 2,
      "col_offset": 0,
      "kind": "func_entry",
      "log_code": "logging.debug('Entering foo with x=%s, y=%s', x, y)"
    },
    ...
  ]
}
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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
    context_before: Optional[List[str]] = None
    context_after: Optional[List[str]] = None
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
            context_before=data.get("context_before") or [],
            context_after=data.get("context_after") or [],
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
    "You are an assistant that writes concise, high-quality Python logging "
    "statements for existing code.\n"
    "You receive a code snippet and metadata about where a log should be inserted.\n"
    "Return exactly ONE Python statement using the standard 'logging' module.\n"
    "- Use the suggested severity level if provided (DEBUG/INFO/WARNING/ERROR).\n"
    "- Use the variables in scope when appropriate.\n"
    "- Do NOT include any comments, extra text, or surrounding code.\n"
    "- Prefer clear, informative messages, not too long."
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
        "\nWrite ONE Python logging statement that would be useful at this position. "
        "It must be a single line starting with logging.<level>(...). "
        "Return only that statement, nothing else."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM backends: OpenAI GPT + Flan-T5 via HuggingFace
# ---------------------------------------------------------------------------


def call_openai_chat(prompt: str, model: str) -> str:
    """Call an OpenAI chat model (e.g., gpt-4.1, gpt-4.1-mini, gpt-5.1)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if openai is None or not api_key:
        return heuristic_logging_line(prompt)

    client = openai.OpenAI(api_key=api_key)  # type: ignore[attr-defined]

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=80,
        temperature=0.2,
    )

    text = response.choices[0].message.content or ""
    return text.strip()


def call_flan_t5_hf(prompt: str, model: str) -> str:
    """Call a Flan-T5 model via HuggingFace Inference API.

    Example model: 'google/flan-t5-large'
    Requires env var HUGGINGFACE_API_KEY.
    """
    hf_key = os.environ.get("HUGGINGFACE_API_KEY")
    if not hf_key:
        return heuristic_logging_line(prompt)

    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {
        "Authorization": f"Bearer {hf_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 80,
            "temperature": 0.2,
        },
    }

    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return heuristic_logging_line(prompt)

    # HF typically returns a list of dicts with "generated_text"
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and "generated_text" in first:
            return str(first["generated_text"]).strip()

    # Fallback: string representation
    return heuristic_logging_line(prompt)


def call_llm(prompt: str, model: str, provider: str) -> str:
    """Unified entry point for all LLM providers."""
    provider = (provider or "openai").lower()

    if provider == "openai":
        return call_openai_chat(prompt, model=model)
    elif provider == "flan":
        return call_flan_t5_hf(prompt, model=model)
    else:
        # Unknown provider → fallback
        return heuristic_logging_line(prompt)


def heuristic_logging_line(prompt: str) -> str:
    """Cheap fallback log line when no LLM is available or provider fails.

    We try to guess a useful message from the prompt, but keep it simple.
    """
    func_name = "unknown"
    severity = "info"

    for line in prompt.splitlines():
        if line.startswith("Enclosing function:"):
            func_name = line.split(":", 1)[1].strip()
        if line.startswith("Suggested severity:"):
            sev = line.split(":", 1)[1].strip().lower()
            if sev in {"debug", "info", "warning", "error", "critical"}:
                severity = sev

    return (
        f"logging.{severity}('AutoLogger: reached candidate in function {func_name}')"
    )


def extract_logging_line(llm_output: str) -> str:
    """Extract a single logging line from the raw LLM output.

    Our prompts already ask for a single statement, but we are defensive
    in case the LLM returns extra whitespace or explanations.
    """
    for raw_line in llm_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        if line.startswith("logging."):
            return line
        if line.startswith("print("):
            return line
    return llm_output.strip()


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
    """Run the LLM over all candidates and return predictions."""
    predictions: List[LogPrediction] = []

    for cand in candidates:
        prompt = build_user_prompt(cand)
        llm_output = call_llm(prompt, model=model, provider=provider)
        log_line = extract_logging_line(llm_output)

        if verbose:
            print(f"Candidate {cand.id} @ {cand.file}:{cand.lineno}")
            print("Prompt:")
            print(prompt)
            print("LLM output:")
            print(llm_output)
            print("Chosen log line:")
            print(log_line)
            print("-" * 80)

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
            "AutoLogger LLM module.\n\n"
            "Examples:\n"
            "  python autologger.py sample1.candidates.json -o sample1.logs.json\n"
            "  python autologger.py sample1.candidates.json --provider flan "
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
