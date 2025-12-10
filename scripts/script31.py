"""
script31.py - Quiz scoring and simple cheating detection.

This script loads quiz attempt data from a JSON file, computes
per-user statistics, and flags suspicious attempts (possible cheating).
It is designed to have several potential logging locations for AutoLogger.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


DATA_DIR = Path("data_quiz")
ATTEMPTS_FILE = DATA_DIR / "attempts.json"


@dataclass
class QuizAttempt:
    user_id: str
    score: float
    max_score: float
    duration_sec: int
    passed: bool

    @property
    def score_ratio(self) -> float:
        if self.max_score <= 0:
            return 0.0
        return self.score / self.max_score

    def is_suspicious(self, fast_threshold: int = 60, high_ratio: float = 0.9) -> bool:
        """A very naive cheating detector: very high score in very short time."""
        if self.duration_sec <= 0:
            return False
        very_fast = self.duration_sec <= fast_threshold
        very_high = self.score_ratio >= high_ratio
        return very_fast and very_high


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def generate_sample_attempts(num_users: int = 10) -> None:
    """Create a sample attempts.json file if none exists."""
    ensure_data_dir()
    attempts: List[Dict[str, object]] = []
    for i in range(1, num_users + 1):
        user_id = f"user{i:03d}"
        for attempt_idx in range(1, 4):
            max_score = 20.0
            base = 5.0 * attempt_idx
            score = min(max_score, base + i % 7)
            duration = 30 * attempt_idx + (i * 3)
            if i == 1 and attempt_idx == 3:
                # deliberately suspicious: almost perfect, very fast
                score = 19.5
                duration = 25
            attempts.append(
                {
                    "user_id": user_id,
                    "score": score,
                    "max_score": max_score,
                    "duration_sec": duration,
                }
            )
    with ATTEMPTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(attempts, f, indent=2)


def load_attempts(path: Path) -> List[QuizAttempt]:
    if not path.exists():
        raise FileNotFoundError(f"Quiz attempts file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError("Expected a list of attempts")
    attempts: List[QuizAttempt] = []
    for entry in raw:
        try:
            score = float(entry.get("score", 0.0))
            max_score = float(entry.get("max_score", 0.0))
            duration = int(entry.get("duration_sec", 0))
            attempts.append(
                QuizAttempt(
                    user_id=str(entry.get("user_id", "")),
                    score=score,
                    max_score=max_score,
                    duration_sec=duration,
                    passed=score >= 0.6 * max_score,
                )
            )
        except Exception:
            # Skip malformed entries
            continue
    return attempts


def group_by_user(attempts: List[QuizAttempt]) -> Dict[str, List[QuizAttempt]]:
    grouped: Dict[str, List[QuizAttempt]] = {}
    for a in attempts:
        grouped.setdefault(a.user_id, []).append(a)
    return grouped


def summarize_user(attempts: List[QuizAttempt]) -> Dict[str, object]:
    if not attempts:
        return {"count": 0, "best_ratio": 0.0, "avg_ratio": 0.0, "any_passed": False}
    ratios = [a.score_ratio for a in attempts]
    best = max(ratios)
    avg = sum(ratios) / len(ratios)
    any_passed = any(a.passed for a in attempts)
    suspicious = any(a.is_suspicious() for a in attempts)
    return {
        "count": len(attempts),
        "best_ratio": round(best, 3),
        "avg_ratio": round(avg, 3),
        "any_passed": any_passed,
        "suspicious": suspicious,
    }


def find_suspicious_users(grouped: Dict[str, List[QuizAttempt]]) -> List[str]:
    suspects: List[str] = []
    for user_id, attempts in grouped.items():
        summary = summarize_user(attempts)
        if summary.get("suspicious"):
            suspects.append(user_id)
    return suspects


def interactive_menu() -> None:
    ensure_data_dir()
    if not ATTEMPTS_FILE.exists():
        print("No attempts file found. Generating sample data...")
        generate_sample_attempts(num_users=12)
    try:
        attempts = load_attempts(ATTEMPTS_FILE)
    except Exception as exc:
        print(f"Failed to load attempts: {exc}")
        return
    grouped = group_by_user(attempts)
    while True:
        print("\nQuiz Analysis Menu")
        print("1) Show per-user summary")
        print("2) Show suspicious users")
        print("3) Regenerate sample data")
        print("0) Exit")
        choice = input("Select an option: ").strip()
        if choice == "0":
            break
        elif choice == "1":
            for user_id, user_attempts in grouped.items():
                summary = summarize_user(user_attempts)
                print(user_id, summary)
        elif choice == "2":
            suspects = find_suspicious_users(grouped)
            if not suspects:
                print("No suspicious users detected.")
            else:
                print("Suspicious users:", ", ".join(suspects))
        elif choice == "3":
            try:
                n_str = input("How many users? (default 10): ").strip()
                n = int(n_str) if n_str else 10
            except ValueError:
                print("Please enter a valid integer.")
                continue
            generate_sample_attempts(max(1, min(n, 100)))
            attempts = load_attempts(ATTEMPTS_FILE)
            grouped = group_by_user(attempts)
            print("Regenerated sample data.")
        else:
            print("Unknown option. Please try again.")


def main() -> None:
    interactive_menu()


if __name__ == "__main__":
    main()
