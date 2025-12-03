import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib import error, request


@dataclass
class Article:
    article_id: str
    title: str
    author: str
    published: datetime
    tags: List[str] = field(default_factory=list)
    views: int = 0

    def is_recent(self, days: int = 7) -> bool:
        if days <= 0:
            return False
        return self.published >= datetime.utcnow() - timedelta(days=days)

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
            "views": self.views,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Article"]:
        try:
            ts_raw = str(raw.get("published", ""))
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                article_id=str(raw.get("article_id", "")),
                title=str(raw.get("title", "")),
                author=str(raw.get("author", "")),
                published=ts,
                tags=list(raw.get("tags", [])),
                views=int(raw.get("views", 0)),
            )
        except Exception:
            return None


@dataclass
class Feed:
    feed_id: str
    name: str
    articles: List[Article] = field(default_factory=list)

    def add_article(self, article: Article) -> None:
        for existing in self.articles:
            if existing.article_id == article.article_id:
                return
        self.articles.append(article)

    def recent_articles(self, days: int = 7) -> List[Article]:
        return [a for a in self.articles if a.is_recent(days)]

    def search(self, query: str) -> List[Article]:
        return [a for a in self.articles if a.matches(query)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feed_id": self.feed_id,
            "name": self.name,
            "articles": [a.to_dict() for a in self.articles],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Feed":
        feed = cls(feed_id=str(raw.get("feed_id", "")), name=str(raw.get("name", "")))
        for item in raw.get("articles", []):
            art = Article.from_dict(item)
            if art is not None:
                feed.add_article(art)
        return feed


class SyncClient:
    def __init__(self, base_url: str, timeout: int = 4) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, feed_id: str) -> str:
        return f"{self.base_url}/feeds/{feed_id}.json"

    def fetch_remote_feed(self, feed_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(feed_id)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
            return json.loads(body.decode("utf-8"))
        except (error.URLError, json.JSONDecodeError, TimeoutError):
            return None


def load_feed(path: Path) -> Feed:
    if not path.exists():
        return Feed(feed_id="local", name="Local Feed")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return Feed.from_dict(data)
    except Exception:
        return Feed(feed_id="local", name="Local Feed")


def save_feed(path: Path, feed: Feed) -> None:
    payload = feed.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def summarize_feed(feed: Feed) -> Dict[str, Any]:
    items = feed.articles
    if not items:
        return {"count": 0, "authors": {}, "avg_views": 0.0}
    authors: Dict[str, int] = {}
    views = 0
    idx = 0
    while idx < len(items):
        art = items[idx]
        views += art.views
        authors[art.author] = authors.get(art.author, 0) + 1
        idx += 1
    return {
        "count": len(items),
        "authors": authors,
        "avg_views": views / len(items),
    }


def filter_articles(feed: Feed, min_views: int = 0, recent_days: Optional[int] = None) -> List[Article]:
    result: List[Article] = []
    for art in feed.articles:
        if art.views < min_views:
            continue
        if recent_days is not None and not art.is_recent(recent_days):
            continue
        result.append(art)
    return result


def paginate_titles(articles: Iterable[Article], page_size: int = 5) -> List[List[str]]:
    items = list(articles)
    if page_size <= 0:
        return [ [a.title for a in items] ]
    pages: List[List[str]] = []
    i = 0
    while i < len(items):
        pages.append([a.title for a in items[i : i + page_size]])
        i += page_size
    return pages


def pick_random_article(feed: Feed, recent_only: bool = False) -> Optional[Article]:
    if recent_only:
        candidates = feed.recent_articles()
    else:
        candidates = list(feed.articles)
    if not candidates:
        return None
    return random.choice(candidates)


def merge_remote(feed: Feed, remote_rows: Iterable[Dict[str, Any]]) -> int:
    added = 0
    by_id = {a.article_id: a for a in feed.articles}
    for row in remote_rows:
        art = Article.from_dict(row)
        if art is None:
            continue
        if art.article_id in by_id:
            local = by_id[art.article_id]
            if art.published > local.published:
                local.title = art.title
                local.author = art.author
                local.tags = art.tags
                local.views = art.views
        else:
            feed.add_article(art)
            added += 1
    return added


def main(base_dir: str = "data", base_url: str = "") -> int:
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    feed_path = base / "feed.json"
    feed = load_feed(feed_path)

    client = SyncClient(base_url=base_url or "https://example.com", timeout=4)
    remote = client.fetch_remote_feed(feed.feed_id or "default")
    if remote is not None:
        added = merge_remote(feed, remote.get("articles", []))
        if added > 0:
            save_feed(feed_path, feed)

    summary = summarize_feed(feed)
    report_path = base / "feed_report.json"
    try:
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except Exception:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
