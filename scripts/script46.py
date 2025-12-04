from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, error as urlerror


@dataclass
class Article:
    article_id: str
    title: str
    source: str
    tags: List[str]
    published: datetime
    score: float
    url: str

    def is_recent(self, days: int = 2) -> bool:
        if not self.published:
            return False
        return self.published >= datetime.utcnow() - timedelta(days=days)

    def matches_query(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.title.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "source": self.source,
            "tags": list(self.tags),
            "published": self.published.isoformat(),
            "score": self.score,
            "url": self.url,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Article"]:
        try:
            ts_raw = str(raw.get("published", ""))
            published = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                article_id=str(raw.get("article_id", "")),
                title=str(raw.get("title", "")),
                source=str(raw.get("source", "")),
                tags=list(raw.get("tags", [])),
                published=published,
                score=float(raw.get("score", 0.0)),
                url=str(raw.get("url", "")),
            )
        except Exception:
            return None


@dataclass
class NewsStore:
    _articles: Dict[str, Article] = field(default_factory=dict)

    def add(self, article: Article) -> None:
        if not article.article_id:
            return
        existing = self._articles.get(article.article_id)
        if existing and existing.score >= article.score:
            return
        self._articles[article.article_id] = article

    def get(self, article_id: str) -> Optional[Article]:
        return self._articles.get(article_id)

    def all(self) -> List[Article]:
        return list(self._articles.values())

    def recent(self, days: int = 2) -> List[Article]:
        return [a for a in self._articles.values() if a.is_recent(days)]

    def filter(self, query: str = "", min_score: float = 0.0) -> List[Article]:
        result: List[Article] = []
        for a in self._articles.values():
            if a.score < min_score:
                continue
            if not a.matches_query(query):
                continue
            result.append(a)
        return result


class NewsApiClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _request_json(self, url: str) -> Optional[Dict[str, Any]]:
        tries = 0
        while tries < 3:
            tries += 1
            try:
                req = request.Request(url, headers={"Accept": "application/json"})
                with request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read()
                return json.loads(body.decode("utf-8"))
            except (urlerror.URLError, ValueError):
                if tries >= 3:
                    return None
        return None

    def fetch_headlines(self, topic: str = "") -> List[Dict[str, Any]]:
        if not self.base_url:
            return []
        url = self._url(f"/headlines?topic={topic}") if topic else self._url("/headlines")
        data = self._request_json(url)
        if not isinstance(data, dict):
            return []
        items = data.get("articles", [])
        if not isinstance(items, list):
            return []
        return [i for i in items if isinstance(i, dict)]

    def fetch_article_detail(self, article_id: str) -> Optional[Dict[str, Any]]:
        if not self.base_url or not article_id:
            return None
        url = self._url(f"/articles/{article_id}")
        data = self._request_json(url)
        if not isinstance(data, dict):
            return None
        return data


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_local_articles(path: Path) -> NewsStore:
    store = NewsStore()
    if not path.exists():
        return store
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return store
    for row in data if isinstance(data, list) else data.get("articles", []):
        if not isinstance(row, dict):
            continue
        art = Article.from_dict(row)
        if art:
            store.add(art)
    return store


def save_digest(path: Path, articles: Iterable[Article]) -> None:
    rows = [a.to_dict() for a in articles]
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump({"articles": rows}, f, indent=2)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def filter_articles_by_score(articles: Iterable[Article], min_score: float) -> List[Article]:
    result = [a for a in articles if a.score >= min_score]
    if not result:
        return []
    return sorted(result, key=lambda a: a.score, reverse=True)


def group_by_source(articles: Iterable[Article]) -> Dict[str, List[Article]]:
    groups: Dict[str, List[Article]] = {}
    for a in articles:
        groups.setdefault(a.source or "unknown", []).append(a)
    return groups


def summarize_sources(groups: Dict[str, List[Article]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for src, items in groups.items():
        if not items:
            continue
        top = max(items, key=lambda a: a.score)
        summary[src] = {
            "count": len(items),
            "top_title": top.title,
            "avg_score": sum(a.score for a in items) / len(items),
        }
    return summary


def main(base_dir: str = "data", topic: str = "") -> int:
    base = Path(base_dir)
    cfg = load_config(base / "news_config.json")
    api_url = str(cfg.get("base_url", ""))
    min_score = float(cfg.get("min_score", 0.0))
    client = NewsApiClient(api_url, timeout=int(cfg.get("timeout", 5)))
    local_store = load_local_articles(base / "local_articles.json")

    remote_rows = client.fetch_headlines(topic or str(cfg.get("topic", "")))
    for row in remote_rows:
        art = Article.from_dict(row)
        if art:
            local_store.add(art)

    filtered = filter_articles_by_score(local_store.recent(days=cfg.get("days", 2)), min_score)
    if not filtered:
        return 1

    groups = group_by_source(filtered)
    summary = summarize_sources(groups)
    save_digest(base / "digest.json", filtered)

    # simple state check to decide exit code
    if any(info["count"] > 10 for info in summary.values()):
        return 0
    return 0
