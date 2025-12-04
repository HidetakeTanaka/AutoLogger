from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request


@dataclass
class StudentSession:
    student_id: str
    course_id: str
    started_at: datetime
    duration_min: int
    completed: bool = False
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
        if any(q in t.lower() for t in self.tags):
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "student_id": self.student_id,
            "course_id": self.course_id,
            "started_at": self.started_at.isoformat(),
            "duration_min": self.duration_min,
            "completed": self.completed,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["StudentSession"]:
        try:
            ts_raw = raw.get("started_at")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                student_id=str(raw.get("student_id", "")),
                course_id=str(raw.get("course_id", "")),
                started_at=ts,
                duration_min=int(raw.get("duration_min", 0)),
                completed=bool(raw.get("completed", False)),
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class CourseInfo:
    course_id: str
    title: str
    level: str
    tags: List[str]
    last_updated: datetime

    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        if not q:
            return True
        if q in self.title.lower() or q in self.level.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "title": self.title,
            "level": self.level,
            "tags": self.tags,
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["CourseInfo"]:
        try:
            ts_raw = raw.get("last_updated")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                course_id=str(raw.get("course_id", "")),
                title=str(raw.get("title", "")),
                level=str(raw.get("level", "")),
                tags=list(raw.get("tags", [])),
                last_updated=ts,
            )
        except Exception:
            return None


@dataclass
class ProgressStore:
    user_id: str
    sessions: List[StudentSession] = field(default_factory=list)
    courses: Dict[str, CourseInfo] = field(default_factory=dict)

    def add_session(self, session: StudentSession) -> None:
        self.sessions.append(session)

    def total_minutes(self, course_id: Optional[str] = None) -> int:
        if course_id is None:
            return sum(s.duration_min for s in self.sessions)
        return sum(s.duration_min for s in self.sessions if s.course_id == course_id)

    def recent_sessions(self, hours: int = 24) -> List[StudentSession]:
        return [s for s in self.sessions if s.is_recent(hours)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "sessions": [s.to_dict() for s in self.sessions],
            "courses": [c.to_dict() for c in self.courses.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ProgressStore":
        store = cls(user_id=str(raw.get("user_id", "local")))
        for s_raw in raw.get("sessions", []):
            s = StudentSession.from_dict(s_raw)
            if s is not None:
                store.sessions.append(s)
        for c_raw in raw.get("courses", []):
            c = CourseInfo.from_dict(c_raw)
            if c is not None:
                store.courses[c.course_id] = c
        return store


class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, topic: str) -> str:
        return f"{self.base_url}/courses?topic={topic}"

    def fetch_recommendations(self, topic: str) -> Optional[List[Dict[str, Any]]]:
        if not self.base_url:
            return None
        url = self._url(topic)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            parsed = json.loads(data)
            items = parsed.get("results")
            if not isinstance(items, list):
                return None
            return items
        except (error.URLError, error.HTTPError, json.JSONDecodeError, KeyError):
            return None


def load_store(path: Path) -> ProgressStore:
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return ProgressStore.from_dict(raw)
    except FileNotFoundError:
        return ProgressStore(user_id="local")
    except Exception:
        return ProgressStore(user_id="local")


def save_store(path: Path, store: ProgressStore) -> None:
    payload = json.dumps(store.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_course_totals(store: ProgressStore) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for s in store.sessions:
        totals[s.course_id] = totals.get(s.course_id, 0) + s.duration_min
    return totals


def apply_recommendations(store: ProgressStore, recs: Optional[List[Dict[str, Any]]]) -> int:
    if not recs:
        return 0
    added = 0
    for r in recs:
        cid = str(r.get("course_id", ""))
        if not cid or cid in store.courses:
            continue
        info = CourseInfo.from_dict(
            {
                "course_id": cid,
                "title": r.get("title", ""),
                "level": r.get("level", "unknown"),
                "tags": r.get("tags", []),
                "last_updated": r.get("last_updated", datetime.utcnow().isoformat()),
            }
        )
        if info is None:
            continue
        store.courses[cid] = info
        added += 1
    return added


def simulate_study(store: ProgressStore, days: int = 3) -> int:
    if not store.courses:
        return 0
    course_ids = list(store.courses.keys())
    created = 0
    for d in range(days):
        for _ in range(random.randint(0, 2)):
            cid = random.choice(course_ids)
            sess = StudentSession(
                student_id=store.user_id,
                course_id=cid,
                started_at=datetime.utcnow() - timedelta(days=days - d),
                duration_min=random.randint(10, 60),
                completed=bool(random.getrandbits(1)),
                tags=["simulated"],
            )
            store.add_session(sess)
            created += 1
    return created


def summarize(store: ProgressStore) -> Dict[str, Any]:
    totals = compute_course_totals(store)
    if not totals:
        return {"user_id": store.user_id, "courses": 0, "sessions": 0, "minutes": 0}
    most_course = max(totals, key=totals.get)
    return {
        "user_id": store.user_id,
        "courses": len(store.courses),
        "sessions": len(store.sessions),
        "minutes": sum(totals.values()),
        "top_course": most_course,
        "top_course_minutes": totals[most_course],
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    store_path = base / "progress.json"
    store = load_store(store_path)
    client = RecommendationClient(base_url=base_url, timeout=5)
    recs = client.fetch_recommendations("python")
    apply_recommendations(store, recs)
    simulate_study(store, days=3)
    summary = summarize(store)
    summary_path = base / "summary.json"
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        save_store(store_path, store)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
