from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class WorkoutSession:
    session_id: str
    user_id: str
    start: datetime
    duration_min: int
    calories: float
    tags: List[str] = field(default_factory=list)

    def is_long(self, threshold: int = 45) -> bool:
        if self.duration_min <= 0:
            return False
        return self.duration_min >= threshold

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.session_id.lower() or q in self.user_id.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "start": self.start.isoformat(),
            "duration_min": self.duration_min,
            "calories": self.calories,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["WorkoutSession"]:
        try:
            start_raw = raw.get("start")
            start = (
                datetime.fromisoformat(start_raw)
                if isinstance(start_raw, str)
                else datetime.utcnow()
            )
            return cls(
                session_id=str(raw.get("session_id", "")),
                user_id=str(raw.get("user_id", "")),
                start=start,
                duration_min=int(raw.get("duration_min", 0)),
                calories=float(raw.get("calories", 0.0)),
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class UserProfile:
    user_id: str
    name: str
    goal_minutes_per_week: int = 150
    sessions: List[WorkoutSession] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_session(self, session: WorkoutSession) -> None:
        if session.user_id != self.user_id:
            return
        self.sessions.append(session)
        self.updated_at = datetime.utcnow()

    def total_minutes(self) -> int:
        return sum(s.duration_min for s in self.sessions)

    def weekly_progress(self, ref: Optional[datetime] = None) -> float:
        ref = ref or datetime.utcnow()
        week_start = ref - timedelta(days=7)
        minutes = sum(
            s.duration_min for s in self.sessions if s.start >= week_start
        )
        if self.goal_minutes_per_week <= 0:
            return 0.0
        return min(1.0, minutes / self.goal_minutes_per_week)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "goal_minutes_per_week": self.goal_minutes_per_week,
            "updated_at": self.updated_at.isoformat(),
            "sessions": [s.to_dict() for s in self.sessions],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "UserProfile":
        updated_raw = raw.get("updated_at")
        try:
            updated = (
                datetime.fromisoformat(updated_raw)
                if isinstance(updated_raw, str)
                else datetime.utcnow()
            )
        except Exception:
            updated = datetime.utcnow()
        profile = cls(
            user_id=str(raw.get("user_id", "")),
            name=str(raw.get("name", "")),
            goal_minutes_per_week=int(raw.get("goal_minutes_per_week", 150)),
            updated_at=updated,
        )
        for s_raw in raw.get("sessions", []):
            s = WorkoutSession.from_dict(s_raw)
            if s:
                profile.sessions.append(s)
        return profile


class AnalyticsClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, user_id: str) -> str:
        return f"{self.base_url}/benchmarks/{user_id}.json"

    def fetch_benchmarks(self, user_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(user_id)
        if not self.base_url:
            return None
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except (error.URLError, error.HTTPError, TimeoutError, ValueError):
            return None

    def push_summary(self, user_id: str, summary: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = self._url(user_id)
        body = json.dumps(summary).encode("utf-8")
        try:
            req = request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (error.URLError, error.HTTPError, TimeoutError):
            return False


def load_profile(path: Path) -> UserProfile:
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return UserProfile.from_dict(raw)
    except Exception:
        return UserProfile(user_id="local", name="Local User")


def save_profile(path: Path, profile: UserProfile) -> None:
    payload = profile.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def summarize_profile(profile: UserProfile) -> Dict[str, Any]:
    if not profile.sessions:
        return {
            "user_id": profile.user_id,
            "name": profile.name,
            "session_count": 0,
            "total_minutes": 0,
            "weekly_progress": 0.0,
        }
    long_sessions = sum(1 for s in profile.sessions if s.is_long())
    return {
        "user_id": profile.user_id,
        "name": profile.name,
        "session_count": len(profile.sessions),
        "total_minutes": profile.total_minutes(),
        "weekly_progress": profile.weekly_progress(),
        "long_sessions": long_sessions,
    }


def simulate_week(profile: UserProfile, days: int = 7) -> None:
    for day in range(days):
        if random.random() < 0.4:
            continue
        duration = random.randint(20, 70)
        calories = duration * random.uniform(5.0, 10.0)
        start = datetime.utcnow() - timedelta(days=(days - day))
        session = WorkoutSession(
            session_id=f"s{len(profile.sessions)+1}",
            user_id=profile.user_id,
            start=start,
            duration_min=duration,
            calories=calories,
            tags=["simulated"],
        )
        profile.add_session(session)


def merge_benchmarks(
    summary: Dict[str, Any], benchmarks: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if not benchmarks:
        return summary
    result = dict(summary)
    target = float(benchmarks.get("recommended_goal_minutes", 0.0))
    result["recommended_goal_minutes"] = target
    if target > 0 and summary.get("total_minutes", 0) < target:
        result["status"] = "below_benchmark"
    else:
        result["status"] = "on_track"
    return result


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    profile_path = base / "profile.json"
    profile = load_profile(profile_path)
    if not profile.sessions:
        simulate_week(profile)
    summary = summarize_profile(profile)
    client = AnalyticsClient(base_url=base_url)
    remote = client.fetch_benchmarks(profile.user_id)
    merged = merge_benchmarks(summary, remote)
    save_profile(profile_path, profile)
    summary_path = base / "summary.json"
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
    except Exception:
        return 1
    if base_url:
        client.push_summary(profile.user_id, merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


