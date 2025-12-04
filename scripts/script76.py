from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class Habit:
    habit_id: str
    name: str
    target_per_day: int
    unit: str = "reps"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.name.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "habit_id": self.habit_id,
            "name": self.name,
            "target_per_day": self.target_per_day,
            "unit": self.unit,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Habit"]:
        try:
            created_raw = raw.get("created_at")
            created = (
                datetime.fromisoformat(created_raw)
                if isinstance(created_raw, str)
                else datetime.utcnow()
            )
            return cls(
                habit_id=str(raw.get("habit_id", "")),
                name=str(raw.get("name", "")),
                target_per_day=int(raw.get("target_per_day", 1)),
                unit=str(raw.get("unit", "reps")),
                tags=list(raw.get("tags", [])),
                created_at=created,
            )
        except Exception:
            return None


@dataclass
class HabitEntry:
    habit_id: str
    date: datetime
    amount: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "habit_id": self.habit_id,
            "date": self.date.date().isoformat(),
            "amount": self.amount,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["HabitEntry"]:
        try:
            d_raw = str(raw.get("date", datetime.utcnow().date().isoformat()))
            d_val = datetime.fromisoformat(d_raw)
            return cls(
                habit_id=str(raw.get("habit_id", "")),
                date=d_val,
                amount=int(raw.get("amount", 0)),
            )
        except Exception:
            return None


@dataclass
class HabitBook:
    user_id: str
    habits: Dict[str, Habit] = field(default_factory=dict)
    entries: List[HabitEntry] = field(default_factory=list)

    def add_habit(self, habit: Habit) -> None:
        self.habits[habit.habit_id] = habit

    def add_entry(self, entry: HabitEntry) -> None:
        if entry.habit_id in self.habits:
            self.entries.append(entry)

    def filter_habits(self, query: str = "") -> List[Habit]:
        return [h for h in self.habits.values() if h.matches(query)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "habits": [h.to_dict() for h in self.habits.values()],
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "HabitBook":
        book = cls(user_id=str(raw.get("user_id", "local")))
        for h_raw in raw.get("habits", []):
            habit = Habit.from_dict(h_raw)
            if habit:
                book.add_habit(habit)
        for e_raw in raw.get("entries", []):
            entry = HabitEntry.from_dict(e_raw)
            if entry:
                book.add_entry(entry)
        return book


class AdviceClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/") or "https://api.adviceslip.com"
        self.timeout = timeout

    def _url(self) -> str:
        return f"{self.base_url}/advice"

    def fetch_advice(self) -> Optional[str]:
        url = self._url()
        try:
            req = request.Request(url)
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
        except error.URLError:
            return None
        try:
            payload = json.loads(data.decode("utf-8"))
            slip = payload.get("slip") or {}
            text = slip.get("advice")
            return str(text) if text else None
        except Exception:
            return None


def load_book(path: Path) -> HabitBook:
    if not path.exists():
        return HabitBook(user_id="local")
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return HabitBook.from_dict(raw)
    except Exception:
        return HabitBook(user_id="local")


def save_book(path: Path, book: HabitBook) -> None:
    payload = book.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def compute_daily_totals(book: HabitBook, day: datetime) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    target_date = day.date()
    for e in book.entries:
        if e.date.date() != target_date:
            continue
        totals[e.habit_id] = totals.get(e.habit_id, 0) + e.amount
    return totals


def compute_streaks(book: HabitBook, habit_id: str, days: int = 7) -> int:
    if habit_id not in book.habits:
        return 0
    streak = 0
    today = datetime.utcnow().date()
    day_idx = 0
    while day_idx < days:
        d = today - timedelta(days=day_idx)
        totals = compute_daily_totals(book, datetime.combine(d, datetime.min.time()))
        if totals.get(habit_id, 0) >= book.habits[habit_id].target_per_day:
            streak += 1
            day_idx += 1
        else:
            break
    return streak


def summarize_book(book: HabitBook) -> Dict[str, Any]:
    if not book.habits:
        return {"habit_count": 0, "entries": 0, "top_streak": 0}
    streaks = [compute_streaks(book, hid, 14) for hid in book.habits]
    top_streak = max(streaks) if streaks else 0
    return {
        "habit_count": len(book.habits),
        "entries": len(book.entries),
        "top_streak": top_streak,
    }


def simulate_day(book: HabitBook, intensity: float = 0.7) -> None:
    today = datetime.utcnow()
    for habit in book.habits.values():
        baseline = habit.target_per_day
        if random.random() > intensity:
            amount = max(0, int(baseline * random.uniform(0.2, 0.8)))
        else:
            amount = int(baseline * random.uniform(0.9, 1.3))
        if amount <= 0:
            continue
        book.add_entry(HabitEntry(habit_id=habit.habit_id, date=today, amount=amount))


def ensure_sample_habits(book: HabitBook) -> None:
    if book.habits:
        return
    samples = [
        Habit(habit_id="water", name="Drink water", target_per_day=8, unit="glasses"),
        Habit(habit_id="steps", name="Walk", target_per_day=6000, unit="steps"),
        Habit(habit_id="read", name="Read", target_per_day=20, unit="minutes"),
    ]
    for h in samples:
        book.add_habit(h)


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    book_path = base / "habits.json"
    book = load_book(book_path)
    ensure_sample_habits(book)
    simulate_day(book, intensity=0.8)
    stats = summarize_book(book)
    client = AdviceClient(base_url or "https://api.adviceslip.com")
    advice = client.fetch_advice()
    summary = {"stats": stats, "advice": advice}
    summary_path = base / "summary.json"
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        save_book(book_path, book)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
