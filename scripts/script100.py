from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, error


@dataclass
class Profile:
    user_id: str
    name: str
    active: bool
    last_seen: datetime
    topics: List[str] = field(default_factory=list)

    def is_active(self, hours: int = 24) -> bool:
        if not self.active:
            return False
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.last_seen < cutoff:
            return False
        return True

    def update_last_seen(self) -> None:
        self.last_seen = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "active": self.active,
            "last_seen": self.last_seen.isoformat(),
            "topics": list(self.topics),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Profile"]:
        try:
            ts_raw = raw.get("last_seen")
            ts = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else datetime.utcnow()
            return cls(
                user_id=str(raw.get("user_id", "")),
                name=str(raw.get("name", "")),
                active=bool(raw.get("active", True)),
                last_seen=ts,
                topics=list(raw.get("topics", [])),
            )
        except Exception:
            return None


@dataclass
class Article:
    article_id: str
    title: str
    topic: str
    published_at: datetime
    score: float

    def is_recent(self, days: int = 3) -> bool:
        cutoff = datetime.utcnow() - timedelta(days=days)
        if self.published_at < cutoff:
            return False
        return True

    def matches_topics(self, topics: Iterable[str]) -> bool:
        topics_l = {t.lower().strip() for t in topics}
        if not topics_l:
            return True
        if self.topic.lower() in topics_l:
            return True
        return any(t in self.title.lower() for t in topics_l)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "topic": self.topic,
            "published_at": self.published_at.isoformat(),
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Article"]:
        try:
            ts_raw = raw.get("published_at")
            ts = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else datetime.utcnow()
            return cls(
                article_id=str(raw.get("article_id", "")),
                title=str(raw.get("title", "")),
                topic=str(raw.get("topic", "")),
                published_at=ts,
                score=float(raw.get("score", 0.0)),
            )
        except Exception:
            return None


@dataclass
class RecommendationSession:
    profile: Profile
    articles: List[Article] = field(default_factory=list)

    def add_article(self, article: Article) -> None:
        self.articles.append(article)

    def personalized_feed(self, limit: int = 10) -> List[Article]:
        if not self.articles:
            return []
        filtered = [
            a for a in self.articles
            if a.is_recent() and a.matches_topics(self.profile.topics)
        ]
        filtered.sort(key=lambda a: a.score, reverse=True)
        return filtered[:limit]

    def summarize(self) -> Dict[str, Any]:
        feed = self.personalized_feed(limit=5)
        return {
            "user_id": self.profile.user_id,
            "feed_count": len(feed),
            "topics": list(self.profile.topics),
            "top_titles": [a.title for a in feed],
        }


class RemoteCatalog:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_articles(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        if topic:
            url = self._url(f"/articles?topic={topic}")
        else:
            url = self._url("/articles")
        if not url:
            return []
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8")
            data = json.loads(text or "[]")
            if not isinstance(data, list):
                return []
            return [d for d in data if isinstance(d, dict)]
        except (error.URLError, ValueError, OSError):
            return []


def load_profiles(path: Path) -> List[Profile]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text or "[]")
        if not isinstance(raw, list):
            return []
        result: List[Profile] = []
        for r in raw:
            p = Profile.from_dict(r)
            if p:
                result.append(p)
        return result
    except (OSError, ValueError):
        return []


def save_profiles(path: Path, profiles: List[Profile]) -> None:
    tmp = path.with_suffix(".tmp")
    payload = [p.to_dict() for p in profiles]
    try:
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return


def parse_articles(raw: Iterable[Dict[str, Any]]) -> List[Article]:
    out: List[Article] = []
    for r in raw:
        art = Article.from_dict(r)
        if art:
            out.append(art)
    return out


def build_recommendations(profile: Profile, catalog: RemoteCatalog) -> RecommendationSession:
    session = RecommendationSession(profile=profile)
    topics = profile.topics or [None]
    for t in topics:
        raw = catalog.fetch_articles(topic=t or None)
        for art in parse_articles(raw):
            session.add_article(art)
    return session


def write_summary(path: Path, summary: Dict[str, Any]) -> bool:
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        return False


def main(config_path: str = "reco_config.json") -> int:
    cfg_file = Path(config_path)
    if not cfg_file.exists():
        return 1
    try:
        cfg_raw = cfg_file.read_text(encoding="utf-8")
        cfg = json.loads(cfg_raw or "{}")
    except (OSError, ValueError):
        return 1

    profiles_path = Path(cfg.get("profiles_path", "profiles.json"))
    summary_path = Path(cfg.get("summary_path", "reco_summary.json"))
    base_url = str(cfg.get("base_url", "")).strip()
    user_id = str(cfg.get("user_id", "")).strip()

    profiles = load_profiles(profiles_path)
    selected = next((p for p in profiles if p.user_id == user_id), None)
    if not selected:
        return 1

    selected.update_last_seen()
    catalog = RemoteCatalog(base_url=base_url)

    retries = 0
    session: Optional[RecommendationSession] = None
    while retries < 2:
        session = build_recommendations(selected, catalog)
        if session.personalized_feed():
            break
        retries += 1

    if not session:
        return 1

    summary = session.summarize()
    if not write_summary(summary_path, summary):
        return 1
    save_profiles(profiles_path, profiles)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
