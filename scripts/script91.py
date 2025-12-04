from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class Task:
    task_id: str
    title: str
    priority: int
    estimated_minutes: int
    created_at: datetime
    completed: bool = False
    tags: List[str] = field(default_factory=list)

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        if now is None:
            now = datetime.utcnow()
        cutoff = self.created_at + timedelta(days=2)
        if self.completed:
            return False
        return now > cutoff

    def matches_tag(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        return any((q in t.lower() for t in self.tags))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "priority": self.priority,
            "estimated_minutes": self.estimated_minutes,
            "created_at": self.created_at.isoformat(),
            "completed": self.completed,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Task"]:
        try:
            ts = datetime.fromisoformat(str(raw.get("created_at", "")))
            return cls(
                task_id=str(raw.get("task_id", "")),
                title=str(raw.get("title", "")),
                priority=int(raw.get("priority", 0)),
                estimated_minutes=int(raw.get("estimated_minutes", 0)),
                created_at=ts,
                completed=bool(raw.get("completed", False)),
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class UserSettings:
    user_id: str
    daily_capacity: int
    timezone: str
    updated_at: datetime

    def needs_refresh(self, hours: int = 72) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return self.updated_at < cutoff

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "daily_capacity": self.daily_capacity,
            "timezone": self.timezone,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["UserSettings"]:
        try:
            ts = datetime.fromisoformat(str(raw.get("updated_at", "")))
            return cls(
                user_id=str(raw.get("user_id", "")),
                daily_capacity=int(raw.get("daily_capacity", 240)),
                timezone=str(raw.get("timezone", "UTC")),
                updated_at=ts,
            )
        except Exception:
            return None


@dataclass
class PlannerState:
    user_id: str
    settings: Optional[UserSettings] = None
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)

    def pending_tasks(self) -> List[Task]:
        return [t for t in self.tasks if not t.completed]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "settings": self.settings.to_dict() if self.settings else None,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "PlannerState":
        state = cls(user_id=str(raw.get("user_id", "local")))
        s_raw = raw.get("settings")
        if isinstance(s_raw, dict):
            state.settings = UserSettings.from_dict(s_raw)
        for tr in raw.get("tasks", []):
            if isinstance(tr, dict):
                t = Task.from_dict(tr)
                if t:
                    state.tasks.append(t)
        return state


class SuggestionClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_suggestions(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        url = self._url(f"suggest?user={user_id}")
        if not url:
            return None
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            parsed = json.loads(data)
            if not isinstance(parsed, list):
                return None
            return parsed
        except (error.URLError, ValueError, TimeoutError):
            return None


def load_state(path: Path) -> PlannerState:
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return PlannerState.from_dict(raw)
    except FileNotFoundError:
        return PlannerState(user_id="local")
    except Exception:
        return PlannerState(user_id="local")


def save_state(path: Path, state: PlannerState) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(state.to_dict(), indent=2)
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_daily_plan(state: PlannerState, for_date: Optional[date] = None) -> List[Task]:
    if not state.tasks:
        return []
    capacity = state.settings.daily_capacity if state.settings else 240
    remaining = capacity
    selected: List[Task] = []
    for t in sorted(state.pending_tasks(), key=lambda x: (-x.priority, x.estimated_minutes)):
        if t.estimated_minutes <= remaining:
            selected.append(t)
            remaining -= t.estimated_minutes
        if remaining <= 0:
            break
    return selected


def simulate_day(state: PlannerState) -> int:
    done = 0
    plan = compute_daily_plan(state)
    if not plan:
        return 0
    for task in plan:
        if random.random() < 0.8:
            task.completed = True
            done += 1
    return done


def summarize_state(state: PlannerState) -> Dict[str, Any]:
    total = len(state.tasks)
    pending = len(state.pending_tasks())
    overdue = sum(1 for t in state.tasks if t.is_overdue())
    topics: Dict[str, int] = {}
    for t in state.tasks:
        for tag in t.tags:
            topics[tag] = topics.get(tag, 0) + 1
    return {
        "user_id": state.user_id,
        "total_tasks": total,
        "pending_tasks": pending,
        "overdue_tasks": overdue,
        "tags": topics,
    }


def apply_suggestions(state: PlannerState, suggestions: Optional[List[Dict[str, Any]]]) -> int:
    if not suggestions:
        return 0
    created = 0
    now = datetime.utcnow()
    for raw in suggestions:
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        t = Task(
            task_id=f"sugg-{now.timestamp()}-{created}",
            title=title,
            priority=int(raw.get("priority", 1)),
            estimated_minutes=int(raw.get("estimated_minutes", 30)),
            created_at=now,
            tags=list(raw.get("tags", [])),
        )
        state.add_task(t)
        created += 1
    return created


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / "planner_state.json"
    state = load_state(state_path)

    client = SuggestionClient(base_url=base_url) if base_url else None
    if client is not None:
        sugg = client.fetch_suggestions(state.user_id)
        apply_suggestions(state, sugg)

    simulate_day(state)
    summary = summarize_state(state)
    summary_path = base / "summary.json"

    try:
        save_state(state_path, state)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
