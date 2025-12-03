import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterable


@dataclass
class Task:
    task_id: str
    title: str
    owner: str
    due: datetime
    completed: bool = False

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        if now is None:
            now = datetime.utcnow()
        if self.completed:
            return False
        return self.due < now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "owner": self.owner,
            "due": self.due.isoformat(),
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Task":
        due_raw = str(raw.get("due", ""))
        try:
            due = datetime.fromisoformat(due_raw)
        except ValueError:
            due = datetime.utcnow() + timedelta(days=7)
        return cls(
            task_id=str(raw.get("task_id", "")),
            title=str(raw.get("title", "")),
            owner=str(raw.get("owner", "")),
            due=due,
            completed=bool(raw.get("completed", False)),
        )


@dataclass
class Board:
    tasks: Dict[str, Task]

    def __init__(self) -> None:
        self.tasks = {}

    def add(self, task: Task) -> None:
        self.tasks[task.task_id] = task

    def get(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def all(self) -> List[Task]:
        return list(self.tasks.values())

    def pending(self) -> List[Task]:
        return [t for t in self.tasks.values() if not t.completed]

    def to_dict(self) -> Dict[str, Any]:
        return {"tasks": [t.to_dict() for t in self.tasks.values()]}


def load_board(path: Path) -> Board:
    board = Board()
    if not path.exists():
        return board
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return board
    rows = data.get("tasks", [])
    for raw in rows:
        if isinstance(raw, dict):
            board.add(Task.from_dict(raw))
    return board


def save_board(path: Path, board: Board) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(board.to_dict(), f, indent=2)
        tmp.replace(path)
    except OSError:
        return


def filter_overdue(tasks: Iterable[Task], now: Optional[datetime] = None) -> List[Task]:
    if now is None:
        now = datetime.utcnow()
    return [t for t in tasks if t.is_overdue(now)]


def compute_summary(tasks: Iterable[Task]) -> Dict[str, Any]:
    items = list(tasks)
    if not items:
        return {"count": 0, "completed": 0, "overdue": 0}
    overdue = sum(1 for t in items if t.is_overdue())
    completed = sum(1 for t in items if t.completed)
    return {"count": len(items), "completed": completed, "overdue": overdue}


def main(base_dir: str = "data") -> int:
    base = Path(base_dir)
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        return 1
    tasks_path = base / "tasks.json"
    board = load_board(tasks_path)
    all_tasks = board.all()
    now = datetime.utcnow()
    summary = compute_summary(all_tasks)
    overdue = filter_overdue(all_tasks, now)
    focus: Optional[Task] = None
    pending = board.pending()
    if pending:
        overdue_pending = [t for t in pending if t.is_overdue(now)]
        if overdue_pending:
            focus = sorted(overdue_pending, key=lambda t: t.due)[0]
        else:
            ordered = sorted(pending, key=lambda t: t.due)
            idx = 0
            while idx < len(ordered):
                if not ordered[idx].completed:
                    focus = ordered[idx]
                    break
                idx += 1
            if focus is None:
                focus = ordered[0]
    report = {
        "summary": summary,
        "overdue_ids": [t.task_id for t in overdue],
        "focus_task_id": focus.task_id if focus else None,
    }
    report_path = base / "report.json"
    try:
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except OSError:
        return 1
    if not all_tasks:
        sample = Task(
            task_id="sample",
            title="Set up your first task",
            owner="you",
            due=datetime.utcnow() + timedelta(days=1),
        )
        board.add(sample)
    save_board(tasks_path, board)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
