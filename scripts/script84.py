from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


@dataclass
class Task:
    task_id: str
    title: str
    due: datetime
    priority: int = 3
    tags: List[str] = field(default_factory=list)
    completed: bool = False

    def is_overdue(self, ref: Optional[datetime] = None) -> bool:
        ref_time = ref or datetime.utcnow()
        if self.completed:
            return False
        return self.due < ref_time

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.title.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "due": self.due.isoformat(),
            "priority": self.priority,
            "tags": list(self.tags),
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Task"]:
        try:
            due_raw = str(raw.get("due", ""))
            due = datetime.fromisoformat(due_raw) if due_raw else datetime.utcnow()
            return cls(
                task_id=str(raw.get("task_id", "")),
                title=str(raw.get("title", "")),
                due=due,
                priority=int(raw.get("priority", 3)),
                tags=list(raw.get("tags", [])),
                completed=bool(raw.get("completed", False)),
            )
        except Exception:
            return None


@dataclass
class PlannerState:
    user_id: str
    tasks: Dict[str, Task] = field(default_factory=dict)

    def add_task(self, task: Task) -> None:
        self.tasks[task.task_id] = task

    def mark_done(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False
        if task.completed:
            return False
        task.completed = True
        return True

    def query_tasks(self, query: str = "") -> List[Task]:
        return [t for t in self.tasks.values() if t.matches(query)]

    def upcoming(self, days: int = 1) -> List[Task]:
        limit = datetime.utcnow() + timedelta(days=days)
        return [t for t in self.tasks.values() if not t.completed and t.due <= limit]

    def to_dict(self) -> Dict[str, Any]:
        return {"user_id": self.user_id, "tasks": [t.to_dict() for t in self.tasks.values()]}

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "PlannerState":
        state = cls(user_id=str(raw.get("user_id", "local")))
        for t in raw.get("tasks", []):
            task = Task.from_dict(t)
            if task:
                state.add_task(task)
        return state


class SyncClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def pull_remote(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        if not self.base_url:
            return None
        url = self._url(f"tasks/{user_id}")
        req = Request(url, method="GET")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            parsed = json.loads(data)
            items = parsed.get("tasks") if isinstance(parsed, dict) else parsed
            if not isinstance(items, list):
                return None
            return items
        except (URLError, HTTPError, ValueError):
            return None

    def push_summary(self, user_id: str, summary: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = self._url(f"summary/{user_id}")
        body = json.dumps(summary).encode("utf-8")
        req = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (URLError, HTTPError):
            return False


def load_state(path: Path) -> PlannerState:
    if not path.exists():
        return PlannerState(user_id="local")
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return PlannerState.from_dict(raw)
    except Exception:
        return PlannerState(user_id="local")


def save_state(path: Path, state: PlannerState) -> None:
    payload = json.dumps(state.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_stats(state: PlannerState) -> Dict[str, Any]:
    tasks = list(state.tasks.values())
    if not tasks:
        return {"count": 0, "completed": 0, "overdue": 0}
    completed = sum(1 for t in tasks if t.completed)
    overdue = sum(1 for t in tasks if t.is_overdue())
    return {
        "count": len(tasks),
        "completed": completed,
        "overdue": overdue,
        "completion_rate": completed / len(tasks),
    }


def simulate_day(state: PlannerState, max_new: int = 3) -> int:
    created = 0
    for _ in range(random.randint(0, max_new)):
        created += 1
        tid = f"sim-{int(datetime.utcnow().timestamp())}-{created}"
        due = datetime.utcnow() + timedelta(hours=random.randint(1, 72))
        task = Task(
            task_id=tid,
            title=f"Simulated task {created}",
            due=due,
            priority=random.randint(1, 5),
            tags=["simulated"],
        )
        state.add_task(task)
    return created


def filter_urgent(state: PlannerState, hours: int = 6) -> List[Task]:
    cutoff = datetime.utcnow() + timedelta(hours=hours)
    urgent = [t for t in state.tasks.values() if not t.completed and t.due <= cutoff]
    urgent.sort(key=lambda t: (t.due, -t.priority))
    return urgent


def summarize_state(state: PlannerState, remote_rate: Optional[float] = None) -> Dict[str, Any]:
    stats = compute_stats(state)
    urgent = filter_urgent(state, hours=12)
    relation = "unknown"
    if remote_rate is not None:
        if stats["completion_rate"] > remote_rate:
            relation = "above_remote"
        elif stats["completion_rate"] < remote_rate:
            relation = "below_remote"
        else:
            relation = "equal_remote"
    return {
        "user_id": state.user_id,
        "stats": stats,
        "urgent_count": len(urgent),
        "remote_relation": relation,
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / "tasks.json"
    summary_path = base / "summary.json"

    try:
        state = load_state(state_path)
        simulate_day(state)
        client = SyncClient(base_url=base_url)
        remote_data = client.pull_remote(state.user_id)
        if remote_data:
            for raw in remote_data:
                task = Task.from_dict(raw)
                if task and task.task_id not in state.tasks:
                    state.add_task(task)
        remote_rate = None
        if remote_data:
            remote_completed = sum(1 for r in remote_data if r.get("completed"))
            remote_rate = remote_completed / max(len(remote_data), 1)
        summary = summarize_state(state, remote_rate)
        save_state(state_path, state)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        client.push_summary(state.user_id, summary)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
