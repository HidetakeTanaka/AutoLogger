from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
import random
import urllib.request
import urllib.error


@dataclass
class Task:
    task_id: str
    title: str
    due: datetime
    completed: bool = False
    tags: List[str] = field(default_factory=list)
    estimate_minutes: int = 0

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        if now is None:
            now = datetime.utcnow()
        if self.completed:
            return False
        return self.due < now

    def matches_query(self, query: str) -> bool:
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
            "completed": self.completed,
            "tags": list(self.tags),
            "estimate_minutes": self.estimate_minutes,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Task"]:
        try:
            due_raw = raw.get("due")
            if isinstance(due_raw, str):
                due = datetime.fromisoformat(due_raw)
            else:
                return None
            return cls(
                task_id=str(raw.get("task_id", "")),
                title=str(raw.get("title", "")),
                due=due,
                completed=bool(raw.get("completed", False)),
                tags=list(raw.get("tags", [])),
                estimate_minutes=int(raw.get("estimate_minutes", 0)),
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

    def active_tasks(self) -> List[Task]:
        return [t for t in self.tasks if not t.completed]

    def overdue_tasks(self, now: Optional[datetime] = None) -> List[Task]:
        return [t for t in self.tasks if t.is_overdue(now)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Project"]:
        try:
            proj = cls(
                project_id=str(raw.get("project_id", "")),
                name=str(raw.get("name", "")),
                tasks=[],
            )
            for item in raw.get("tasks", []):
                task = Task.from_dict(item)
                if task is not None:
                    proj.add_task(task)
            return proj
        except Exception:
            return None


class PlannerClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_remote_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        url = self._url(f"projects/{project_id}/tasks")
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
            data = json.loads(body.decode("utf-8"))
            if isinstance(data, list):
                return [i for i in data if isinstance(i, dict)]
            return []
        except (urllib.error.URLError, json.JSONDecodeError):
            return []


def load_project(path: Path) -> Project:
    if not path.exists():
        now = datetime.utcnow()
        default_task = Task(
            task_id="sample",
            title="Sample task",
            due=now + timedelta(days=1),
            tags=["sample"],
            estimate_minutes=30,
        )
        return Project(project_id="local", name="Local Project", tasks=[default_task])
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        proj = Project.from_dict(data)
        if proj is None:
            return Project(project_id="local", name="Local Project")
        return proj
    except (OSError, json.JSONDecodeError):
        return Project(project_id="local", name="Local Project")


def save_project(path: Path, project: Project) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = project.to_dict()
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def merge_remote_tasks(project: Project, remote_rows: Iterable[Dict[str, Any]]) -> int:
    by_id = {t.task_id: t for t in project.tasks}
    added = 0
    for row in remote_rows:
        task = Task.from_dict(row)
        if task is None:
            continue
        if task.task_id in by_id:
            local = by_id[task.task_id]
            if task.due > local.due:
                local.due = task.due
            local.estimate_minutes = max(local.estimate_minutes, task.estimate_minutes)
        else:
            project.add_task(task)
            by_id[task.task_id] = task
            added += 1
    return added


def choose_next_task(project: Project) -> Optional[Task]:
    candidates = [t for t in project.active_tasks() if not t.is_overdue()]
    if not candidates:
        candidates = project.active_tasks()
    if not candidates:
        return None
    urgent = [t for t in candidates if t.estimate_minutes <= 30]
    if urgent:
        return random.choice(urgent)
    return random.choice(candidates)


def summarize_project(project: Project) -> Dict[str, Any]:
    total = len(project.tasks)
    completed = sum(1 for t in project.tasks if t.completed)
    overdue = len(project.overdue_tasks())
    if total == 0:
        return {"total": 0, "completed": 0, "overdue": 0, "completion_rate": 0.0}
    return {
        "total": total,
        "completed": completed,
        "overdue": overdue,
        "completion_rate": completed / total,
    }


def main(base_dir: str = "data", base_url: str = "") -> int:
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    project_path = base / "project.json"

    project = load_project(project_path)
    if base_url:
        client = PlannerClient(base_url=base_url)
        remote_rows = client.fetch_remote_tasks(project.project_id)
        merge_remote_tasks(project, remote_rows)

    summary = summarize_project(project)
    next_task = choose_next_task(project)

    report = {
        "project_id": project.project_id,
        "name": project.name,
        "summary": summary,
        "next_task": next_task.to_dict() if next_task else None,
        "generated_at": datetime.utcnow().isoformat(),
    }

    report_path = base / "report.json"
    try:
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except OSError:
        return 1

    save_project(project_path, project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
