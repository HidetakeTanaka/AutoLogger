"""
autologger.py

LLM integration module for the AutoLogger project.

This script reads parser output JSON files like `sample1.candidates.json`,
sends each candidate logging position to an LLM to generate a concrete
logging statement, and writes out a new JSON file that other components
(baselines, evaluation scripts) can consume.

Assumed JSON schema for *.candidates.json
-----------------------------------------
We assume that the parser (parser.py) produces JSON of the following form:

{
  "file": "sample1.py",
  "candidates": [
    {
      "id": 0,
      "lineno": 12,                 # 1-based line number where the log should go
      "col_offset": 4,              # indentation level (in spaces)
      "kind": "call",               # e.g. "entry", "return", "exception", "io"
      "function": "process_items",   # optional: enclosing function name
      "code": "result = foo(x, y)",  # source code line / short snippet
      "context_before": ["..."],     # optional: few lines before
      "context_after": ["..."]       # optional: few lines after
    },
    ...
  ]
}

Your actual schema may have different optional fields, but should at least
contain:

- "file" (str)      : path to the Python file
- "candidates" (list[dict]) with at least:
  - "id" (int)
  - "lineno" (int)
  - "code" (str or None)

If it differs, adapt `Candidate.from_dict` below to your real schema.

Predicted logs JSON schema (output of this script)
--------------------------------------------------
We produce JSON like:

{
  "file": "sample1.py",
  "logs": [
    {
      "candidate_id": 0,
      "lineno": 12,
      "col_offset": 4,
      "kind": "call",
      "log_code": "logging.info('Processing items: %s', items)"
    },
    ...
  ]
}

This keeps the link to the original candidate so the evaluation scripts can
compare LLM-logs against gold logs.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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
    code: Optional[str] = None
    context_before: Optional[List[str]] = None
    context_after: Optional[List[str]] = None

    @staticmethod
    def from_dict(data: Dict[str, Any], file_fallback: str) -> "Candidate":
        """Create a Candidate from a parser JSON dict.

        We are defensive here because we don't know the exact schema used
        in your group. Adjust this mapping once you have parser/schema.py.
        """
        return Candidate(
            file=data.get("file", file_fallback),
            id=int(data.get("id", data.get("candidate_id", 0))),
            lineno=int(data.get("lineno", data.get("line", 0))),
            col_offset=int(data.get("col_offset", data.get("indent", 0) or 0)),
            kind=str(data.get("kind", data.get("type", "generic"))),
            function=data.get("function") or data.get("func_name"),
            code=data.get("code") or data.get("source"),
            context_before=data.get("context_before") or data.get("before"),
            context_after=data.get("context_after") or data.get("after"),
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
# Prompt construction & LLM call
# ---------------------------------------------------------------------------


DEFAULT_SYSTEM_PROMPT = (
    "You are an assistant that writes concise, high-quality Python logging "
    "statements for existing code. "
    "You receive a code snippet and a description of where a log should be inserted. "
    "Return exactly ONE Python statement using the standard 'logging' module. "
    "Do NOT include any other text, comments, or code around it. "
    "Prefer info-level logs unless an error is explicitly mentioned."
)


def build_user_prompt(candidate: Candidate) -> str:
    """Create a user prompt string for a single candidate."""
    lines = []

    if candidate.function:
        lines.append(f"Enclosing function: {candidate.function}")
    lines.append(f"Candidate kind: {candidate.kind}")
    lines.append(f"Target line number: {candidate.lineno}")
    lines.append("Code at candidate:")
    lines.append(candidate.code or "<no code available>")

    if candidate.context_before:
        lines.append("\nContext before:")
        lines.extend(candidate.context_before)

    if candidate.context_after:
        lines.append("\nContext after:")
        lines.extend(candidate.context_after)

    lines.append(
        "\nWrite ONE Python statement using the logging module that would be "
        "useful at this position. Do not add comments; return only the statement."
    )

    return "\n".join(lines)


def call_llm(prompt: str, model: str = "gpt-4.1-mini") -> str:
    """Call the LLM to get a logging statement.

    If the OpenAI client is not available, or no API key is configured, we
    fall back to a deterministic heuristic so that the script still works
    during development and for the random/heuristic baselines.
    """
    # Fallback if OpenAI is not installed or API key is missing
    api_key = os.environ.get("OPENAI_API_KEY")
    if openai is None or not api_key:
        return heuristic_logging_line(prompt)

    # Minimal OpenAI chat call; adapt to your environment if needed.
    client = openai.OpenAI(api_key=api_key)  # type: ignore[attr-defined]

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=64,
        temperature=0.3,
    )

    text = response.choices[0].message.content or ""
    return text.strip()


def heuristic_logging_line(prompt: str) -> str:
    """Cheap fallback log line when no LLM is available.

    We try to guess a useful message from the prompt, but keep it simple.
    """
    # Very crude heuristic: look for function name in the prompt text.
    func_name = "unknown"
    for line in prompt.splitlines():
        if line.startswith("Enclosing function:"):
            func_name = line.split(":", 1)[1].strip()
            break

    return (
        f"logging.info('AutoLogger: reached candidate in function {func_name}')"
    )


def extract_logging_line(llm_output: str) -> str:
    """Extract a single logging line from the raw LLM output.

    Our system prompt already asks for a single statement, but we are defensive
    in case the LLM returns extra whitespace or explanations.
    """
    # Take the first non-empty, non-comment line.
    for raw_line in llm_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # If user used backticks or ```python blocks, strip them.
        if line.startswith("```"):
            continue
        # We accept lines that start with logging.<level> or print(…) as a backup.
        if line.startswith("logging.") or line.startswith("print("):
            return line
    # Fallback: return everything as-is, hope it's just one statement
    return llm_output.strip()


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def load_candidates(path: Path) -> List[Candidate]:
    """Load candidates from a *.candidates.json file."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Two possible shapes:
    # 1) {"file": ..., "candidates": [...]}
    # 2) [{"file": ..., "id": ..., ...}, ...]
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
        # If 'id' was missing, ensure a unique id based on position.
        if candidate.id == 0 and "id" not in cand_dict:
            candidate.id = idx
        candidates.append(candidate)

    return candidates


def generate_logs_for_candidates(
    candidates: Iterable[Candidate],
    model: str = "gpt-4.1-mini",
    verbose: bool = False,
) -> List[LogPrediction]:
    """Run the LLM over all candidates and return predictions."""
    predictions: List[LogPrediction] = []

    for cand in candidates:
        prompt = build_user_prompt(cand)
        llm_output = call_llm(prompt, model=model)
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
        # Recover Python file name from candidates JSON name
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
            "Example:\n"
            "  python autologger.py sample1.candidates.json -o sample1.logs.json\n"
            "  python autologger.py sample2.candidates.json --verbose\n"
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
        help="LLM model name (used by OpenAI client).",
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
        verbose=bool(args.verbose),
    )

    write_predictions(predictions, in_path=in_path, out_path=out_path)

    print(f"Wrote {len(predictions)} log predictions to {out_path}")


if __name__ == "__main__":
    main()

