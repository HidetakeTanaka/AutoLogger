from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class Task:
    task_id: str
    title: str
    due_date: datetime
    completed: bool = False
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_overdue(self) -> bool:
        if self.completed:
            return False
        return datetime.utcnow() > self.due_date

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
            "due_date": self.due_date.isoformat(),
            "completed": self.completed,
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Task"]:
        try:
            due_raw = str(raw.get("due_date", ""))
            created_raw = str(raw.get("created_at", ""))
            due = datetime.fromisoformat(due_raw) if due_raw else datetime.utcnow()
            created = datetime.fromisoformat(created_raw) if created_raw else datetime.utcnow()
            return cls(
                task_id=str(raw.get("task_id", "")),
                title=str(raw.get("title", "")),
                due_date=due,
                completed=bool(raw.get("completed", False)),
                tags=list(raw.get("tags", [])),
                created_at=created,
            )
        except Exception:
            return None


@dataclass
class TaskBoard:
    user_id: str
    tasks: Dict[str, Task] = field(default_factory=dict)

    def add_task(self, task: Task) -> None:
        self.tasks[task.task_id] = task

    def complete_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False
        if task.completed:
            return False
        task.completed = True
        return True

    def search(self, query: str = "") -> List[Task]:
        return [t for t in self.tasks.values() if t.matches(query)]

    def overdue_tasks(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.is_overdue()]

    def to_dict(self) -> Dict[str, Any]:
        return {"user_id": self.user_id, "tasks": [t.to_dict() for t in self.tasks.values()]}

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "TaskBoard":
        board = cls(user_id=str(raw.get("user_id", "local")))
        for t_raw in raw.get("tasks", []):
            task = Task.from_dict(t_raw)
            if task is not None:
                board.add_task(task)
        return board


class SuggestionClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, user_id: str) -> str:
        return f"{self.base_url}/users/{user_id}/task_suggestions.json"

    def fetch_suggestions(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        if not self.base_url:
            return None
        url = self._url(user_id)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            parsed = json.loads(data.decode("utf-8"))
            if not isinstance(parsed, list):
                return None
            return parsed
        except (error.URLError, TimeoutError, ValueError):
            return None


def load_board(path: Path) -> TaskBoard:
    if not path.exists():
        return TaskBoard(user_id="local")
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return TaskBoard.from_dict(raw)
    except Exception:
        return TaskBoard(user_id="local")


def save_board(path: Path, board: TaskBoard) -> None:
    payload = board.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        return


def compute_stats(board: TaskBoard) -> Dict[str, Any]:
    tasks = list(board.tasks.values())
    if not tasks:
        return {"count": 0, "completed": 0, "overdue": 0}
    completed = sum(1 for t in tasks if t.completed)
    overdue = sum(1 for t in tasks if t.is_overdue())
    return {"count": len(tasks), "completed": completed, "overdue": overdue}


def simulate_progress(board: TaskBoard, days: int = 3) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    if not board.tasks:
        return history
    day = 0
    task_ids = list(board.tasks.keys())
    while day < days and task_ids:
        random.shuffle(task_ids)
        take = max(1, len(task_ids) // 3)
        for tid in task_ids[:take]:
            board.complete_task(tid)
        history.append({"day": day + 1, "stats": compute_stats(board)})
        day += 1
    return history


def apply_suggestions(board: TaskBoard, recs: Optional[List[Dict[str, Any]]]) -> int:
    if not recs:
        return 0
    added = 0
    for raw in recs:
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        tid = str(raw.get("task_id", f"sugg-{added}"))
        if tid in board.tasks:
            continue
        due = datetime.utcnow() + timedelta(days=int(raw.get("days", 2)))
        tags = list(raw.get("tags", []))
        board.add_task(Task(task_id=tid, title=title, due_date=due, tags=tags))
        added += 1
    return added


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    board_path = base / "tasks.json"
    summary_path = base / "summary.json"

    board = load_board(board_path)
    if not board.tasks:
        now = datetime.utcnow()
        for i in range(3):
            t = Task(
                task_id=f"seed-{i}",
                title=f"Sample task {i + 1}",
                due_date=now + timedelta(days=i + 1),
                tags=["sample"],
            )
            board.add_task(t)

    client = SuggestionClient(base_url=base_url) if base_url else None
    if client:
        recs = client.fetch_suggestions(board.user_id)
        apply_suggestions(board, recs)

    simulate_progress(board, days=3)
    stats = compute_stats(board)
    summary = {"user_id": board.user_id, "stats": stats, "generated_at": datetime.utcnow().isoformat()}

    try:
        save_board(board_path, board)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
