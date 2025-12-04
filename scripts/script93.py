from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class Event:
    event_id: str
    kind: str
    value: float
    occurred_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_recent(self, minutes: int = 60) -> bool:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        if self.occurred_at < cutoff:
            return False
        return True

    def matches_type(self, query: str) -> bool:
        q = query.lower().strip()
        if not q:
            return True
        if q in self.kind.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "value": self.value,
            "occurred_at": self.occurred_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Event"]:
        try:
            ts_raw = raw.get("occurred_at")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                event_id=str(raw.get("event_id", "")),
                kind=str(raw.get("kind", "")),
                value=float(raw.get("value", 0.0)),
                occurred_at=ts,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class UserProfile:
    user_id: str
    name: str
    preferred_kinds: List[str]
    updated_at: datetime

    def prefers(self, kind: str) -> bool:
        if not self.preferred_kinds:
            return True
        return kind.lower() in (k.lower() for k in self.preferred_kinds)

    def needs_refresh(self, days: int = 7) -> bool:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.updated_at < cutoff

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "preferred_kinds": list(self.preferred_kinds),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["UserProfile"]:
        try:
            ts_raw = raw.get("updated_at")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                user_id=str(raw.get("user_id", "")),
                name=str(raw.get("name", "")),
                preferred_kinds=list(raw.get("preferred_kinds", [])),
                updated_at=ts,
            )
        except Exception:
            return None


@dataclass
class TimelineState:
    user_id: str
    profile: Optional[UserProfile] = None
    events: List[Event] = field(default_factory=list)

    def add_event(self, event: Event) -> None:
        self.events.append(event)

    def recent_events(self, minutes: int = 60) -> List[Event]:
        return [e for e in self.events if e.is_recent(minutes)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "profile": self.profile.to_dict() if self.profile else None,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "TimelineState":
        state = cls(user_id=str(raw.get("user_id", "local")))
        p_raw = raw.get("profile")
        if p_raw:
            prof = UserProfile.from_dict(p_raw)
            if prof:
                state.profile = prof
        for e_raw in raw.get("events", []):
            e = Event.from_dict(e_raw)
            if e:
                state.events.append(e)
        return state


class AnalyticsClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_score(self, user_id: str) -> Optional[float]:
        url = self._url(f"score/{user_id}")
        if not url:
            return None
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
            parsed = json.loads(data)
            score = parsed.get("score")
            return float(score) if score is not None else None
        except (error.URLError, ValueError, json.JSONDecodeError):
            return None

    def push_summary(self, summary: Dict[str, Any]) -> bool:
        url = self._url("summary")
        if not url:
            return False
        try:
            body = json.dumps(summary).encode("utf-8")
            req = request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except error.URLError:
            return False


def load_state(path: Path) -> TimelineState:
    if not path.exists():
        return TimelineState(user_id="local")
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return TimelineState.from_dict(raw)
    except Exception:
        return TimelineState(user_id="local")


def save_state(path: Path, state: TimelineState) -> None:
    payload = json.dumps(state.to_dict(), ensure_ascii=False, indent=2)
    tmp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_engagement(state: TimelineState) -> Dict[str, Any]:
    if not state.events:
        return {"count": 0, "avg_value": None, "by_kind": {}}
    by_kind: Dict[str, List[float]] = {}
    for e in state.events:
        by_kind.setdefault(e.kind, []).append(e.value)
    avg_by_kind = {k: sum(v) / len(v) for k, v in by_kind.items()}
    all_vals = [e.value for e in state.events]
    return {"count": len(state.events), "avg_value": sum(all_vals) / len(all_vals), "by_kind": avg_by_kind}


def detect_bursts(state: TimelineState, window_minutes: int = 30) -> List[Dict[str, Any]]:
    if not state.events:
        return []
    sorted_events = sorted(state.events, key=lambda e: e.occurred_at)
    bursts: List[Dict[str, Any]] = []
    start = 0
    while start < len(sorted_events):
        end = start
        window_start = sorted_events[start].occurred_at
        while end < len(sorted_events) and (sorted_events[end].occurred_at - window_start).total_seconds() <= window_minutes * 60:
            end += 1
        if end - start >= 3:
            bursts.append({"from": window_start.isoformat(), "to": sorted_events[end - 1].occurred_at.isoformat(), "count": end - start})
        start += 1
    return bursts


def simulate_events(state: TimelineState, count: int = 10) -> int:
    kinds = ["click", "view", "purchase"]
    created = 0
    now = datetime.utcnow()
    for i in range(count):
        kind = random.choice(kinds)
        ts = now - timedelta(minutes=random.randint(0, 180))
        value = random.uniform(1.0, 100.0)
        ev = Event(event_id=f"sim-{len(state.events)+i}", kind=kind, value=value, occurred_at=ts, tags=[kind])
        state.add_event(ev)
        created += 1
    return created


def summarize_state(state: TimelineState, score: Optional[float]) -> Dict[str, Any]:
    engagement = compute_engagement(state)
    bursts = detect_bursts(state)
    return {
        "user_id": state.user_id,
        "profile_name": state.profile.name if state.profile else None,
        "score": score,
        "engagement": engagement,
        "burst_count": len(bursts),
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    state_path = base / "timeline_state.json"
    summary_path = base / "timeline_summary.json"

    state = load_state(state_path)
    if not state.events:
        simulate_events(state, count=15)

    client = AnalyticsClient(base_url=base_url)
    score = client.fetch_score(state.user_id)
    summary = summarize_state(state, score)

    try:
        save_state(state_path, state)
        summary_payload = json.dumps(summary, ensure_ascii=False, indent=2)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary_payload, encoding="utf-8")
        if base_url:
            client.push_summary(summary)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
