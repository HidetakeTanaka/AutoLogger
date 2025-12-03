from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request


@dataclass
class Article:
    article_id: str
    title: str
    category: str
    published_at: datetime
    score: float = 0.0

    def is_recent(self, hours: int = 24) -> bool:
        ref = datetime.utcnow() - timedelta(hours=hours)
        return self.published_at >= ref

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "category": self.category,
            "published_at": self.published_at.isoformat(),
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Article"]:
        try:
            ts_raw = str(raw.get("published_at", ""))
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                article_id=str(raw.get("article_id", "")),
                title=str(raw.get("title", "")),
                category=str(raw.get("category", "")),
                published_at=ts,
                score=float(raw.get("score", 0.0)),
            )
        except Exception:
            return None


@dataclass
class UserProfile:
    user_id: str
    interests: Dict[str, float] = field(default_factory=dict)
    last_seen: datetime = field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        self.last_seen = datetime.utcnow()

    def update_interest(self, category: str, delta: float = 1.0) -> None:
        current = self.interests.get(category, 0.0)
        self.interests[category] = max(0.0, current + delta)

    def preferred_categories(self, min_score: float = 0.5) -> List[str]:
        return [k for k, v in self.interests.items() if v >= min_score]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "interests": self.interests,
            "last_seen": self.last_seen.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "UserProfile":
        ts_raw = str(raw.get("last_seen", ""))
        try:
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
        except Exception:
            ts = datetime.utcnow()
        return cls(
            user_id=str(raw.get("user_id", "")),
            interests=dict(raw.get("interests", {})),
            last_seen=ts,
        )


class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, user_id: str) -> str:
        return f"{self.base_url}/recommend/{user_id}.json"

    def fetch_recommendations(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        url = self._url(user_id)
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
        except (error.URLError, TimeoutError):
            return None
        try:
            parsed = json.loads(data.decode("utf-8"))
            if isinstance(parsed, list):
                return parsed
            return None
        except Exception:
            return None


def load_user(path: Path) -> UserProfile:
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return UserProfile.from_dict(raw)
    except Exception:
        return UserProfile(user_id="anonymous")


def save_user(path: Path, user: UserProfile) -> None:
    payload = user.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def normalize_scores(articles: List[Article]) -> None:
    if not articles:
        return
    max_score = max(a.score for a in articles) or 1.0
    for a in articles:
        a.score = a.score / max_score


def enrich_with_preferences(
    articles: List[Article], profile: UserProfile
) -> List[Article]:
    if not articles:
        return []
    prefs = profile.interests
    for a in articles:
        bonus = prefs.get(a.category, 0.0)
        a.score += bonus
    normalize_scores(articles)
    return sorted(articles, key=lambda x: x.score, reverse=True)


def compute_preferences(history: List[Article]) -> Dict[str, float]:
    if not history:
        return {}
    weights: Dict[str, float] = {}
    for art in history:
        weights[art.category] = weights.get(art.category, 0.0) + 1.0
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


def simulate_session(
    profile: UserProfile, pool: List[Article], clicks: int = 3
) -> List[Article]:
    clicked: List[Article] = []
    if not pool:
        return clicked
    for _ in range(clicks):
        ranked = enrich_with_preferences(list(pool), profile)
        chosen = ranked[0]
        clicked.append(chosen)
        profile.update_interest(chosen.category, 0.2)
        time.sleep(0.01)
    return clicked


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    user_path = base / "user.json"
    profile = load_user(user_path)
    profile.touch()

    client = RecommendationClient(base_url=base_url or "https://example.com", timeout=5)
    remote = client.fetch_recommendations(profile.user_id)

    if remote is None:
        fake_articles: List[Article] = []
        for i in range(5):
            fake_articles.append(
                Article(
                    article_id=f"local-{i}",
                    title=f"Local Article {i}",
                    category=random.choice(["tech", "sports", "news"]),
                    published_at=datetime.utcnow() - timedelta(hours=i),
                    score=random.random(),
                )
            )
        pool = fake_articles
    else:
        pool = []
        for raw in remote:
            art = Article.from_dict(raw)
            if art is not None:
                pool.append(art)

    clicked = simulate_session(profile, pool, clicks=3)
    profile.interests = compute_preferences(clicked or pool)
    save_user(user_path, profile)

    summary_path = base / "summary.json"
    summary = {
        "user_id": profile.user_id,
        "interests": profile.interests,
        "clicked_ids": [a.article_id for a in clicked],
    }
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
