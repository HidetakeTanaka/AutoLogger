from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterable


@dataclass
class Article:
    article_id: str
    title: str
    category: str
    views: int
    likes: int

    def popularity_score(self) -> float:
        if self.views <= 0:
            return float(self.likes)
        return self.likes / self.views * 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "category": self.category,
            "views": self.views,
            "likes": self.likes,
        }


@dataclass
class Recommendation:
    user_id: str
    article_id: str
    rank: int


class ArticleStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._articles: Dict[str, Article] = {}

    def load(self) -> None:
        if not self.path.exists():
            self._articles = {}
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._articles = {}
            return
        arts: Dict[str, Article] = {}
        for raw in data.get("articles", []):
            try:
                aid = str(raw["article_id"])
                title = str(raw.get("title", ""))
                cat = str(raw.get("category", ""))
                views = int(raw.get("views", 0))
                likes = int(raw.get("likes", 0))
            except (KeyError, ValueError):
                continue
            arts[aid] = Article(article_id=aid, title=title, category=cat, views=views, likes=likes)
        self._articles = arts

    def save(self) -> None:
        payload = {"articles": [a.to_dict() for a in self._articles.values()]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def get(self, article_id: str) -> Optional[Article]:
        return self._articles.get(article_id)

    def all(self) -> List[Article]:
        return list(self._articles.values())


class UserHistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Dict[str, List[str]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
        result: Dict[str, List[str]] = {}
        for raw in data.get("history", []):
            uid = str(raw.get("user_id", ""))
            if not uid:
                continue
            ids = [str(a) for a in raw.get("articles", [])]
            result[uid] = ids
        return result


def sort_articles_by_popularity(articles: Iterable[Article]) -> List[Article]:
    return sorted(articles, key=lambda a: a.popularity_score(), reverse=True)


def build_recommendations_for_user(
    user_id: str,
    history: List[str],
    articles: List[Article],
    limit: int = 5,
) -> List[Recommendation]:
    candidates = [a for a in articles if a.article_id not in history]
    ranked = sort_articles_by_popularity(candidates)
    recs: List[Recommendation] = []
    for idx, art in enumerate(ranked[:limit], start=1):
        recs.append(Recommendation(user_id=user_id, article_id=art.article_id, rank=idx))
    return recs


def build_recommendations(
    histories: Dict[str, List[str]],
    articles: List[Article],
    limit: int = 5,
) -> List[Recommendation]:
    all_recs: List[Recommendation] = []
    for uid, hist in histories.items():
        recs = build_recommendations_for_user(uid, hist, articles, limit=limit)
        all_recs.extend(recs)
    return all_recs


def export_recommendations(path: Path, recs: List[Recommendation]) -> None:
    payload = [
        {"user_id": r.user_id, "article_id": r.article_id, "rank": r.rank}
        for r in recs
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"recommendations": payload}, f, indent=2, ensure_ascii=False)


def compute_category_stats(articles: List[Article]) -> Dict[str, Any]:
    stats: Dict[str, Any] = {}
    for a in articles:
        cat = a.category or "unknown"
        entry = stats.setdefault(cat, {"count": 0, "total_views": 0, "total_likes": 0})
        entry["count"] += 1
        entry["total_views"] += a.views
        entry["total_likes"] += a.likes
    for cat, entry in stats.items():
        views = entry["total_views"]
        likes = entry["total_likes"]
        if views > 0:
            entry["like_rate"] = likes / views
        else:
            entry["like_rate"] = 0.0
    return stats


def export_category_stats(path: Path, stats: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"categories": stats}, f, indent=2, ensure_ascii=False)


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    base = Path("data")
    articles_path = base / "articles.json"
    history_path = base / "history.json"
    recs_path = base / "recommendations.json"
    stats_path = base / "category_stats.json"
    config_path = base / "rec_config.json"

    store = ArticleStore(articles_path)
    store.load()
    if not store.all():
        return 1

    history_store = UserHistoryStore(history_path)
    histories = history_store.load()

    articles = store.all()
    recs = build_recommendations(histories, articles, limit=5)
    export_recommendations(recs_path, recs)

    stats = compute_category_stats(articles)
    export_category_stats(stats_path, stats)

    cfg = load_config(config_path)
    if cfg.get("debug_mode"):
        _ = sort_articles_by_popularity(articles)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
