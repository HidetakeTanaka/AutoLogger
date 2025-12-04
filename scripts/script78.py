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
    url: str
    published_at: datetime
    tags: List[str] = field(default_factory=list)
    read: bool = False

    def is_recent(self, hours: int = 24) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.published_at < cutoff:
            return False
        return True

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.title.lower() or q in self.url.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def mark_read(self) -> None:
        self.read = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "tags": self.tags,
            "read": self.read,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Article"]:
        try:
            ts_raw = raw.get("published_at") or ""
            ts = datetime.fromisoformat(ts_raw)
            return cls(
                article_id=str(raw.get("article_id", "")),
                title=str(raw.get("title", "")),
                url=str(raw.get("url", "")),
                published_at=ts,
                tags=list(raw.get("tags", [])),
                read=bool(raw.get("read", False)),
            )
        except Exception:
            return None


@dataclass
class FeedState:
    feed_id: str
    name: str
    articles: List[Article] = field(default_factory=list)

    def add_article(self, article: Article) -> None:
        if any(a.article_id == article.article_id for a in self.articles):
            return
        self.articles.append(article)

    def unread(self) -> List[Article]:
        return [a for a in self.articles if not a.read]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feed_id": self.feed_id,
            "name": self.name,
            "articles": [a.to_dict() for a in self.articles],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "FeedState":
        feed = cls(feed_id=str(raw.get("feed_id", "")), name=str(raw.get("name", "")))
        for ar in raw.get("articles", []):
            art = Article.from_dict(ar)
            if art is not None:
                feed.add_article(art)
        return feed


class NewsClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, topic: str) -> str:
        return f"{self.base_url}/search?q={topic}"

    def fetch_feed(self, topic: str) -> Optional[List[Dict[str, Any]]]:
        if not self.base_url:
            return None
        url = self._url(topic)
        try:
            req = request.Request(url, headers={"Accept": "application/json"})
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
        except error.URLError:
            return None
        except Exception:
            return None
        try:
            parsed = json.loads(data.decode("utf-8"))
            items = parsed.get("items") or parsed.get("articles") or []
            return items if isinstance(items, list) else None
        except Exception:
            return None


def load_feeds(path: Path) -> List[FeedState]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    feeds: List[FeedState] = []
    for obj in raw:
        if isinstance(obj, dict):
            feeds.append(FeedState.from_dict(obj))
    return feeds


def save_feeds(path: Path, feeds: List[FeedState]) -> None:
    payload = [f.to_dict() for f in feeds]
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def merge_feed(
    feeds: List[FeedState],
    feed_id: str,
    name: str,
    items: Optional[List[Dict[str, Any]]],
) -> FeedState:
    index = {f.feed_id: f for f in feeds}
    feed = index.get(feed_id) or FeedState(feed_id=feed_id, name=name)
    if feed not in feeds:
        feeds.append(feed)
    if not items:
        return feed
    for item in items:
        aid = str(item.get("id") or item.get("url") or "")
        if not aid:
            continue
        tags = item.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        ts_raw = item.get("published_at") or item.get("pub_date") or ""
        try:
            ts = datetime.fromisoformat(ts_raw)
        except Exception:
            ts = datetime.utcnow()
        art = Article(
            article_id=aid,
            title=str(item.get("title", "")),
            url=str(item.get("url", "")),
            published_at=ts,
            tags=list(tags),
        )
        feed.add_article(art)
    return feed


def summarize_feeds(feeds: List[FeedState]) -> Dict[str, Any]:
    total_articles = sum(len(f.articles) for f in feeds)
    total_unread = sum(len(f.unread()) for f in feeds)
    recent = sum(
        1
        for f in feeds
        for a in f.articles
        if a.is_recent(24)
    )
    return {
        "feeds": len(feeds),
        "articles": total_articles,
        "unread": total_unread,
        "recent_24h": recent,
    }


def simulate_reading(feeds: List[FeedState], max_items: int = 5) -> int:
    unread = [a for f in feeds for a in f.unread()]
    if not unread or max_items <= 0:
        return 0
    read_count = 0
    random.shuffle(unread)
    i = 0
    while i < len(unread) and read_count < max_items:
        unread[i].mark_read()
        read_count += 1
        i += 1
    return read_count


def find_trending_tags(feeds: List[FeedState], min_count: int = 2) -> List[str]:
    counts: Dict[str, int] = {}
    for f in feeds:
        for a in f.articles:
            for t in a.tags:
                key = t.lower()
                counts[key] = counts.get(key, 0) + 1
    tags = [tag for tag, c in counts.items() if c >= min_count]
    return sorted(tags)


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    store_path = base / "feeds.json"
    summary_path = base / "summary.json"
    feeds = load_feeds(store_path)
    client = NewsClient(base_url=base_url) if base_url else None

    try:
        topics = ["tech", "world", "sports"]
        if client is not None:
            for topic in topics:
                items = client.fetch_feed(topic)
                merge_feed(feeds, feed_id=topic, name=topic.title(), items=items)
        simulate_reading(feeds, max_items=7)
        summary = summarize_feeds(feeds)
        summary["trending_tags"] = find_trending_tags(feeds)
        save_feeds(store_path, feeds)
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            with summary_path.open("w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
        except Exception:
            return 1
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
