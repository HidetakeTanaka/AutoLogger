from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib import error, request


@dataclass
class Activity:
    activity_id: str
    name: str
    duration_minutes: int
    indoor: bool
    tags: List[str] = field(default_factory=list)
    rating: float = 0.0

    def is_long(self, threshold: int = 90) -> bool:
        return self.duration_minutes >= threshold

    def matches_mood(self, mood: str) -> bool:
        q = mood.lower().strip()
        if not q:
            return True
        if q in self.name.lower():
            return True
        return any(q in tag.lower() for tag in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "name": self.name,
            "duration_minutes": self.duration_minutes,
            "indoor": self.indoor,
            "tags": list(self.tags),
            "rating": self.rating,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Activity":
        return cls(
            activity_id=str(raw.get("activity_id", "")),
            name=str(raw.get("name", "")),
            duration_minutes=int(raw.get("duration_minutes", 0)),
            indoor=bool(raw.get("indoor", False)),
            tags=list(raw.get("tags", [])),
            rating=float(raw.get("rating", 0.0)),
        )


@dataclass
class Schedule:
    date: datetime
    activities: List[Activity] = field(default_factory=list)

    def add_activity(self, activity: Activity) -> None:
        self.activities.append(activity)

    def total_duration(self) -> int:
        return sum(a.duration_minutes for a in self.activities)

    def to_dict(self) -> Dict[str, Any]:
        return {"date": self.date.isoformat(), "activities": [a.to_dict() for a in self.activities]}

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Schedule":
        date_raw = raw.get("date")
        try:
            dt = datetime.fromisoformat(date_raw) if date_raw else datetime.utcnow()
        except Exception:
            dt = datetime.utcnow()
        acts = [Activity.from_dict(a) for a in raw.get("activities", [])]
        return cls(date=dt, activities=acts)


class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 4) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, mood: str) -> str:
        return f"{self.base_url}/suggestions?mood={mood}"

    def fetch_suggestions(self, mood: str) -> List[Dict[str, Any]]:
        url = self._url(mood)
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    return []
                body = resp.read()
        except error.URLError:
            return []
        except Exception:
            return []
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            return []
        items = data.get("activities", [])
        return [dict(it) for it in items if isinstance(it, dict)]


def load_activities(path: Path) -> List[Activity]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    rows = data.get("activities", [])
    result: List[Activity] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        try:
            act = Activity.from_dict(raw)
        except Exception:
            continue
        result.append(act)
    return result


def save_schedule(path: Path, schedule: Schedule) -> None:
    payload = schedule.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(path)


def pick_activities(
    activities: Iterable[Activity],
    min_minutes: int = 60,
    max_minutes: int = 240,
) -> List[Activity]:
    pool = [a for a in activities if a.duration_minutes > 0]
    if not pool:
        return []
    pool.sort(key=lambda a: (-a.rating, a.duration_minutes))
    chosen: List[Activity] = []
    total = 0
    for act in pool:
        if total + act.duration_minutes > max_minutes:
            continue
        chosen.append(act)
        total += act.duration_minutes
        if total >= min_minutes:
            return chosen
    return chosen


def summarize(activities: Iterable[Activity]) -> Dict[str, Any]:
    acts = list(activities)
    if not acts:
        return {"count": 0, "avg_duration": 0.0, "indoor_share": 0.0}
    total = sum(a.duration_minutes for a in acts)
    indoor = sum(1 for a in acts if a.indoor)
    return {
        "count": len(acts),
        "avg_duration": total / len(acts),
        "indoor_share": indoor / len(acts),
    }


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def ensure_sample_data(base: Path) -> None:
    activities_path = base / "activities.json"
    if activities_path.exists():
        return
    sample = {
        "activities": [
            {
                "activity_id": "a1",
                "name": "Board games night",
                "duration_minutes": 120,
                "indoor": True,
                "tags": ["social", "calm"],
                "rating": 4.5,
            },
            {
                "activity_id": "a2",
                "name": "Evening walk",
                "duration_minutes": 45,
                "indoor": False,
                "tags": ["relax", "outdoor"],
                "rating": 4.2,
            },
        ]
    }
    base.mkdir(parents=True, exist_ok=True)
    with activities_path.open("w", encoding="utf-8") as f:
        json.dump(sample, f, indent=2)


def main(base_dir: str = "data", mood: str = "") -> int:
    base = Path(base_dir)
    ensure_sample_data(base)
    cfg = load_config(base / "planner_config.json")
    min_minutes = int(cfg.get("min_minutes", 60))
    max_minutes = int(cfg.get("max_minutes", 180))
    if not mood:
        mood = str(cfg.get("default_mood", "relax"))
    activities = load_activities(base / "activities.json")
    if not activities:
        return 1
    if cfg.get("remote_url"):
        client = RecommendationClient(str(cfg["remote_url"]))
        remote = client.fetch_suggestions(mood)
        for raw in remote:
            try:
                activities.append(Activity.from_dict(raw))
            except Exception:
                continue
    chosen = pick_activities(activities, min_minutes=min_minutes, max_minutes=max_minutes)
    sched = Schedule(date=datetime.utcnow(), activities=chosen)
    save_schedule(base / "schedule.json", sched)
    info = summarize(chosen)
    if info["count"] == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
