from __future__ import annotations

import json
import random
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SensorReading:
    device_id: str
    metric: str
    value: float
    recorded_at: datetime
    tags: List[str] = field(default_factory=list)

    def is_recent(self, minutes: int = 30) -> bool:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        if self.recorded_at < cutoff:
            return False
        return True

    def matches_tag(self, query: str) -> bool:
        q = query.lower().strip()
        if not q:
            return True
        if q in self.metric.lower():
            return True
        return any(q in t.lower() for t in self.tags)

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
        ts_raw = raw.get("recorded_at")
        try:
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                device_id=str(raw.get("device_id", "")),
                metric=str(raw.get("metric", "")),
                value=float(raw.get("value", 0.0)),
                recorded_at=ts,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class DeviceStatus:
    device_id: str
    name: str
    online: bool
    last_seen: datetime

    def is_stale(self, minutes: int = 10) -> bool:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return self.last_seen < cutoff

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "online": self.online,
            "last_seen": self.last_seen.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["DeviceStatus"]:
        ts_raw = raw.get("last_seen")
        try:
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                device_id=str(raw.get("device_id", "")),
                name=str(raw.get("name", "")),
                online=bool(raw.get("online", False)),
                last_seen=ts,
            )
        except Exception:
            return None


@dataclass
class MonitoringState:
    site_id: str
    devices: Dict[str, DeviceStatus] = field(default_factory=dict)
    readings: List[SensorReading] = field(default_factory=list)

    def add_reading(self, reading: SensorReading) -> None:
        self.readings.append(reading)

    def recent_readings(self, minutes: int = 30) -> List[SensorReading]:
        return [r for r in self.readings if r.is_recent(minutes)]

    def filter_metric(self, metric: str) -> List[SensorReading]:
        return [r for r in self.readings if r.metric == metric]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_id": self.site_id,
            "devices": [d.to_dict() for d in self.devices.values()],
            "readings": [r.to_dict() for r in self.readings],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "MonitoringState":
        state = cls(site_id=str(raw.get("site_id", "local")))
        for d_raw in raw.get("devices", []):
            d = DeviceStatus.from_dict(d_raw)
            if d:
                state.devices[d.device_id] = d
        for r_raw in raw.get("readings", []):
            r = SensorReading.from_dict(r_raw)
            if r:
                state.readings.append(r)
        return state


class AlertClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}" if self.base_url else ""

    def push_alerts(self, alerts: List[Dict[str, Any]]) -> bool:
        if not self.base_url or not alerts:
            return False
        url = self._url("alerts")
        body = json.dumps({"alerts": alerts}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False


def load_state(path: Path) -> MonitoringState:
    if not path.exists():
        return MonitoringState(site_id="local")
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text or "{}")
        return MonitoringState.from_dict(raw)
    except Exception:
        return MonitoringState(site_id="local")


def save_state(path: Path, state: MonitoringState) -> None:
    payload = json.dumps(state.to_dict(), indent=2)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def compute_stats(state: MonitoringState) -> Dict[str, Any]:
    if not state.readings:
        return {"count": 0, "avg": None, "by_metric": {}}
    totals: Dict[str, List[float]] = {}
    for r in state.readings:
        totals.setdefault(r.metric, []).append(r.value)
    by_metric = {
        m: sum(vals) / len(vals)
        for m, vals in totals.items()
        if vals
    }
    overall_vals = [v for vals in totals.values() for v in vals]
    avg = sum(overall_vals) / len(overall_vals) if overall_vals else None
    return {"count": len(state.readings), "avg": avg, "by_metric": by_metric}


def filter_alerts(state: MonitoringState, metric: str, limit: float) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    for r in state.filter_metric(metric):
        if r.value > limit:
            alerts.append(
                {
                    "device_id": r.device_id,
                    "metric": r.metric,
                    "value": r.value,
                    "recorded_at": r.recorded_at.isoformat(),
                }
            )
    return alerts


def simulate_readings(state: MonitoringState, count: int = 10) -> int:
    if not state.devices:
        return 0
    metrics = ["temperature", "humidity", "pressure"]
    created = 0
    device_ids = list(state.devices.keys())
    for _ in range(count):
        did = random.choice(device_ids)
        metric = random.choice(metrics)
        value = round(random.uniform(10.0, 40.0), 2)
        ts = datetime.utcnow() - timedelta(minutes=random.randint(0, 60))
        state.add_reading(
            SensorReading(
                device_id=did,
                metric=metric,
                value=value,
                recorded_at=ts,
                tags=["simulated"],
            )
        )
        created += 1
    return created


def summarize_state(state: MonitoringState) -> Dict[str, Any]:
    stats = compute_stats(state)
    online = sum(1 for d in state.devices.values() if d.online)
    stale = sum(1 for d in state.devices.values() if d.is_stale())
    return {
        "site_id": state.site_id,
        "devices": len(state.devices),
        "online_devices": online,
        "stale_devices": stale,
        "reading_count": stats["count"],
        "avg_value": stats["avg"],
    }


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / "monitoring.json"
    state = load_state(state_path)

    if not state.devices:
        now = datetime.utcnow()
        for i in range(3):
            did = f"dev-{i+1}"
            state.devices[did] = DeviceStatus(
                device_id=did,
                name=f"Device {i+1}",
                online=True,
                last_seen=now,
            )

    simulate_readings(state, count=15)
    save_state(state_path, state)

    summary = summarize_state(state)
    alerts = filter_alerts(state, metric="temperature", limit=30.0)
    alert_payloads = alerts[:10]

    client = AlertClient(base_url=base_url) if base_url else None
    if client and alert_payloads:
        client.push_alerts(alert_payloads)

    summary_path = base / "summary.json"
    try:
        summary_path.write_text(json.dumps({"summary": summary, "alerts": alert_payloads}, indent=2), encoding="utf-8")
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
