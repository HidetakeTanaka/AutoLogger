from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import math
import random
from urllib import request, error


@dataclass
class Review:
    user_id: str
    book_id: str
    rating: float
    created_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_recent(self, hours: int = 24) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.created_at < cutoff:
            return False
        return True

    def matches_tag(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.book_id.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "book_id": self.book_id,
            "rating": self.rating,
            "created_at": self.created_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Review"]:
        try:
            ts_raw = raw.get("created_at")
            ts = (
                datetime.fromisoformat(ts_raw)
                if isinstance(ts_raw, str)
                else datetime.utcnow()
            )
            return cls(
                user_id=str(raw.get("user_id", "")),
                book_id=str(raw.get("book_id", "")),
                rating=float(raw.get("rating", 0.0)),
                created_at=ts,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class LibraryState:
    library_id: str
    reviews: List[Review] = field(default_factory=list)

    def add_review(self, review: Review) -> None:
        self.reviews.append(review)

    def average_rating(self) -> float:
        if not self.reviews:
            return 0.0
        return sum(r.rating for r in self.reviews) / len(self.reviews)

    def filter_by_tag(self, tag: str) -> List[Review]:
        return [r for r in self.reviews if r.matches_tag(tag)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "library_id": self.library_id,
            "reviews": [r.to_dict() for r in self.reviews],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "LibraryState":
        state = cls(library_id=str(raw.get("library_id", "local")))
        for r in raw.get("reviews", []):
            rev = Review.from_dict(r)
            if rev is not None:
                state.add_review(rev)
        return state


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_global_average(self) -> Optional[float]:
        if not self.base_url:
            return None
        url = self._url("global-average")
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            payload = json.loads(data)
            value = payload.get("average")
            return float(value) if value is not None else None
        except Exception:
            return None

    def send_summary(self, summary: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = self._url("summary")
        body = json.dumps(summary).encode("utf-8")
        try:
            req = request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except error.URLError:
            return False
        except Exception:
            return False


def load_state(path: Path) -> LibraryState:
    if not path.exists():
        return LibraryState(library_id="local")
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return LibraryState.from_dict(raw)
    except Exception:
        return LibraryState(library_id="local")


def save_state(path: Path, state: LibraryState) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(state.to_dict(), ensure_ascii=False, indent=2)
    try:
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_tag_stats(state: LibraryState) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for r in state.reviews:
        for t in r.tags or ["untagged"]:
            totals[t] = totals.get(t, 0.0) + r.rating
            counts[t] = counts.get(t, 0) + 1
    if not totals:
        return {}
    return {k: totals[k] / counts[k] for k in totals}


def detect_outliers(state: LibraryState, std_limit: float = 2.0) -> List[Review]:
    ratings = [r.rating for r in state.reviews]
    if len(ratings) < 2:
        return []
    avg = sum(ratings) / len(ratings)
    var = sum((x - avg) ** 2 for x in ratings) / (len(ratings) - 1)
    std = math.sqrt(var)
    if std == 0:
        return []
    return [r for r in state.reviews if abs(r.rating - avg) > std_limit * std]


def simulate_reviews(
    state: LibraryState, users: int = 5, books: int = 3, total: int = 20
) -> int:
    created = 0
    if total <= 0:
        return 0
    for _ in range(total):
        u = f"u{random.randint(1, users)}"
        b = f"b{random.randint(1, books)}"
        rating = random.randint(1, 5)
        tags = ["fiction"] if random.random() < 0.5 else ["non-fiction"]
        ts = datetime.utcnow() - timedelta(hours=random.randint(0, 72))
        state.add_review(Review(u, b, rating, ts, tags))
        created += 1
    return created


def summarize_state(state: LibraryState, global_avg: Optional[float]) -> Dict[str, Any]:
    avg = state.average_rating()
    tag_stats = compute_tag_stats(state)
    outliers = detect_outliers(state)
    relation = "unknown"
    if global_avg is not None:
        if avg > global_avg:
            relation = "above"
        elif avg < global_avg:
            relation = "below"
        else:
            relation = "equal"
    return {
        "library_id": state.library_id,
        "average": avg,
        "tag_stats": tag_stats,
        "outlier_count": len(outliers),
        "relation_to_global": relation,
        "review_count": len(state.reviews),
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    try:
        base = Path(data_dir)
        state_path = base / "reviews.json"
        summary_path = base / "summary.json"
        state = load_state(state_path)
        if not state.reviews:
            simulate_reviews(state)
            save_state(state_path, state)
        client = ApiClient(base_url=base_url) if base_url else ApiClient("", 5)
        global_avg = client.fetch_global_average()
        summary = summarize_state(state, global_avg)
        summary_payload = json.dumps(summary, ensure_ascii=False, indent=2)
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(summary_payload, encoding="utf-8")
        except Exception:
            return 1
        if base_url:
            client.send_summary(summary)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
