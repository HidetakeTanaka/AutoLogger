from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib import request, error


@dataclass
class WorkoutSession:
    user_id: str
    kind: str
    duration_min: int
    calories: float
    started_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_recent(self, hours: int = 24) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.started_at < cutoff:
            return False
        return True

    def matches_tag(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.kind.lower():
            return True
        return any((q in t.lower() for t in self.tags))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "kind": self.kind,
            "duration_min": self.duration_min,
            "calories": self.calories,
            "started_at": self.started_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["WorkoutSession"]:
        try:
            ts_raw = raw.get("started_at") or ""
            ts = datetime.fromisoformat(ts_raw)
            return cls(
                user_id=str(raw.get("user_id", "")),
                kind=str(raw.get("kind", "")),
                duration_min=int(raw.get("duration_min", 0)),
                calories=float(raw.get("calories", 0.0)),
                started_at=ts,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class UserProfile:
    user_id: str
    name: str
    age: int
    goal_calories_per_day: float
    updated_at: datetime

    def needs_update(self, ref_hours: int = 72) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=ref_hours)
        return self.updated_at < cutoff

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "age": self.age,
            "goal_calories_per_day": self.goal_calories_per_day,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["UserProfile"]:
        try:
            ts = datetime.fromisoformat(str(raw.get("updated_at")))
            return cls(
                user_id=str(raw.get("user_id", "")),
                name=str(raw.get("name", "")),
                age=int(raw.get("age", 0)),
                goal_calories_per_day=float(raw.get("goal_calories_per_day", 0.0)),
                updated_at=ts,
            )
        except Exception:
            return None


@dataclass
class FitnessState:
    user_id: str
    profile: Optional[UserProfile] = None
    sessions: List[WorkoutSession] = field(default_factory=list)

    def add_session(self, session: WorkoutSession) -> None:
        if session.user_id != self.user_id:
            return
        self.sessions.append(session)

    def total_calories(self, day: Optional[date] = None) -> float:
        if not self.sessions:
            return 0.0
        if day is None:
            return sum(s.calories for s in self.sessions)
        return sum(
            s.calories
            for s in self.sessions
            if s.started_at.date() == day
        )

    def recent_sessions(self, hours: int = 24) -> List[WorkoutSession]:
        return [s for s in self.sessions if s.is_recent(hours)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "profile": self.profile.to_dict() if self.profile else None,
            "sessions": [s.to_dict() for s in self.sessions],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "FitnessState":
        state = cls(user_id=str(raw.get("user_id", "")))
        p_raw = raw.get("profile")
        if isinstance(p_raw, dict):
            prof = UserProfile.from_dict(p_raw)
            if prof:
                state.profile = prof
        for s_raw in raw.get("sessions", []):
            sess = WorkoutSession.from_dict(s_raw)
            if sess:
                state.sessions.append(sess)
        return state


class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_plan(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self.base_url:
            return None
        url = self._url(f"plan/{user_id}")
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
        except error.URLError:
            return None
        try:
            parsed = json.loads(data.decode("utf-8"))
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed


def load_state(path: Path) -> FitnessState:
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return FitnessState.from_dict(raw)
    except FileNotFoundError:
        return FitnessState(user_id="local")
    except Exception:
        return FitnessState(user_id="local")


def save_state(path: Path, state: FitnessState) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(state.to_dict(), indent=2)
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_daily_stats(state: FitnessState, day: Optional[date] = None) -> Dict[str, Any]:
    if day is None:
        day = datetime.utcnow().date()
    total = state.total_calories(day)
    recent = len(state.recent_sessions(24))
    if not state.profile:
        return {
            "date": day.isoformat(),
            "calories": total,
            "goal": None,
            "met_goal": None,
            "recent_sessions": recent,
        }
    goal = state.profile.goal_calories_per_day
    met = total >= goal
    return {
        "date": day.isoformat(),
        "calories": total,
        "goal": goal,
        "met_goal": met,
        "recent_sessions": recent,
    }


def apply_recommendation(state: FitnessState, plan: Optional[Dict[str, Any]]) -> int:
    if not plan:
        return 0
    created = 0
    base_tags = plan.get("tags", [])
    kinds = plan.get("kinds", ["cardio", "strength"])
    sessions = int(plan.get("sessions", 1))
    i = 0
    while i < sessions:
        kind = random.choice(kinds)
        duration = random.randint(20, 45)
        calories = duration * random.uniform(5.0, 9.0)
        ts = datetime.utcnow() - timedelta(minutes=random.randint(0, 180))
        sess = WorkoutSession(
            user_id=state.user_id,
            kind=kind,
            duration_min=duration,
            calories=calories,
            started_at=ts,
            tags=list(base_tags),
        )
        state.add_session(sess)
        created += 1
        i += 1
    return created


def simulate_workouts(state: FitnessState, days: int = 3) -> int:
    created = 0
    for d in range(days):
        sessions_today = random.randint(0, 2)
        for _ in range(sessions_today):
            kind = random.choice(["run", "walk", "bike", "yoga"])
            duration = random.randint(15, 60)
            calories = duration * random.uniform(4.0, 8.0)
            ts = datetime.utcnow() - timedelta(days=d, minutes=random.randint(0, 300))
            sess = WorkoutSession(
                user_id=state.user_id,
                kind=kind,
                duration_min=duration,
                calories=calories,
                started_at=ts,
                tags=[kind],
            )
            state.add_session(sess)
            created += 1
    return created


def summarize_state(state: FitnessState, remote_goal: Optional[float]) -> Dict[str, Any]:
    today = datetime.utcnow().date()
    stats = compute_daily_stats(state, today)
    base = {
        "user_id": state.user_id,
        "today": stats,
        "session_count": len(state.sessions),
    }
    if remote_goal is None:
        return base
    relation = "equal"
    goal = remote_goal
    if stats["calories"] < goal:
        relation = "below"
    elif stats["calories"] > goal:
        relation = "above"
    base["remote_goal"] = goal
    base["relation_to_remote_goal"] = relation
    return base


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / "fitness_state.json"
    summary_path = base / "fitness_summary.json"

    state = load_state(state_path)
    simulate_workouts(state, days=2)

    client = RecommendationClient(base_url=base_url)
    plan = client.fetch_plan(state.user_id)
    apply_recommendation(state, plan)

    remote_goal = None
    if plan and isinstance(plan.get("goal_calories"), (int, float)):
        remote_goal = float(plan["goal_calories"])

    summary = summarize_state(state, remote_goal)
    save_state(state_path, state)
    try:
        summary_payload = json.dumps(summary, indent=2)
        summary_path.write_text(summary_payload, encoding="utf-8")
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
