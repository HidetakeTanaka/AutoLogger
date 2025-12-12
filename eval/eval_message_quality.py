"""
Note: It is not working! You cannot use this program.

= = = = =
eval_message_quality.py

Evaluate the *content* quality of predicted log messages
against gold log messages using BLEU and semantic similarity.

Intended usage (per script):

    python eval/eval_message_quality.py \
        dataset/gold_logs_script31 \
        results/script31_gpt4.json

Assumptions:
- Gold directory contains one or more JSON files with the schema:
    {
      "file": "sample1.py",
      "logs": [
        {
          "candidate_id": int,
          "lineno": int,
          "col_offset": int,
          "kind": "generic",
          "log_code": "logging.info('...')"
        },
        ...
      ]
    }

- Prediction file has the same schema (AutoLogger output):
    {
      "file": "sample1.py",
      "logs": [ ... ]
    }

We match gold vs predicted by (file, candidate_id).
Only pairs where both sides have a non-empty log_code are evaluated.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------

try:
    from nltk.translate.bleu_score import sentence_bleu
except Exception:  # pragma: no cover - optional dependency
    sentence_bleu = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer, util as st_util
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore
    st_util = None  # type: ignore


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


def load_logs_from_dir(dir_path: Path) -> Dict[Tuple[str, int], str]:
    """
    Load all logs from a directory of gold JSON files.

    Returns a mapping:
        (file, line) -> message_text
    """
    mapping: Dict[Tuple[str, int], str] = {}

    for json_path in sorted(dir_path.glob("*.json")):
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        file_name = data.get("file", json_path.stem + ".py")
        logs = data.get("logs", [])
        if not isinstance(logs, list):
            continue

        for log in logs:
            if not isinstance(log, dict):
                continue

            line = int(log.get("line", 0))
            msg = str(log.get("message", "")).strip()

            key = (file_name, line)
            mapping[key] = msg

    return mapping


def load_logs_from_file(path: Path) -> Dict[Tuple[str, int], str]:
    """
    Load logs from a single prediction file.

    Returns a mapping:
        (file, lineno) -> log_text
    """
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    file_name = data.get("file", path.stem + ".py")
    logs = data.get("logs", [])
    mapping: Dict[Tuple[str, int], str] = {}

    if isinstance(logs, list):
        for log in logs:
            if not isinstance(log, dict):
                continue

            line = int(log.get("lineno", 0))
            log_code = str(log.get("log_code", "")).strip()

            key = (file_name, line)
            mapping[key] = log_code

    return mapping


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


def compute_bleu(reference: str, prediction: str) -> Optional[float]:
    """Compute sentence-level BLEU using nltk.

    Returns:
        BLEU score in [0, 1], or None if nltk is not available.
    """
    if sentence_bleu is None:
        return None

    ref_tokens = reference.split()
    pred_tokens = prediction.split()

    # Simple sentence BLEU (no smoothing for now)
    try:
        return float(sentence_bleu([ref_tokens], pred_tokens))
    except Exception:
        return None


class SemanticSimilarity:
    """Wrapper around sentence-transformers for semantic similarity."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        if SentenceTransformer is None or st_util is None:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Install it with `pip install sentence-transformers`."
            )
        self.model = SentenceTransformer(model_name)

    def cosine_sim(self, s1: str, s2: str) -> float:
        emb1 = self.model.encode(s1, convert_to_tensor=True)
        emb2 = self.model.encode(s2, convert_to_tensor=True)
        cos = st_util.cos_sim(emb1, emb2)
        # cos is a 1x1 tensor
        return float(cos.item())


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_message_quality(
    gold_dir: Path,
    pred_file: Path,
    use_semantic: bool = True,
) -> None:
    """Main evaluation routine."""

    gold_logs = load_logs_from_dir(gold_dir)
    pred_logs = load_logs_from_file(pred_file)

    common_keys = sorted(set(gold_logs.keys()) & set(pred_logs.keys()))

    if not common_keys:
        print("No overlapping (file, candidate_id) between gold and predictions.")
        print(f"Gold entries: {len(gold_logs)}, Predicted entries: {len(pred_logs)}")
        return

    bleu_scores: List[float] = []
    sem_scores: List[float] = []

    # Try to load semantic similarity model (optional)
    sem_model: Optional[SemanticSimilarity] = None
    if use_semantic:
        try:
            sem_model = SemanticSimilarity()
        except Exception as e:
            print(f"[WARN] Semantic similarity disabled: {e}")
            sem_model = None

    total_pairs = 0
    skipped_empty = 0

    for key in common_keys:
        gold_msg = gold_logs[key].strip()
        pred_msg = pred_logs[key].strip()

        # Skip pairs where one of the messages is empty
        if not gold_msg or not pred_msg:
            skipped_empty += 1
            continue

        total_pairs += 1

        # BLEU
        b = compute_bleu(gold_msg, pred_msg)
        if b is not None:
            bleu_scores.append(b)

        # Semantic similarity
        if sem_model is not None:
            try:
                s = sem_model.cosine_sim(gold_msg, pred_msg)
                sem_scores.append(s)
            except Exception as e:
                print(f"[WARN] Failed semantic similarity for {key}: {e}")

    print("===============================================")
    print(" Message Quality Evaluation")
    print("===============================================")
    print(f"Gold logs total:        {len(gold_logs)}")
    print(f"Predicted logs total:   {len(pred_logs)}")
    print(f"Overlapping candidates: {len(common_keys)}")
    print(f"Evaluated pairs:        {total_pairs}")
    print(f"Skipped (empty msg):    {skipped_empty}")
    print("-----------------------------------------------")

    # BLEU stats
    if bleu_scores:
        print("BLEU (nltk sentence_bleu)")
        print(f"  Count: {len(bleu_scores)}")
        print(f"  Mean:  {statistics.mean(bleu_scores):.4f}")
        print(f"  Median:{statistics.median(bleu_scores):.4f}")
        print(f"  Min:   {min(bleu_scores):.4f}")
        print(f"  Max:   {max(bleu_scores):.4f}")
    else:
        if sentence_bleu is None:
            print("BLEU: not available (nltk is not installed).")
        else:
            print("BLEU: no valid pairs to evaluate.")

    print("-----------------------------------------------")

    # Semantic similarity stats
    if sem_model is not None:
        if sem_scores:
            print("Semantic similarity (cosine over MiniLM embeddings)")
            print(f"  Count: {len(sem_scores)}")
            print(f"  Mean:  {statistics.mean(sem_scores):.4f}")
            print(f"  Median:{statistics.median(sem_scores):.4f}")
            print(f"  Min:   {min(sem_scores):.4f}")
            print(f"  Max:   {max(sem_scores):.4f}")
        else:
            print("Semantic similarity: no valid pairs to evaluate.")
    else:
        print("Semantic similarity: disabled or sentence-transformers not installed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate message-level quality of AutoLogger logs using BLEU and "
            "semantic similarity.\n\n"
            "Example:\n"
            "  python eval/eval_message_quality.py "
            "dataset/gold_logs_script31 results/script31_gpt4.json\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "gold_dir",
        type=str,
        help="Directory containing gold log JSON files "
             "(e.g., dataset/gold_logs_script31).",
    )
    parser.add_argument(
        "pred_file",
        type=str,
        help="Prediction JSON file produced by AutoLogger "
             "(e.g., results/script31_gpt4.json).",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Disable semantic similarity evaluation (only compute BLEU).",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    gold_dir = Path(args.gold_dir)
    pred_file = Path(args.pred_file)

    if not gold_dir.is_dir():
        raise SystemExit(f"Gold directory not found: {gold_dir}")
    if not pred_file.is_file():
        raise SystemExit(f"Prediction file not found: {pred_file}")

    evaluate_message_quality(
        gold_dir=gold_dir,
        pred_file=pred_file,
        use_semantic=not args.no_semantic,
    )


if __name__ == "__main__":
    main()
