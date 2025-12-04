from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request


@dataclass
class Response:
    user_id: str
    question_id: str
    score: float
    submitted_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_recent(self, hours: int = 24) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.submitted_at < cutoff:
            return False
        return True

    def matches_tag(self, tag: str) -> bool:
        t = tag.lower().strip()
        if not t:
            return True
        return any(t in x.lower() for x in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "question_id": self.question_id,
            "score": self.score,
            "submitted_at": self.submitted_at.isoformat(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Response"]:
        try:
            ts_raw = str(raw.get("submitted_at", ""))
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                user_id=str(raw.get("user_id", "")),
                question_id=str(raw.get("question_id", "")),
                score=float(raw.get("score", 0.0)),
                submitted_at=ts,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class SurveyState:
    survey_id: str
    responses: List[Response] = field(default_factory=list)

    def add_response(self, resp: Response) -> None:
        self.responses.append(resp)

    def average_score(self) -> float:
        if not self.responses:
            return 0.0
        return sum(r.score for r in self.responses) / len(self.responses)

    def filter_by_tag(self, tag: str) -> List[Response]:
        return [r for r in self.responses if r.matches_tag(tag)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "survey_id": self.survey_id,
            "responses": [r.to_dict() for r in self.responses],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "SurveyState":
        state = cls(survey_id=str(raw.get("survey_id", "unknown")))
        for item in raw.get("responses", []):
            r = Response.from_dict(item)
            if r is not None:
                state.add_response(r)
        return state


class AnalyticsClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_benchmark(self, survey_id: str) -> Optional[float]:
        if not self.base_url:
            return None
        url = self._url(f"benchmark/{survey_id}")
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            payload = json.loads(data.decode("utf-8"))
            value = payload.get("benchmark")
            return float(value) if value is not None else None
        except (error.URLError, ValueError, KeyError):
            return None

    def send_summary(self, summary: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = self._url("summary")
        body = json.dumps(summary).encode("utf-8")
        try:
            req = request.Request(
                url, data=body, method="POST", headers={"Content-Type": "application/json"}
            )
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except error.URLError:
            return False


def load_survey(path: Path) -> SurveyState:
    if not path.exists():
        return SurveyState(survey_id="local")
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return SurveyState.from_dict(raw)
    except Exception:
        return SurveyState(survey_id="local")


def save_survey(path: Path, survey: SurveyState) -> None:
    payload = json.dumps(survey.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(payload)
        tmp.replace(path)
    except Exception:
        return


def compute_tag_scores(state: SurveyState) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for r in state.responses:
        for tag in (t.lower() for t in r.tags):
            totals[tag] = totals.get(tag, 0.0) + r.score
            counts[tag] = counts.get(tag, 0) + 1
    if not totals:
        return {}
    return {k: totals[k] / counts[k] for k in totals}


def detect_outliers(state: SurveyState, std_limit: float = 2.0) -> List[Response]:
    scores = [r.score for r in state.responses]
    if len(scores) < 2:
        return []
    avg = sum(scores) / len(scores)
    var = sum((s - avg) ** 2 for s in scores) / len(scores)
    std = var ** 0.5
    if std == 0:
        return []
    return [r for r in state.responses if abs(r.score - avg) > std_limit * std]


def simulate_responses(
    state: SurveyState, users: List[str], questions: List[str], days: int = 1
) -> None:
    if not users or not questions:
        return
    total = max(1, days * len(users))
    created = 0
    while created < total:
        u = random.choice(users)
        q = random.choice(questions)
        score = random.uniform(1, 5)
        ts = datetime.utcnow() - timedelta(hours=random.randint(0, days * 24))
        tags = ["auto", random.choice(["ui", "speed", "support", "feature"])]
        state.add_response(Response(user_id=u, question_id=q, score=score, submitted_at=ts, tags=tags))
        created += 1


def summarize_state(
    state: SurveyState, benchmark: Optional[float] = None
) -> Dict[str, Any]:
    avg = state.average_score()
    tag_scores = compute_tag_scores(state)
    outliers = detect_outliers(state)
    comparison: Optional[str]
    if benchmark is None:
        comparison = None
    elif avg > benchmark:
        comparison = "above"
    elif avg < benchmark:
        comparison = "below"
    else:
        comparison = "equal"
    return {
        "survey_id": state.survey_id,
        "average": avg,
        "tag_scores": tag_scores,
        "outlier_count": len(outliers),
        "benchmark_relation": comparison,
        "response_count": len(state.responses),
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    survey_path = base / "survey.json"
    summary_path = base / "summary.json"

    state = load_survey(survey_path)
    if not state.responses:
        simulate_responses(
            state,
            users=["alice", "bob", "carol"],
            questions=["q1", "q2", "q3"],
            days=2,
        )

    client = AnalyticsClient(base_url=base_url, timeout=5) if base_url else None
    benchmark = client.fetch_benchmark(state.survey_id) if client else None
    summary = summarize_state(state, benchmark)

    save_survey(survey_path, state)
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except Exception:
        return 1

    if client:
        sent = client.send_summary(summary)
        if not sent:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
