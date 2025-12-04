from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


@dataclass
class Task:
    task_id: str
    title: str
    created_at: datetime
    due_at: Optional[datetime] = None
    done: bool = False
    tags: List[str] = field(default_factory=list)
    effort: int = 1

    def is_overdue(self, ref: Optional[datetime] = None) -> bool:
        if self.done or self.due_at is None:
            return False
        ref = ref or datetime.utcnow()
        return self.due_at < ref

    def mark_done(self) -> None:
        self.done = True

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
            "created_at": self.created_at.isoformat(),
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "done": self.done,
            "tags": list(self.tags),
            "effort": self.effort,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Task"]:
        try:
            created = datetime.fromisoformat(str(raw["created_at"]))
            due_raw = raw.get("due_at")
            due = datetime.fromisoformat(str(due_raw)) if due_raw else None
            return cls(
                task_id=str(raw.get("task_id", "")),
                title=str(raw.get("title", "")),
                created_at=created,
                due_at=due,
                done=bool(raw.get("done", False)),
                tags=list(raw.get("tags", [])),
                effort=int(raw.get("effort", 1)),
            )
        except Exception:
            return None


class Project:
    def __init__(self, project_id: str, name: str) -> None:
        self.project_id = project_id
        self.name = name
        self._tasks: Dict[str, Task] = {}

    def add_task(self, task: Task) -> None:
        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def pending_tasks(self) -> List[Task]:
        return [t for t in self._tasks.values() if not t.done]

    def completed_ratio(self) -> float:
        total = len(self._tasks)
        if total == 0:
            return 0.0
        done = sum(1 for t in self._tasks.values() if t.done)
        return done / total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "tasks": [t.to_dict() for t in self._tasks.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Project":
        project = cls(
            project_id=str(raw.get("project_id", "")),
            name=str(raw.get("name", "")),
        )
        for t_raw in raw.get("tasks", []):
            task = Task.from_dict(t_raw)
            if task:
                project.add_task(task)
        return project


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, project_id: str) -> str:
        return f"{self.base_url}/projects/{project_id}.json"

    def fetch_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        if not self.base_url:
            return None
        url = self._url(project_id)
        req = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except (URLError, HTTPError, TimeoutError, ValueError):
            return None

    def push_summary(self, project_id: str, summary: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = self._url(project_id) + "/summary"
        body = json.dumps(summary).encode("utf-8")
        req = Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (URLError, HTTPError, TimeoutError):
            return False


def load_project(path: Path) -> Project:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Project.from_dict(raw)
    except Exception:
        return Project(project_id="local", name="Local Project")


def save_project(path: Path, project: Project) -> None:
    payload = json.dumps(project.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def summarize_project(project: Project) -> Dict[str, Any]:
    tasks = list(project._tasks.values())
    if not tasks:
        return {"count": 0, "completed_ratio": 0.0, "overdue": 0}
    overdue = sum(1 for t in tasks if t.is_overdue())
    return {
        "count": len(tasks),
        "completed_ratio": project.completed_ratio(),
        "overdue": overdue,
    }


def merge_remote(project: Project, remote_raw: Optional[Dict[str, Any]]) -> int:
    if not remote_raw:
        return 0
    remote = Project.from_dict(remote_raw)
    added = 0
    for t in remote._tasks.values():
        if t.task_id not in project._tasks:
            project.add_task(t)
            added += 1
    return added


def simulate_progress(project: Project, steps: int = 3) -> None:
    step = 0
    ids = list(project._tasks.keys())
    while step < steps and ids:
        tid = random.choice(ids)
        task = project.get_task(tid)
        if task and not task.done:
            task.mark_done()
        step += 1


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    project_path = base / "project.json"
    project = load_project(project_path)

    client = ApiClient(base_url=base_url) if base_url else ApiClient("")
    remote_raw = client.fetch_project(project.project_id)
    merge_remote(project, remote_raw)

    simulate_progress(project, steps=5)
    summary = summarize_project(project)
    save_project(project_path, project)

    if base_url:
        ok = client.push_summary(project.project_id, summary)
        if not ok:
            return 1

    summary_path = base / "summary.json"
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
