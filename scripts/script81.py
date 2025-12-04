from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
import json
import random
import urllib.request
import urllib.error


@dataclass
class Workout:
    user_id: str
    workout_id: str
    kind: str
    duration_min: int
    calories: int
    tags: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def is_recent(self, hours: int = 24) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.timestamp < cutoff:
            return False
        return True

    def matches_kind(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.kind.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "workout_id": self.workout_id,
            "kind": self.kind,
            "duration_min": self.duration_min,
            "calories": self.calories,
            "tags": list(self.tags),
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Workout"]:
        try:
            ts_raw = str(raw.get("timestamp", ""))
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                user_id=str(raw.get("user_id", "")),
                workout_id=str(raw.get("workout_id", "")),
                kind=str(raw.get("kind", "")),
                duration_min=int(raw.get("duration_min", 0)),
                calories=int(raw.get("calories", 0)),
                tags=list(raw.get("tags", [])),
                timestamp=ts,
            )
        except Exception:
            return None


@dataclass
class WorkoutLog:
    user_id: str
    workouts: List[Workout] = field(default_factory=list)

    def add_workout(self, workout: Workout) -> None:
        if workout.user_id != self.user_id:
            return
        self.workouts.append(workout)

    def filter_by_kind(self, query: str = "") -> List[Workout]:
        return [w for w in self.workouts if w.matches_kind(query)]

    def recent_workouts(self, hours: int = 24) -> List[Workout]:
        return [w for w in self.workouts if w.is_recent(hours)]

    def total_calories(self, day: Optional[date] = None) -> int:
        if not day:
            return sum(w.calories for w in self.workouts)
        return sum(
            w.calories for w in self.workouts if w.timestamp.date() == day
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "workouts": [w.to_dict() for w in self.workouts],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "WorkoutLog":
        log = cls(user_id=str(raw.get("user_id", "")))
        for w_raw in raw.get("workouts", []):
            w = Workout.from_dict(w_raw)
            if w is not None:
                log.add_workout(w)
        return log


class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, kind: str) -> str:
        return f"{self.base_url}/recommend?kind={kind}"

    def fetch_suggestions(self, kind: str) -> Optional[List[Dict[str, Any]]]:
        if not self.base_url:
            return None
        url = self._url(kind)
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            payload = json.loads(data)
            items = payload.get("suggestions")
            if not isinstance(items, list):
                return None
            return items
        except (urllib.error.URLError, ValueError, KeyError):
            return None


def load_log(path: Path) -> WorkoutLog:
    if not path.exists():
        return WorkoutLog(user_id="local")
    try:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        return WorkoutLog.from_dict(data)
    except Exception:
        return WorkoutLog(user_id="local")


def save_log(path: Path, log: WorkoutLog) -> None:
    payload = log.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def compute_daily_summary(log: WorkoutLog, day: date) -> Dict[str, Any]:
    day_workouts = [w for w in log.workouts if w.timestamp.date() == day]
    if not day_workouts:
        return {"date": day.isoformat(), "count": 0, "duration": 0, "calories": 0}
    total_duration = sum(w.duration_min for w in day_workouts)
    total_cal = sum(w.calories for w in day_workouts)
    return {
        "date": day.isoformat(),
        "count": len(day_workouts),
        "duration": total_duration,
        "calories": total_cal,
    }


def simulate_day(log: WorkoutLog, target_calories: int = 400) -> int:
    if not log.workouts:
        return 0
    added = 0
    total = 0
    while total < target_calories and added < 5:
        base = random.choice(log.workouts)
        w = Workout(
            user_id=log.user_id,
            workout_id=f"sim-{datetime.utcnow().timestamp()}-{added}",
            kind=base.kind,
            duration_min=max(10, int(base.duration_min * random.uniform(0.5, 1.2))),
            calories=max(50, int(base.calories * random.uniform(0.5, 1.2))),
            tags=list(base.tags),
            timestamp=datetime.utcnow(),
        )
        log.add_workout(w)
        total += w.calories
        added += 1
    return added


def merge_remote_recs(log: WorkoutLog, recs: Optional[List[Dict[str, Any]]]) -> int:
    if not recs:
        return 0
    added = 0
    for raw in recs:
        w = Workout.from_dict(raw)
        if w is None:
            continue
        if w.workout_id in {x.workout_id for x in log.workouts}:
            continue
        w.user_id = log.user_id
        log.add_workout(w)
        added += 1
    return added


def summarize(log: WorkoutLog) -> Dict[str, Any]:
    today = datetime.utcnow().date()
    return {
        "user_id": log.user_id,
        "total_workouts": len(log.workouts),
        "total_calories": log.total_calories(),
        "today_calories": log.total_calories(today),
        "recent_24h": len(log.recent_workouts(24)),
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    store_path = base / "workouts.json"
    summary_path = base / "summary.json"

    log = load_log(store_path)

    if not log.workouts:
        for i in range(3):
            log.add_workout(
                Workout(
                    user_id=log.user_id,
                    workout_id=f"seed-{i}",
                    kind=random.choice(["run", "bike", "yoga"]),
                    duration_min=random.randint(20, 60),
                    calories=random.randint(150, 500),
                    tags=["seed"],
                )
            )

    simulate_day(log)
    client = RecommendationClient(base_url=base_url) if base_url else None
    if client:
        recs = client.fetch_suggestions("run")
        merge_remote_recs(log, recs)

    save_log(store_path, log)
    summary = summarize(log)
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
