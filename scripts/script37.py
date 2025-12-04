from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterable
import urllib.request
import urllib.error


@dataclass
class Task:
    task_id: str
    title: str
    status: str
    priority: int
    due_date: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        if self.due_date is None:
            return False
        if now is None:
            now = datetime.utcnow()
        return now > self.due_date and self.status != "done"

    def is_open(self) -> bool:
        return self.status in {"todo", "in_progress"}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Task:
        raw_due = raw.get("due_date")
        due: Optional[datetime]
        if raw_due:
            try:
                due = datetime.fromisoformat(str(raw_due))
            except ValueError:
                due = None
        else:
            due = None
        return cls(
            task_id=str(raw.get("task_id", "")),
            title=str(raw.get("title", "")),
            status=str(raw.get("status", "todo")),
            priority=int(raw.get("priority", 0)),
            due_date=due,
            tags=list(raw.get("tags", [])),
        )


@dataclass
class Project:
    project_id: str
    name: str
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)

    def remove_task(self, task_id: str) -> bool:
        for i, t in enumerate(self.tasks):
            if t.task_id == task_id:
                del self.tasks[i]
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Project:
        tasks_raw = raw.get("tasks", [])
        tasks = [Task.from_dict(t) for t in tasks_raw]
        return cls(
            project_id=str(raw.get("project_id", "")),
            name=str(raw.get("name", "")),
            tasks=tasks,
        )


class ProjectStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._projects: Dict[str, Project] = {}

    def load(self) -> None:
        if not self.path.exists():
            self._projects = {}
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._projects = {}
            return
        projects: Dict[str, Project] = {}
        for raw in data.get("projects", []):
            proj = Project.from_dict(raw)
            if proj.project_id:
                projects[proj.project_id] = proj
        self._projects = projects

    def save(self) -> None:
        payload = {"projects": [p.to_dict() for p in self._projects.values()]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp.replace(self.path)

    def get(self, project_id: str) -> Optional[Project]:
        return self._projects.get(project_id)

    def upsert(self, project: Project) -> None:
        self._projects[project.project_id] = project

    def all(self) -> List[Project]:
        return list(self._projects.values())


class RemoteClient:
    def __init__(self, base_url: str, timeout: int = 4) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def fetch_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        url = self._url(f"/projects/{project_id}/tasks")
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except (urllib.error.URLError, urllib.error.HTTPError):
            return []
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return []
        return list(data.get("tasks", []))

    def push_project(self, project: Project) -> bool:
        url = self._url(f"/projects/{project.project_id}/sync")
        raw = json.dumps(project.to_dict()).encode("utf-8")
        req = urllib.request.Request(url, data=raw, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.URLError, urllib.error.HTTPError):
            return False


def filter_overdue(tasks: Iterable[Task]) -> List[Task]:
    now = datetime.utcnow()
    return [t for t in tasks if t.is_overdue(now)]


def filter_by_tag(tasks: Iterable[Task], tag: str) -> List[Task]:
    result: List[Task] = []
    for t in tasks:
        if tag in t.tags:
            result.append(t)
    return result


def sort_by_priority(tasks: Iterable[Task]) -> List[Task]:
    return sorted(tasks, key=lambda t: (-t.priority, t.title))


def summarize_tasks(tasks: Iterable[Task]) -> Dict[str, Any]:
    total = 0
    open_count = 0
    overdue_count = 0
    now = datetime.utcnow()
    for t in tasks:
        total += 1
        if t.is_open():
            open_count += 1
        if t.is_overdue(now):
            overdue_count += 1
    return {"total": total, "open": open_count, "overdue": overdue_count}


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def ensure_demo_project(store: ProjectStore) -> None:
    if store.all():
        return
    base = datetime.utcnow()
    proj = Project(project_id="demo", name="Demo")
    for i in range(4):
        due = base + timedelta(days=i - 1)
        t = Task(
            task_id=f"T{i+1}",
            title=f"Demo Task {i+1}",
            status="todo" if i % 2 == 0 else "in_progress",
            priority=4 - i,
            due_date=due,
            tags=["demo"],
        )
        proj.add_task(t)
    store.upsert(proj)
    store.save()


def sync_if_enabled(store: ProjectStore, cfg: Dict[str, Any]) -> None:
    if not cfg.get("sync_enabled", False):
        return
    base_url = str(cfg.get("remote_base_url", "https://example.invalid"))
    client = RemoteClient(base_url=base_url, timeout=int(cfg.get("timeout", 4)))
    project_id = str(cfg.get("project_id", "demo"))
    project = store.get(project_id)
    if project is None:
        return
    remote_tasks = client.fetch_tasks(project_id)
    if not remote_tasks:
        return
    project.tasks = [Task.from_dict(t) for t in remote_tasks]
    store.upsert(project)
    store.save()


def export_summary(path: Path, summary: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def main(base_dir: str = "data") -> int:
    base = Path(base_dir)
    projects_path = base / "projects.json"
    summary_path = base / "tasks_summary.json"
    config_path = base / "task_config.json"

    store = ProjectStore(projects_path)
    store.load()
    ensure_demo_project(store)

    cfg = load_config(config_path)
    sync_if_enabled(store, cfg)

    all_projects = store.all()
    all_tasks: List[Task] = []
    for p in all_projects:
        all_tasks.extend(p.tasks)

    summary = summarize_tasks(all_tasks)
    overdue = filter_overdue(all_tasks)
    summary["overdue_ids"] = [t.task_id for t in overdue]

    export_summary(summary_path, summary)

    if summary["total"] == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
