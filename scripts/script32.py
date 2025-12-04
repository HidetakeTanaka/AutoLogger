from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterable, Tuple
import random


@dataclass
class Event:
    event_id: str
    user_id: str
    event_type: str
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_recent(self, now: Optional[datetime] = None, minutes: int = 60) -> bool:
        if now is None:
            now = datetime.utcnow()
        delta = now - self.created_at
        return delta <= timedelta(minutes=minutes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class User:
    user_id: str
    name: str
    country: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        return bool(self.properties.get("active", True))

    def update_country(self, country: str) -> None:
        self.country = country

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "country": self.country,
            "properties": self.properties,
        }


@dataclass
class Segment:
    name: str
    countries: List[str]
    min_events: int = 1

    def matches(self, user: User, events: List[Event]) -> bool:
        if self.countries and user.country not in self.countries:
            return False
        count = sum(1 for e in events if e.user_id == user.user_id)
        return count >= self.min_events


class UserStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._users: Dict[str, User] = {}

    def load(self) -> None:
        if not self.path.exists():
            self._users = {}
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._users = {}
            return
        users: Dict[str, User] = {}
        for raw in data.get("users", []):
            uid = str(raw.get("user_id", ""))
            if not uid:
                continue
            name = str(raw.get("name", ""))
            country = str(raw.get("country", "unknown"))
            props = raw.get("properties") or {}
            users[uid] = User(user_id=uid, name=name, country=country, properties=props)
        self._users = users

    def save(self) -> None:
        payload = {"users": [u.to_dict() for u in self._users.values()]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp.replace(self.path)

    def get(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def upsert(self, user: User) -> None:
        self._users[user.user_id] = user

    def all(self) -> List[User]:
        return list(self._users.values())


class EventStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> List[Event]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
        events: List[Event] = []
        for raw in data.get("events", []):
            try:
                created = datetime.fromisoformat(str(raw["created_at"]))
            except (KeyError, ValueError):
                continue
            evt = Event(
                event_id=str(raw.get("event_id", "")),
                user_id=str(raw.get("user_id", "")),
                event_type=str(raw.get("event_type", "")),
                created_at=created,
                metadata=raw.get("metadata") or {},
            )
            events.append(evt)
        return events


def generate_random_events(users: List[User], count: int = 50) -> List[Event]:
    if not users or count <= 0:
        return []
    result: List[Event] = []
    now = datetime.utcnow()
    for i in range(count):
        user = random.choice(users)
        created = now - timedelta(minutes=random.randint(0, 240))
        evt = Event(
            event_id=f"e{i+1}",
            user_id=user.user_id,
            event_type=random.choice(["page_view", "purchase", "signup"]),
            created_at=created,
            metadata={"value": random.randint(1, 100)},
        )
        result.append(evt)
    return result


def write_events(path: Path, events: List[Event]) -> None:
    payload = {"events": [e.to_dict() for e in events]}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def filter_recent_events(events: List[Event], minutes: int = 60) -> List[Event]:
    now = datetime.utcnow()
    return [e for e in events if e.is_recent(now, minutes=minutes)]


def build_segments() -> List[Segment]:
    return [
        Segment(name="EU-active", countries=["DE", "FR", "ES"], min_events=2),
        Segment(name="Global-heavy", countries=[], min_events=5),
    ]


def assign_segments(
    users: List[User],
    events: List[Event],
    segments: List[Segment],
) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {u.user_id: [] for u in users}
    for seg in segments:
        for u in users:
            if not u.is_active():
                continue
            if seg.matches(u, events):
                mapping[u.user_id].append(seg.name)
    return mapping


def export_segments(path: Path, mapping: Dict[str, List[str]]) -> None:
    payload = [{"user_id": uid, "segments": segs} for uid, segs in mapping.items()]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"memberships": payload}, f, indent=2, ensure_ascii=False)


def load_or_create_users(path: Path) -> UserStore:
    store = UserStore(path)
    store.load()
    if not store.all():
        for i in range(10):
            user = User(
                user_id=f"u{i+1}",
                name=f"User {i+1}",
                country=random.choice(["DE", "FR", "US", "IN"]),
                properties={"active": True},
            )
            store.upsert(user)
        store.save()
    return store


def main(base_dir: str = "data") -> int:
    base = Path(base_dir)
    users_path = base / "users.json"
    events_path = base / "events.json"
    segments_path = base / "segments.json"

    store = load_or_create_users(users_path)
    event_store = EventStore(events_path)
    events = event_store.load()

    if not events:
        events = generate_random_events(store.all(), count=80)
        write_events(events_path, events)

    recent = filter_recent_events(events, minutes=90)
    if not recent:
        recent = events

    segments = build_segments()
    mapping = assign_segments(store.all(), recent, segments)
    export_segments(segments_path, mapping)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
