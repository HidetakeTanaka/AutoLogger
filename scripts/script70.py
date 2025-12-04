from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request


@dataclass
class Task:
    task_id: str
    title: str
    duration_min: int
    completed: bool = False
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_long(self, threshold: int = 60) -> bool:
        if self.duration_min <= 0:
            return False
        return self.duration_min >= threshold

    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        if not q:
            return True
        if q in self.title.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def mark_done(self) -> None:
        self.completed = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "duration_min": self.duration_min,
            "completed": self.completed,
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Task"]:
        created_raw = raw.get("created_at")
        try:
            created = (
                datetime.fromisoformat(created_raw)
                if isinstance(created_raw, str)
                else datetime.utcnow()
            )
            return cls(
                task_id=str(raw.get("task_id", "")),
                title=str(raw.get("title", "")),
                duration_min=int(raw.get("duration_min", 0)),
                completed=bool(raw.get("completed", False)),
                tags=list(raw.get("tags", [])),
                created_at=created,
            )
        except Exception:
            return None


@dataclass
class Project:
    project_id: str
    name: str
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)

    def get_task(self, task_id: str) -> Optional[Task]:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None

    def completed_tasks(self) -> List[Task]:
        return [t for t in self.tasks if t.completed]

    def active_tasks(self) -> List[Task]:
        return [t for t in self.tasks if not t.completed]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Project":
        project = cls(
            project_id=str(raw.get("project_id", "")),
            name=str(raw.get("name", "")),
            tasks=[],
        )
        for r in raw.get("tasks", []):
            t = Task.from_dict(r)
            if t is not None:
                project.add_task(t)
        return project


class AnalyticsClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, project_id: str) -> str:
        return f"{self.base_url}/projects/{project_id}/suggestions.json"

    def fetch_suggestions(self, project_id: str) -> Optional[Dict[str, Any]]:
        if not self.base_url:
            return None
        url = self._url(project_id)
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except (error.URLError, ValueError, TimeoutError):
            return None

    def push_summary(self, project_id: str, summary: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = f"{self.base_url}/projects/{project_id}/summary"
        body = json.dumps(summary).encode("utf-8")
        req = request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except error.URLError:
            return False


def load_project(path: Path) -> Project:
    try:
        data = path.read_text(encoding="utf-8")
        raw = json.loads(data)
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
            except OSError:
                pass


def compute_stats(project: Project) -> Dict[str, Any]:
    tasks = project.tasks
    if not tasks:
        return {"count": 0, "completed": 0, "avg_duration": 0.0, "long_tasks": 0}
    durations = [t.duration_min for t in tasks if t.duration_min > 0]
    completed = sum(1 for t in tasks if t.completed)
    long_tasks = sum(1 for t in tasks if t.is_long())
    if not durations:
        return {
            "count": len(tasks),
            "completed": completed,
            "avg_duration": 0.0,
            "long_tasks": long_tasks,
        }
    avg = sum(durations) / len(durations)
    return {
        "count": len(tasks),
        "completed": completed,
        "avg_duration": avg,
        "long_tasks": long_tasks,
    }


def simulate_work(project: Project, steps: int = 3) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    if not project.tasks:
        return history
    index = 0
    step = 0
    while step < steps and project.tasks:
        task = project.tasks[index % len(project.tasks)]
        if not task.completed:
            delta = random.randint(5, 25)
            task.duration_min += delta
            if task.duration_min >= 60 and random.random() < 0.5:
                task.mark_done()
        history.append(
            {"task_id": task.task_id, "duration_min": task.duration_min, "done": task.completed}
        )
        index += 1
        step += 1
    return history


def merge_remote_suggestions(project: Project, remote: Optional[Dict[str, Any]]) -> int:
    if not remote:
        return 0
    added = 0
    existing_ids = {t.task_id for t in project.tasks}
    for raw in remote.get("suggested_tasks", []):
        tid = str(raw.get("task_id", ""))
        if not tid or tid in existing_ids:
            continue
        t = Task.from_dict(raw)
        if t is None:
            continue
        project.add_task(t)
        existing_ids.add(t.task_id)
        added += 1
    return added


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    project_path = base / "project.json"
    summary_path = base / "summary.json"
    project = load_project(project_path)
    client = AnalyticsClient(base_url=base_url, timeout=5)
    try:
        remote = client.fetch_suggestions(project.project_id)
        merge_remote_suggestions(project, remote)
        simulate_work(project, steps=5)
        stats = compute_stats(project)
        summary = {
            "project_id": project.project_id,
            "name": project.name,
            "stats": stats,
            "generated_at": datetime.utcnow().isoformat(),
        }
        save_project(project_path, project)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if base_url:
            client.push_summary(project.project_id, summary)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
