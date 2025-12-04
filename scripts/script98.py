from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, error


@dataclass
class Task:
    task_id: str
    name: str
    status: str
    priority: int
    updated_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_open(self) -> bool:
        return self.status.lower() in {"todo", "in_progress", "blocked"}

    def is_stale(self, days: int = 7) -> bool:
        cutoff = datetime.utcnow() - timedelta(days=days)
        if self.updated_at < cutoff and self.is_open():
            return True
        return False

    def update_status(self, status: str) -> None:
        self.status = status
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status,
            "priority": self.priority,
            "updated_at": self.updated_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Task"]:
        try:
            ts_raw = raw.get("updated_at")
            ts = (
                datetime.fromisoformat(ts_raw)
                if isinstance(ts_raw, str)
                else datetime.utcnow()
            )
            return cls(
                task_id=str(raw.get("task_id", "")),
                name=str(raw.get("name", "")),
                status=str(raw.get("status", "todo")),
                priority=int(raw.get("priority", 0)),
                updated_at=ts,
                tags=list(raw.get("tags", [])),
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

    def open_tasks(self) -> List[Task]:
        return [t for t in self.tasks if t.is_open()]

    def find_task(self, task_id: str) -> Optional[Task]:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None

    def completion_ratio(self) -> float:
        if not self.tasks:
            return 0.0
        closed = sum(1 for t in self.tasks if not t.is_open())
        return closed / len(self.tasks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Project"]:
        try:
            proj = cls(project_id=str(raw.get("project_id", "")), name=str(raw.get("name", "")))
            for r in raw.get("tasks", []):
                t = Task.from_dict(r)
                if t:
                    proj.tasks.append(t)
            return proj
        except Exception:
            return None


@dataclass
class ProjectStore:
    path: Path
    projects: List[Project] = field(default_factory=list)

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            text = self.path.read_text(encoding="utf-8")
            raw = json.loads(text or "[]")
            self.projects = []
            for p in raw:
                proj = Project.from_dict(p)
                if proj:
                    self.projects.append(proj)
        except (OSError, ValueError):
            self.projects = []

    def save(self) -> None:
        payload = [p.to_dict() for p in self.projects]
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            return

    def get_or_create(self, project_id: str, name: str) -> Project:
        for p in self.projects:
            if p.project_id == project_id:
                return p
        proj = Project(project_id=project_id, name=name)
        self.projects.append(proj)
        return proj

    def all_tasks(self) -> Iterable[Task]:
        for p in self.projects:
            for t in p.tasks:
                yield t


class SyncClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_remote_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        url = self._url(f"/projects/{project_id}/tasks")
        if not url:
            return []
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8")
            data = json.loads(text or "[]")
            if not isinstance(data, list):
                return []
            return [d for d in data if isinstance(d, dict)]
        except (error.URLError, ValueError, OSError):
            return []

    def push_update(self, task: Task) -> bool:
        url = self._url(f"/tasks/{task.task_id}")
        if not url:
            return False
        payload = json.dumps(task.to_dict()).encode("utf-8")
        req = request.Request(url, data=payload, method="PUT")
        req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.getcode() < 300
        except (error.URLError, OSError):
            return False


def load_store(path_str: str) -> ProjectStore:
    store = ProjectStore(path=Path(path_str))
    store.load()
    return store


def save_store(store: ProjectStore) -> None:
    store.save()


def filter_tasks(tasks: Iterable[Task], status: Optional[str] = None, min_priority: int = 0) -> List[Task]:
    status = status.lower().strip() if status else ""
    selected: List[Task] = []
    for t in tasks:
        if status and t.status.lower() != status:
            continue
        if t.priority < min_priority:
            continue
        selected.append(t)
    return selected


def summarize_projects(projects: Iterable[Project]) -> Dict[str, Any]:
    items = list(projects)
    if not items:
        return {"count": 0, "avg_completion": 0.0}
    avg = sum(p.completion_ratio() for p in items) / len(items)
    return {"count": len(items), "avg_completion": avg}


def sync_project(store: ProjectStore, client: SyncClient, project_id: str) -> int:
    remote = client.fetch_remote_tasks(project_id)
    if not remote:
        return 0
    proj = store.get_or_create(project_id, name=f"Project {project_id}")
    added = 0
    for r in remote:
        task = Task.from_dict(r)
        if not task:
            continue
        if not proj.find_task(task.task_id):
            proj.add_task(task)
            added += 1
    store.save()
    return added


def read_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        cfg = json.loads(text or "{}")
        if not isinstance(cfg, dict):
            return {}
        return cfg
    except (OSError, ValueError):
        return {}


def main(config_path: str = "task_config.json") -> int:
    cfg_file = Path(config_path)
    cfg = read_config(cfg_file)
    store_path = cfg.get("store_path", "projects.json")
    base_url = cfg.get("base_url", "")
    project_id = cfg.get("project_id", "default")

    store = load_store(store_path)
    client = SyncClient(base_url=str(base_url))

    added = sync_project(store, client, project_id)
    open_tasks = filter_tasks(store.all_tasks(), status="todo", min_priority=cfg.get("min_priority", 0))
    summary = summarize_projects(store.projects)

    report_path = Path(cfg.get("report_path", "project_summary.json"))
    try:
        report_path.write_text(json.dumps({"summary": summary, "open": len(open_tasks)}, indent=2), encoding="utf-8")
    except OSError:
        return 1

    if added == 0 and not open_tasks:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
