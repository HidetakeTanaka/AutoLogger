from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class Article:
    article_id: str
    title: str
    author: str
    published: datetime
    tags: List[str] = field(default_factory=list)
    score: float = 0.0

    def is_recent(self, hours: int = 24) -> bool:
        if hours <= 0:
            return False
        ref = datetime.utcnow() - timedelta(hours=hours)
        return self.published >= ref

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.title.lower() or q in self.author.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "author": self.author,
            "published": self.published.isoformat(),
            "tags": list(self.tags),
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Article"]:
        try:
            pub_raw = str(raw.get("published", ""))
            published = datetime.fromisoformat(pub_raw) if pub_raw else datetime.utcnow()
            return cls(
                article_id=str(raw.get("article_id", "")),
                title=str(raw.get("title", "")),
                author=str(raw.get("author", "")),
                published=published,
                tags=list(raw.get("tags", [])),
                score=float(raw.get("score", 0.0)),
            )
        except Exception:
            return None


class Feed:
    def __init__(self, feed_id: str, name: str) -> None:
        self.feed_id = feed_id
        self.name = name
        self._articles: Dict[str, Article] = {}

    def add(self, article: Article) -> None:
        self._articles[article.article_id] = article

    def get(self, article_id: str) -> Optional[Article]:
        return self._articles.get(article_id)

    def all(self) -> List[Article]:
        return list(self._articles.values())

    def search(self, query: str = "") -> List[Article]:
        items = [a for a in self._articles.values() if a.matches(query)]
        return sorted(items, key=lambda a: a.published, reverse=True)

    def recent(self, hours: int = 24) -> List[Article]:
        return [a for a in self._articles.values() if a.is_recent(hours)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feed_id": self.feed_id,
            "name": self.name,
            "articles": [a.to_dict() for a in self._articles.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Feed":
        feed = cls(
            feed_id=str(raw.get("feed_id", "local")),
            name=str(raw.get("name", "Local Feed")),
        )
        for item in raw.get("articles", []):
            art = Article.from_dict(item)
            if art:
                feed.add(art)
        return feed


class HttpClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, feed_id: str) -> str:
        return f"{self.base_url}/feeds/{feed_id}.json"

    def fetch_feed(self, feed_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(feed_id)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except (error.URLError, OSError, ValueError):
            return None


def load_feed(path: Path) -> Feed:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Feed.from_dict(raw)
    except FileNotFoundError:
        return Feed(feed_id="local", name="Local Feed")
    except Exception:
        return Feed(feed_id="local", name="Local Feed")


def save_feed(path: Path, feed: Feed) -> None:
    payload = json.dumps(feed.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def summarize_feed(feed: Feed) -> Dict[str, Any]:
    articles = feed.all()
    if not articles:
        return {"count": 0, "avg_score": 0.0, "recent": 0}
    total = sum(a.score for a in articles)
    recent = sum(1 for a in articles if a.is_recent())
    return {
        "count": len(articles),
        "avg_score": total / len(articles),
        "recent": recent,
    }


def pick_random_article(feed: Feed, recent_only: bool = False) -> Optional[Article]:
    items = feed.all()
    if not items:
        return None
    if recent_only:
        rec = [a for a in items if a.is_recent()]
        if rec:
            return random.choice(rec)
    return random.choice(items)


def merge_remote_feed(local: Feed, remote_raw: Optional[Dict[str, Any]]) -> int:
    if not remote_raw:
        return 0
    remote = Feed.from_dict(remote_raw)
    added = 0
    for art in remote.all():
        if local.get(art.article_id) is None:
            local.add(art)
            added += 1
    return added


def enrich_scores(feed: Feed) -> None:
    articles = feed.all()
    if not articles:
        return
    now = datetime.utcnow()
    for a in articles:
        age_hours = max((now - a.published).total_seconds() / 3600.0, 1.0)
        base = 10.0 / age_hours
        if a.tags:
            base += len(a.tags) * 0.5
        a.score = round(base, 2)


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    feed_path = base / "feed.json"
    feed = load_feed(feed_path)

    if base_url:
        client = HttpClient(base_url=base_url)
        remote = client.fetch_feed(feed.feed_id)
        merge_remote_feed(feed, remote)

    enrich_scores(feed)
    summary = summarize_feed(feed)
    summary_path = base / "feed_summary.json"
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except OSError:
        return 1

    save_feed(feed_path, feed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
