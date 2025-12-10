from __future__ import annotations
import json, random, urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class SensorReading:
    device_id: str
    metric: str
    value: float
    recorded_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_recent(self, minutes: int = 60) -> bool:
        return self.recorded_at >= datetime.utcnow() - timedelta(minutes=minutes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "metric": self.metric,
            "value": self.value,
            "recorded_at": self.recorded_at.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["SensorReading"]:
        try:
            ts_raw = raw.get("recorded_at")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                str(raw.get("device_id", "")),
                str(raw.get("metric", "")),
                float(raw.get("value", 0.0)),
                ts,
                list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class DeviceState:
    device_id: str
    threshold: float = 50.0
    updated_at: datetime = field(default_factory=datetime.utcnow)
    readings: List[SensorReading] = field(default_factory=list)

    def add_reading(self, reading: SensorReading) -> None:
        if reading.device_id == self.device_id:
            self.readings.append(reading)

    def needs_refresh(self, hours: int = 24) -> bool:
        return self.updated_at < datetime.utcnow() - timedelta(hours=hours)

    def daily_average(self, day: date, metric: str) -> Optional[float]:
        vals = [
            r.value
            for r in self.readings
            if r.metric == metric and r.recorded_at.date() == day
        ]
        return sum(vals) / len(vals) if vals else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "threshold": self.threshold,
            "updated_at": self.updated_at.isoformat(),
            "readings": [r.to_dict() for r in self.readings],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "DeviceState":
        try:
            ts_raw = raw.get("updated_at")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
        except Exception:
            ts = datetime.utcnow()
        state = cls(
            str(raw.get("device_id", "")),
            float(raw.get("threshold", 50.0)),
            ts,
        )
        for rr in raw.get("readings", []):
            r = SensorReading.from_dict(rr)
            if r is not None:
                state.readings.append(r)
        return state


class TelemetryClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url, self.timeout = base_url.rstrip("/"), timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}" if self.base_url else ""

    def fetch_remote_threshold(self, device_id: str) -> Optional[float]:
        url = self._url(f"devices/{device_id}/threshold")
        if not url:
            return None
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            val = json.loads(data.decode("utf-8")).get("threshold")
            return float(val) if val is not None else None
        except Exception:
            return None

    def push_summary(self, summary: Dict[str, Any]) -> bool:
        url = self._url("devices/summary")
        if not url:
            return False
        body = json.dumps(summary).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False


def load_state(path: Path) -> DeviceState:
    if not path.exists():
        return DeviceState(device_id="local")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return DeviceState.from_dict(raw)
    except Exception:
        return DeviceState(device_id="local")


def save_state(path: Path, state: DeviceState) -> None:
    payload = json.dumps(state.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_stats(state: DeviceState) -> Dict[str, Any]:
    if not state.readings:
        return {"count": 0, "over_threshold": 0, "metrics": {}}
    metrics: Dict[str, List[float]] = {}
    over = 0
    for r in state.readings:
        metrics.setdefault(r.metric, []).append(r.value)
        if r.value > state.threshold:
            over += 1
    avg = {m: (sum(v) / len(v)) for m, v in metrics.items()}
    return {"count": len(state.readings), "over_threshold": over, "metrics": avg}


def simulate_readings(state: DeviceState, hours: int = 12) -> int:
    metrics = ["temp", "humidity", "pressure"]
    created = 0
    now = datetime.utcnow()
    h = 0
    while h < hours:
        ts = now - timedelta(hours=h)
        for m in metrics:
            if random.random() < 0.4:
                continue
            val = round(random.uniform(0, 100), 2)
            state.add_reading(
                SensorReading(state.device_id, m, val, ts, tags=[m, "sim"])
            )
            created += 1
        h += 1
    return created


def summarize_state(state: DeviceState, remote_threshold: Optional[float]) -> Dict[str, Any]:
    if remote_threshold is not None:
        state.threshold, state.updated_at = remote_threshold, datetime.utcnow()
    stats = compute_stats(state)
    return {
        "device_id": state.device_id,
        "threshold": state.threshold,
        "count": stats["count"],
        "over_threshold": stats["over_threshold"],
        "metrics": stats["metrics"],
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    state_path, summary_path = base / "telemetry.json", base / "telemetry_summary.json"
    try:
        state = load_state(state_path)
        if not state.readings:
            simulate_readings(state, hours=24)
        client = TelemetryClient(base_url)
        remote = client.fetch_remote_threshold(state.device_id)
        summary = summarize_state(state, remote)
        save_state(state_path, state)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if base_url:
            client.push_summary(summary)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
