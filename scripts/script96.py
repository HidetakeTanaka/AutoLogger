from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class NewsItem:
    item_id: str
    title: str
    category: str
    sentiment: float
    published_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_recent(self, hours: int = 24) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.published_at < cutoff:
            return False
        return True

    def matches_category(self, query: str) -> bool:
        q = query.lower().strip()
        if not q:
            return True
        if q in self.category.lower():
            return True
        return any((q in t.lower() for t in self.tags))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "category": self.category,
            "sentiment": self.sentiment,
            "published_at": self.published_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["NewsItem"]:
        try:
            ts_raw = raw.get("published_at")
            ts = (
                datetime.fromisoformat(ts_raw)
                if isinstance(ts_raw, str)
                else datetime.utcnow()
            )
            return cls(
                item_id=str(raw.get("item_id", "")),
                title=str(raw.get("title", "")),
                category=str(raw.get("category", "")),
                sentiment=float(raw.get("sentiment", 0.0)),
                published_at=ts,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class UserPrefs:
    user_id: str
    preferred_categories: List[str] = field(default_factory=list)
    min_sentiment: float = 0.0
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def prefers(self, category: str) -> bool:
        if not self.preferred_categories:
            return True
        return category.lower() in (c.lower() for c in self.preferred_categories)

    def needs_refresh(self, days: int = 7) -> bool:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.updated_at < cutoff

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "preferred_categories": list(self.preferred_categories),
            "min_sentiment": self.min_sentiment,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["UserPrefs"]:
        try:
            ts_raw = raw.get("updated_at")
            ts = (
                datetime.fromisoformat(ts_raw)
                if isinstance(ts_raw, str)
                else datetime.utcnow()
            )
            return cls(
                user_id=str(raw.get("user_id", "")),
                preferred_categories=list(raw.get("preferred_categories", [])),
                min_sentiment=float(raw.get("min_sentiment", 0.0)),
                updated_at=ts,
            )
        except Exception:
            return None


@dataclass
class FeedState:
    user_id: str
    prefs: Optional[UserPrefs] = None
    items: List[NewsItem] = field(default_factory=list)

    def add_item(self, item: NewsItem) -> None:
        self.items.append(item)

    def recent_items(self, hours: int = 24) -> List[NewsItem]:
        return [i for i in self.items if i.is_recent(hours)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "prefs": self.prefs.to_dict() if self.prefs else None,
            "items": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "FeedState":
        state = cls(user_id=str(raw.get("user_id", "local")))
        p_raw = raw.get("prefs")
        if isinstance(p_raw, dict):
            prefs = UserPrefs.from_dict(p_raw)
            if prefs:
                state.prefs = prefs
        for r in raw.get("items", []):
            item = NewsItem.from_dict(r)
            if item:
                state.items.append(item)
        return state


class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_remote_prefs(self, user_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(f"/prefs/{user_id}")
        if not url:
            return None
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            parsed = json.loads(data or "{}")
            if not isinstance(parsed, dict):
                return None
            return parsed
        except (error.URLError, ValueError, OSError):
            return None


def load_state(path: Path) -> FeedState:
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text or "{}")
        return FeedState.from_dict(raw)
    except FileNotFoundError:
        return FeedState(user_id="local")
    except Exception:
        return FeedState(user_id="local")


def save_state(path: Path, state: FeedState) -> None:
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return


def compute_category_stats(state: FeedState) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    scores: Dict[str, float] = {}
    for item in state.items:
        cat = item.category or "unknown"
        counts[cat] = counts.get(cat, 0) + 1
        scores[cat] = scores.get(cat, 0.0) + item.sentiment
    if not counts:
        return {"counts": {}, "avg_sentiment": {}}
    avg = {c: scores[c] / counts[c] for c in counts}
    return {"counts": counts, "avg_sentiment": avg}


def apply_remote_prefs(state: FeedState, client: RecommendationClient) -> Optional[UserPrefs]:
    remote = client.fetch_remote_prefs(state.user_id)
    if not remote:
        return None
    prefs = UserPrefs.from_dict(remote)
    if not prefs:
        return None
    state.prefs = prefs
    return prefs


def simulate_items(state: FeedState, days: int = 3) -> int:
    if days <= 0:
        return 0
    categories = ["tech", "sports", "finance", "entertainment"]
    created = 0
    now = datetime.utcnow()
    for d in range(days):
        day_base = now - timedelta(days=d)
        for _ in range(random.randint(1, 4)):
            cat = random.choice(categories)
            ts = day_base - timedelta(minutes=random.randint(0, 600))
            item = NewsItem(
                item_id=f"sim-{d}-{created}",
                title=f"Sample {cat} news {created}",
                category=cat,
                sentiment=random.uniform(-1.0, 1.0),
                published_at=ts,
                tags=[cat, "simulated"],
            )
            state.add_item(item)
            created += 1
    return created


def summarize_state(state: FeedState, today: Optional[date] = None) -> Dict[str, Any]:
    stats = compute_category_stats(state)
    today = today or date.today()
    recent = state.recent_items(24)
    prefs = state.prefs.to_dict() if state.prefs else None
    return {
        "user_id": state.user_id,
        "today": today.isoformat(),
        "total_items": len(state.items),
        "recent_items": len(recent),
        "prefs": prefs,
        "category_stats": stats,
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / "feed_state.json"
    state = load_state(state_path)
    if not state.items:
        simulate_items(state, days=2)
    client = RecommendationClient(base_url=base_url)
    apply_remote_prefs(state, client)
    summary = summarize_state(state)
    summary_path = base / "feed_summary.json"
    try:
        summary_payload = json.dumps(summary, indent=2, sort_keys=True)
        summary_path.write_text(summary_payload, encoding="utf-8")
    except OSError:
        return 1
    save_state(state_path, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
