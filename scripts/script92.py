from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class MetricSample:
    user_id: str
    metric: str
    value: float
    recorded_at: datetime
    tags: Set[str]

    def is_recent(self, hours: int = 24) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.recorded_at < cutoff:
            return False
        return True

    def matches_tag(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "metric": self.metric,
            "value": self.value,
            "recorded_at": self.recorded_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["MetricSample"]:
        try:
            ts_raw = raw.get("recorded_at")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                user_id=str(raw.get("user_id", "")),
                metric=str(raw.get("metric", "")),
                value=float(raw.get("value", 0.0)),
                recorded_at=ts,
                tags=set(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class Profile:
    user_id: str
    name: str
    target_value: float
    updated_at: datetime

    def needs_update(self, hours: int = 72) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return self.updated_at < cutoff

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "target_value": self.target_value,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Profile"]:
        try:
            ts_raw = raw.get("updated_at")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                user_id=str(raw.get("user_id", "")),
                name=str(raw.get("name", "")),
                target_value=float(raw.get("target_value", 0.0)),
                updated_at=ts,
            )
        except Exception:
            return None


@dataclass
class MetricsState:
    user_id: str
    profile: Optional[Profile] = None
    samples: List[MetricSample] = None

    def __post_init__(self) -> None:
        if self.samples is None:
            self.samples = []

    def add_sample(self, sample: MetricSample) -> None:
        if sample.user_id != self.user_id:
            return
        self.samples.append(sample)

    def recent_samples(self, hours: int = 24) -> List[MetricSample]:
        return [s for s in self.samples if s.is_recent(hours)]

    def average_value(self, metric: str) -> Optional[float]:
        vals = [s.value for s in self.samples if s.metric == metric]
        if not vals:
            return None
        return sum(vals) / len(vals)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "profile": self.profile.to_dict() if self.profile else None,
            "samples": [s.to_dict() for s in self.samples],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "MetricsState":
        state = cls(user_id=str(raw.get("user_id", "local")))
        p_raw = raw.get("profile")
        if p_raw:
            prof = Profile.from_dict(p_raw)
            if prof:
                state.profile = prof
        for r in raw.get("samples", []):
            s = MetricSample.from_dict(r)
            if s:
                state.samples.append(s)
        return state


class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_target(self, user_id: str) -> Optional[float]:
        url = self._url(f"target/{user_id}")
        if not url:
            return None
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError):
            return None
        try:
            parsed = json.loads(data)
            val = parsed.get("target_value")
            if val is None:
                return None
            return float(val)
        except Exception:
            return None


def load_state(path: Path) -> MetricsState:
    if not path.exists():
        return MetricsState(user_id="local")
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
        return MetricsState.from_dict(raw)
    except Exception:
        return MetricsState(user_id="local")


def save_state(path: Path, state: MetricsState) -> None:
    payload = json.dumps(state.to_dict(), indent=2)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_daily_summary(
    state: MetricsState, day: Optional[date] = None
) -> Dict[str, Any]:
    if day is None:
        day = datetime.utcnow().date()
    vals = [s.value for s in state.samples if s.recorded_at.date() == day]
    if not vals:
        return {"date": day.isoformat(), "count": 0, "avg": None}
    avg = sum(vals) / len(vals)
    return {"date": day.isoformat(), "count": len(vals), "avg": avg}


def apply_remote_target(state: MetricsState, client: RecommendationClient) -> Optional[float]:
    if not client.base_url:
        return None
    val = client.fetch_target(state.user_id)
    if val is None:
        return None
    if state.profile is None:
        state.profile = Profile(
            user_id=state.user_id,
            name="User",
            target_value=val,
            updated_at=datetime.utcnow(),
        )
    else:
        state.profile.target_value = val
        state.profile.updated_at = datetime.utcnow()
    return val


def simulate_samples(state: MetricsState, days: int = 3) -> int:
    created = 0
    now = datetime.utcnow()
    metrics = ["steps", "sleep", "focus"]
    i = 0
    while i < days * 3:
        metric = random.choice(metrics)
        value = random.uniform(0, 100)
        ts = now - timedelta(hours=random.randint(0, days * 24))
        sample = MetricSample(
            user_id=state.user_id,
            metric=metric,
            value=value,
            recorded_at=ts,
            tags={metric, "simulated"},
        )
        state.add_sample(sample)
        created += 1
        i += 1
    return created


def summarize_state(state: MetricsState, remote_target: Optional[float]) -> Dict[str, Any]:
    today = compute_daily_summary(state)
    avg_steps = state.average_value("steps")
    target = remote_target
    if target is None and state.profile:
        target = state.profile.target_value
    return {
        "user_id": state.user_id,
        "today": today,
        "avg_steps": avg_steps,
        "target_value": target,
        "sample_count": len(state.samples),
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    state_path = base / "metrics_state.json"
    summary_path = base / "metrics_summary.json"

    state = load_state(state_path)
    simulate_samples(state, days=2)

    client = RecommendationClient(base_url=base_url, timeout=5)
    target = apply_remote_target(state, client)

    summary = summarize_state(state, target)
    save_state(state_path, state)
    try:
        summary_payload = json.dumps(summary, indent=2)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary_payload, encoding="utf-8")
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
