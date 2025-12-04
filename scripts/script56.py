from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, error


@dataclass
class Task:
    task_id: str
    title: str
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    due_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    effort: int = 1

    def is_overdue(self, ref: Optional[datetime] = None) -> bool:
        if self.due_at is None:
            return False
        ref_time = ref or datetime.utcnow()
        return self.status != "done" and self.due_at < ref_time

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.title.lower():
            return True
        if q in self.status.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "due_at": self.due_at.isoformat() if self.due_at else "",
            "tags": list(self.tags),
            "effort": self.effort,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional[Task]:
        try:
            created_raw = raw.get("created_at") or ""
            due_raw = raw.get("due_at") or ""
            created_at = datetime.fromisoformat(created_raw) if created_raw else datetime.utcnow()
            due_at = datetime.fromisoformat(due_raw) if due_raw else None
            return cls(
                task_id=str(raw.get("task_id", "")),
                title=str(raw.get("title", "")),
                status=str(raw.get("status", "pending")),
                created_at=created_at,
                due_at=due_at,
                tags=list(raw.get("tags", [])),
                effort=int(raw.get("effort", 1)),
            )
        except Exception:
            return None


class TaskList:
    def __init__(self, list_id: str, name: str) -> None:
        self.list_id = list_id
        self.name = name
        self._tasks: Dict[str, Task] = {}

    def add(self, task: Task) -> None:
        self._tasks[task.task_id] = task

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def all(self) -> List[Task]:
        return list(self._tasks.values())

    def search(self, query: str = "") -> List[Task]:
        items = [t for t in self._tasks.values() if t.matches(query)]
        return sorted(items, key=lambda t: t.created_at)

    def open_tasks(self) -> List[Task]:
        return [t for t in self._tasks.values() if t.status != "done"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "list_id": self.list_id,
            "name": self.name,
            "tasks": [t.to_dict() for t in self._tasks.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> TaskList:
        tl = cls(list_id=str(raw.get("list_id", "local")), name=str(raw.get("name", "Local Tasks")))
        for item in raw.get("tasks", []):
            t = Task.from_dict(item)
            if t:
                tl.add(t)
        return tl


class SyncClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, list_id: str) -> str:
        return f"{self.base_url}/tasks/{list_id}.json"

    def fetch_remote(self, list_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(list_id)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
            return json.loads(body.decode("utf-8"))
        except (error.URLError, ValueError, OSError):
            return None

    def push_update(self, list_id: str, payload: Dict[str, Any]) -> bool:
        url = self._url(list_id)
        data = json.dumps(payload).encode("utf-8")
        try:
            req = request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (error.URLError, OSError):
            return False


def load_task_list(path: Path) -> TaskList:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return TaskList.from_dict(raw)
    except FileNotFoundError:
        return TaskList(list_id="local", name="Local Tasks")
    except Exception:
        return TaskList(list_id="local", name="Local Tasks")


def save_task_list(path: Path, tl: TaskList) -> None:
    data = json.dumps(tl.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(data, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def summarize_task_list(tl: TaskList) -> Dict[str, Any]:
    tasks = tl.all()
    if not tasks:
        return {"count": 0, "open": 0, "overdue": 0}
    open_tasks = [t for t in tasks if t.status != "done"]
    overdue = sum(1 for t in tasks if t.is_overdue())
    return {"count": len(tasks), "open": len(open_tasks), "overdue": overdue}


def filter_tasks(
    tl: TaskList,
    tag: str = "",
    max_effort: Optional[int] = None,
    only_open: bool = False,
) -> List[Task]:
    results: List[Task] = []
    for t in tl.all():
        if only_open and t.status == "done":
            continue
        if tag and tag.lower() not in [x.lower() for x in t.tags]:
            continue
        if max_effort is not None and t.effort > max_effort:
            continue
        results.append(t)
    return results


def pick_next_task(tl: TaskList, prefer_short: bool = True) -> Optional[Task]:
    open_tasks = tl.open_tasks()
    if not open_tasks:
        return None
    if not prefer_short:
        return random.choice(open_tasks)
    candidates = [t for t in open_tasks if t.effort <= 2]
    if candidates:
        return random.choice(candidates)
    return random.choice(open_tasks)


def simulate_progress(tl: TaskList, days: int = 3) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    current = datetime.utcnow()
    for _ in range(days):
        remaining = [t for t in tl.open_tasks() if not t.is_overdue(current)]
        if not remaining:
            history.append({"date": current.date().isoformat(), "open": 0})
            current += timedelta(days=1)
            continue
        done_today = 0
        idx = 0
        while idx < len(remaining) and done_today < 2:
            remaining[idx].status = "done"
            done_today += 1
            idx += 1
        history.append({"date": current.date().isoformat(), "open": len(tl.open_tasks())})
        current += timedelta(days=1)
    return history


def merge_remote_tasks(local: TaskList, remote_data: Optional[Dict[str, Any]]) -> int:
    if not remote_data:
        return 0
    remote = TaskList.from_dict(remote_data)
    added = 0
    for t in remote.all():
        if local.get(t.task_id) is None:
            local.add(t)
            added += 1
    return added


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    tasks_path = base / "tasks.json"
    tl = load_task_list(tasks_path)

    if base_url:
        client = SyncClient(base_url=base_url)
        remote_data = client.fetch_remote(tl.list_id)
        merge_remote_tasks(tl, remote_data)

    summary = summarize_task_list(tl)
    report_path = base / "tasks_report.json"
    try:
        report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except OSError:
        return 1

    save_task_list(tasks_path, tl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
