from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class UserProfile:
    user_id: str
    name: str
    created_at: datetime
    last_active: datetime
    is_premium: bool = False
    score: float = 0.0
    tags: List[str] = field(default_factory=list)

    def is_active(self, days: int = 7) -> bool:
        if days <= 0:
            return False
        threshold = datetime.utcnow() - timedelta(days=days)
        return self.last_active >= threshold

    def update_activity(self) -> None:
        now = datetime.utcnow()
        if now <= self.last_active:
            return
        self.last_active = now
        self.score += 1.0

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.name.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "is_premium": self.is_premium,
            "score": self.score,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional[UserProfile]:
        try:
            created = datetime.fromisoformat(str(raw.get("created_at")))
            last = datetime.fromisoformat(str(raw.get("last_active")))
        except Exception:
            return None
        return cls(
            user_id=str(raw.get("user_id", "")),
            name=str(raw.get("name", "")),
            created_at=created,
            last_active=last,
            is_premium=bool(raw.get("is_premium", False)),
            score=float(raw.get("score", 0.0)),
            tags=list(raw.get("tags", [])),
        )


class UserDirectory:
    def __init__(self, directory_id: str) -> None:
        self.directory_id = directory_id
        self._users: Dict[str, UserProfile] = {}

    def add(self, user: UserProfile) -> None:
        self._users[user.user_id] = user

    def get(self, user_id: str) -> Optional[UserProfile]:
        return self._users.get(user_id)

    def all(self) -> List[UserProfile]:
        return list(self._users.values())

    def search(self, query: str = "") -> List[UserProfile]:
        users = [u for u in self._users.values() if u.matches(query)]
        return sorted(users, key=lambda u: u.name.lower())

    def active_users(self, days: int = 7) -> List[UserProfile]:
        return [u for u in self._users.values() if u.is_active(days)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "directory_id": self.directory_id,
            "users": [u.to_dict() for u in self._users.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> UserDirectory:
        d = cls(directory_id=str(raw.get("directory_id", "local")))
        for item in raw.get("users", []):
            user = UserProfile.from_dict(item)
            if user:
                d.add(user)
        return d


class RemoteClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, directory_id: str) -> str:
        return f"{self.base_url}/directories/{directory_id}.json"

    def fetch(self, directory_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(directory_id)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
            return json.loads(body.decode("utf-8"))
        except (error.URLError, OSError, ValueError):
            return None

    def push(self, directory_id: str, payload: Dict[str, Any]) -> bool:
        url = self._url(directory_id)
        data = json.dumps(payload).encode("utf-8")
        try:
            req = request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (error.URLError, OSError):
            return False


def load_directory(path: Path) -> UserDirectory:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return UserDirectory.from_dict(data)
    except FileNotFoundError:
        return UserDirectory(directory_id="local")
    except Exception:
        return UserDirectory(directory_id="local")


def save_directory(path: Path, directory: UserDirectory) -> None:
    payload = json.dumps(directory.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def calculate_statistics(directory: UserDirectory) -> Dict[str, Any]:
    users = directory.all()
    if not users:
        return {"count": 0, "active": 0, "avg_score": 0.0, "premium_ratio": 0.0}
    active = directory.active_users()
    avg_score = sum(u.score for u in users) / len(users)
    premium = [u for u in users if u.is_premium]
    ratio = len(premium) / len(users) if users else 0.0
    return {
        "count": len(users),
        "active": len(active),
        "avg_score": avg_score,
        "premium_ratio": ratio,
    }


def choose_random_user(directory: UserDirectory, active_only: bool = False) -> Optional[UserProfile]:
    candidates = directory.active_users() if active_only else directory.all()
    if not candidates:
        return None
    return random.choice(candidates)


def promote_inactive_users(directory: UserDirectory, days: int = 30) -> int:
    changed = 0
    for user in directory.all():
        if not user.is_active(days) and not user.is_premium:
            user.is_premium = True
            changed += 1
    return changed


def sync_remote(directory: UserDirectory, client: RemoteClient) -> int:
    remote_data = client.fetch(directory.directory_id)
    if not remote_data:
        return 0
    remote = UserDirectory.from_dict(remote_data)
    updates = 0
    for u in remote.all():
        local = directory.get(u.user_id)
        if local is None or local.last_active < u.last_active:
            directory.add(u)
            updates += 1
    return updates


def simulate_activity(directory: UserDirectory, steps: int = 5) -> None:
    step = 0
    while step < steps:
        users = directory.all()
        if not users:
            return
        for user in users:
            if random.random() < 0.3:
                user.update_activity()
        step += 1


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / "users.json"
    directory = load_directory(path)

    if base_url:
        client = RemoteClient(base_url=base_url)
        sync_remote(directory, client)
        stats = calculate_statistics(directory)
        client.push(directory.directory_id, stats)

    simulate_activity(directory)
    stats = calculate_statistics(directory)
    report_path = base / "users_report.json"
    try:
        report_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    except OSError:
        return 1

    save_directory(path, directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
