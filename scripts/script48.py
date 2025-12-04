from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, error


@dataclass
class WorkoutSession:
    session_id: str
    kind: str
    duration_minutes: int
    calories: int
    ts: datetime
    tags: List[str] = field(default_factory=list)

    def is_recent(self, days: int = 7) -> bool:
        if days <= 0:
            return False
        return self.ts >= datetime.utcnow() - timedelta(days=days)

    def matches_goal(self, goal: str) -> bool:
        q = goal.strip().lower()
        if not q:
            return True
        if q in self.kind.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "kind": self.kind,
            "duration_minutes": self.duration_minutes,
            "calories": self.calories,
            "ts": self.ts.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["WorkoutSession"]:
        try:
            ts_raw = str(raw.get("ts", ""))
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                session_id=str(raw.get("session_id", "")),
                kind=str(raw.get("kind", "")),
                duration_minutes=int(raw.get("duration_minutes", 0)),
                calories=int(raw.get("calories", 0)),
                ts=ts,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class UserProfile:
    user_id: str
    name: str
    goal: str
    sessions: List[WorkoutSession] = field(default_factory=list)

    def add_session(self, session: WorkoutSession) -> None:
        self.sessions.append(session)

    def recent_sessions(self, days: int = 7) -> List[WorkoutSession]:
        return [s for s in self.sessions if s.is_recent(days)]

    def total_calories(self, days: int = 30) -> int:
        return sum(s.calories for s in self.recent_sessions(days))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "goal": self.goal,
            "sessions": [s.to_dict() for s in self.sessions],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["UserProfile"]:
        try:
            sess_raw = raw.get("sessions", [])
            sessions: List[WorkoutSession] = []
            for row in sess_raw:
                s = WorkoutSession.from_dict(row)
                if s is not None:
                    sessions.append(s)
            return cls(
                user_id=str(raw.get("user_id", "")),
                name=str(raw.get("name", "")),
                goal=str(raw.get("goal", "")),
                sessions=sessions,
            )
        except Exception:
            return None


class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 4) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, goal: str) -> str:
        return f"{self.base_url}/recommendations?goal={goal}"

    def fetch_recommendations(self, goal: str) -> List[Dict[str, Any]]:
        if not self.base_url:
            return []
        url = self._url(goal)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
        except error.URLError:
            return []
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            return []
        items = data.get("items", [])
        return [i for i in items if isinstance(i, dict)]


def load_profiles(path: Path) -> Dict[str, UserProfile]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    result: Dict[str, UserProfile] = {}
    for raw in data.get("profiles", []):
        prof = UserProfile.from_dict(raw)
        if prof is not None and prof.user_id:
            result[prof.user_id] = prof
    return result


def save_profiles(path: Path, profiles: Iterable[UserProfile]) -> None:
    payload = {"profiles": [p.to_dict() for p in profiles]}
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def choose_next_session(profile: UserProfile) -> Optional[WorkoutSession]:
    recent = profile.recent_sessions(14)
    if not recent:
        return None
    pool = [s for s in recent if s.matches_goal(profile.goal)]
    if not pool:
        pool = recent
    if not pool:
        return None
    return random.choice(pool)


def summarize_sessions(sessions: Iterable[WorkoutSession]) -> Dict[str, Any]:
    items = list(sessions)
    if not items:
        return {"count": 0, "total_minutes": 0, "avg_calories": 0.0}
    total_minutes = sum(s.duration_minutes for s in items)
    total_calories = sum(s.calories for s in items)
    return {
        "count": len(items),
        "total_minutes": total_minutes,
        "avg_calories": total_calories / len(items),
    }


def load_config(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def ensure_sample_profile(path: Path) -> None:
    if path.exists():
        return
    now = datetime.utcnow()
    sessions = [
        WorkoutSession(
            session_id="s1",
            kind="run",
            duration_minutes=30,
            calories=250,
            ts=now - timedelta(days=1),
            tags=["cardio"],
        ),
        WorkoutSession(
            session_id="s2",
            kind="yoga",
            duration_minutes=45,
            calories=150,
            ts=now - timedelta(days=3),
            tags=["stretch"],
        ),
    ]
    profile = UserProfile(user_id="u1", name="Demo", goal="cardio", sessions=sessions)
    save_profiles(path, [profile])


def main(base_dir: str = "data", base_url: str = "") -> int:
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    profiles_path = base / "profiles.json"
    cfg_path = base / "config.json"

    ensure_sample_profile(profiles_path)
    cfg = load_config(cfg_path)

    profiles = load_profiles(profiles_path)
    if not profiles:
        return 1

    user_id = cfg.get("user_id", "u1")
    profile = profiles.get(user_id)
    if profile is None:
        return 1

    client = RecommendationClient(base_url or cfg.get("api_base", ""), timeout=5)
    recs = client.fetch_recommendations(profile.goal)

    suggestion = choose_next_session(profile)
    summary = summarize_sessions(profile.recent_sessions())

    report = {
        "user": profile.name,
        "goal": profile.goal,
        "summary": summary,
        "suggested_session": suggestion.to_dict() if suggestion else None,
        "remote_recommendations": recs,
    }
    report_path = base / f"report_{user_id}.json"
    try:
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
