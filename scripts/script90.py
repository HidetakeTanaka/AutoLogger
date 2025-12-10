from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib import error, request


@dataclass
class Article:
    article_id: str
    title: str
    topic: str
    score: float
    published_at: datetime
    tags: Set[str] = field(default_factory=set)

    def is_recent(self, hours: int = 24) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.published_at < cutoff:
            return False
        return True

    def matches_topic(self, query: str) -> bool:
        q = query.lower().strip()
        if not q:
            return True
        if q in self.topic.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "topic": self.topic,
            "score": self.score,
            "published_at": self.published_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Article"]:
        try:
            ts_raw = raw.get("published_at", "")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                article_id=str(raw.get("article_id", "")),
                title=str(raw.get("title", "")),
                topic=str(raw.get("topic", "")),
                score=float(raw.get("score", 0.0)),
                published_at=ts,
                tags=set(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class UserPreferences:
    user_id: str
    favorite_topics: List[str] = field(default_factory=list)
    min_score: float = 0.0
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def needs_refresh(self, hours: int = 72) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return self.updated_at < cutoff

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "favorite_topics": list(self.favorite_topics),
            "min_score": self.min_score,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["UserPreferences"]:
        try:
            ts_raw = raw.get("updated_at", "")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                user_id=str(raw.get("user_id", "")),
                favorite_topics=list(raw.get("favorite_topics", [])),
                min_score=float(raw.get("min_score", 0.0)),
                updated_at=ts,
            )
        except Exception:
            return None


@dataclass
class FeedState:
    user_id: str
    preferences: Optional[UserPreferences] = None
    articles: List[Article] = field(default_factory=list)

    def add_article(self, article: Article) -> None:
        self.articles.append(article)

    def filter_for_user(self) -> List[Article]:
        if not self.preferences:
            return [a for a in self.articles if a.score >= 0.0]
        fav = {t.lower() for t in self.preferences.favorite_topics}
        results = []
        for a in self.articles:
            if a.score < self.preferences.min_score:
                continue
            if not fav:
                results.append(a)
                continue
            if a.topic.lower() in fav or any(t in fav for t in (x.lower() for x in a.tags)):
                results.append(a)
        return results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "preferences": self.preferences.to_dict() if self.preferences else None,
            "articles": [a.to_dict() for a in self.articles],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "FeedState":
        state = cls(user_id=str(raw.get("user_id", "local")))
        p_raw = raw.get("preferences")
        state.preferences = UserPreferences.from_dict(p_raw) if p_raw else None
        for a_raw in raw.get("articles", []):
            art = Article.from_dict(a_raw)
            if art:
                state.articles.append(art)
        return state


class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_remote_score(self, article_id: str) -> Optional[float]:
        url = self._url(f"scores/{article_id}")
        if not url:
            return None
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            parsed = json.loads(data)
            value = parsed.get("score")
            return float(value) if value is not None else None
        except (error.URLError, ValueError, json.JSONDecodeError):
            return None


def load_state(path: Path) -> FeedState:
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return FeedState.from_dict(raw)
    except FileNotFoundError:
        return FeedState(user_id="local")
    except Exception:
        return FeedState(user_id="local")


def save_state(path: Path, state: FeedState) -> None:
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_topic_stats(state: FeedState) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for a in state.articles:
        totals[a.topic] = totals.get(a.topic, 0.0) + a.score
        counts[a.topic] = counts.get(a.topic, 0) + 1
    if not totals:
        return {}
    return {k: totals[k] / counts[k] for k in totals}


def detect_trending(state: FeedState, hours: int = 6) -> List[Article]:
    recent = [a for a in state.articles if a.is_recent(hours)]
    if not recent:
        return []
    threshold = max(a.score for a in recent) * 0.7
    return [a for a in recent if a.score >= threshold]


def simulate_reads(state: FeedState, sessions: int = 5) -> int:
    if not state.articles:
        return 0
    read = 0
    i = 0
    while i < sessions:
        article = random.choice(state.articles)
        article.score += random.uniform(-0.5, 1.0)
        read += 1
        i += 1
    return read


def summarize_state(state: FeedState, client: Optional[RecommendationClient]) -> Dict[str, Any]:
    topic_stats = compute_topic_stats(state)
    trending = detect_trending(state)
    remote_checked = 0
    if client and trending:
        for a in trending[:3]:
            remote = client.fetch_remote_score(a.article_id)
            if remote is not None:
                a.score = (a.score + remote) / 2
                remote_checked += 1
    base = {
        "user_id": state.user_id,
        "article_count": len(state.articles),
        "topic_stats": topic_stats,
        "trending_ids": [a.article_id for a in trending],
        "remote_scores_updated": remote_checked,
    }
    return base


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / "feed_state.json"
    state = load_state(state_path)

    if not state.articles:
        for i in range(5):
            art = Article(
                article_id=f"local-{i}",
                title=f"Sample Article {i}",
                topic=random.choice(["tech", "sports", "finance"]),
                score=random.uniform(0.0, 5.0),
                published_at=datetime.utcnow() - timedelta(hours=random.randint(0, 24)),
                tags={"sample", "demo"},
            )
            state.add_article(art)

    client = RecommendationClient(base_url=base_url) if base_url else None
    summary = summarize_state(state, client)
    save_state(state_path, state)

    summary_path = base / "feed_summary.json"
    try:
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
