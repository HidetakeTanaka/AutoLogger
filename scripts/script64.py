from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


@dataclass
class Device:
    device_id: str
    kind: str
    last_seen: datetime
    online: bool = True
    metrics: Dict[str, float] = field(default_factory=dict)

    def is_recent(self, minutes: int = 5) -> bool:
        ref = datetime.utcnow() - timedelta(minutes=minutes)
        if self.last_seen >= ref:
            return True
        return False

    def update_metric(self, name: str, value: float) -> None:
        self.metrics[name] = value
        self.last_seen = datetime.utcnow()
        if value < 0:
            self.online = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "kind": self.kind,
            "last_seen": self.last_seen.isoformat(),
            "online": self.online,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Device"]:
        try:
            ts_raw = raw.get("last_seen")
            last_seen = (
                datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            )
            return cls(
                device_id=str(raw.get("device_id", "")),
                kind=str(raw.get("kind", "")),
                last_seen=last_seen,
                online=bool(raw.get("online", True)),
                metrics=dict(raw.get("metrics", {})),
            )
        except Exception:
            return None


class Fleet:
    def __init__(self, fleet_id: str) -> None:
        self.fleet_id = fleet_id
        self._devices: Dict[str, Device] = {}

    def add(self, device: Device) -> None:
        self._devices[device.device_id] = device

    def get(self, device_id: str) -> Optional[Device]:
        return self._devices.get(device_id)

    def all(self) -> List[Device]:
        return list(self._devices.values())

    def active_devices(self) -> List[Device]:
        return [d for d in self._devices.values() if d.online]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fleet_id": self.fleet_id,
            "devices": [d.to_dict() for d in self._devices.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Fleet":
        fleet = cls(fleet_id=str(raw.get("fleet_id", "local")))
        for d_raw in raw.get("devices", []):
            dev = Device.from_dict(d_raw)
            if dev:
                fleet.add(dev)
        return fleet


class TelemetryClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, fleet_id: str) -> str:
        return f"{self.base_url}/fleets/{fleet_id}.json"

    def fetch_fleet_snapshot(self, fleet_id: str) -> Optional[Dict[str, Any]]:
        if not self.base_url:
            return None
        url = self._url(fleet_id)
        req = Request(url, method="GET")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
            return json.loads(body.decode("utf-8"))
        except (URLError, HTTPError, ValueError):
            return None

    def push_aggregates(self, fleet_id: str, payload: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = self._url(fleet_id)
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (URLError, HTTPError):
            return False


def load_fleet(path: Path) -> Fleet:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Fleet.from_dict(raw)
    except Exception:
        return Fleet(fleet_id="local")


def save_fleet(path: Path, fleet: Fleet) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(fleet.to_dict(), indent=2)
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def compute_stats(fleet: Fleet) -> Dict[str, Any]:
    devices = fleet.all()
    if not devices:
        return {"count": 0, "online": 0, "avg_metrics": {}}
    online = sum(1 for d in devices if d.online)
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for d in devices:
        for k, v in d.metrics.items():
            totals[k] = totals.get(k, 0.0) + v
            counts[k] = counts.get(k, 0) + 1
    avg_metrics = {k: totals[k] / counts[k] for k in totals}
    return {"count": len(devices), "online": online, "avg_metrics": avg_metrics}


def detect_offline(fleet: Fleet, minutes: int = 10) -> List[str]:
    ref = datetime.utcnow() - timedelta(minutes=minutes)
    return [
        d.device_id
        for d in fleet.all()
        if (not d.online) or (d.last_seen < ref)
    ]


def simulate_fleet(fleet: Fleet, steps: int = 3) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    step = 0
    device_ids = [d.device_id for d in fleet.all()]
    while step < steps and device_ids:
        picked = random.choice(device_ids)
        dev = fleet.get(picked)
        if dev is None:
            step += 1
            continue
        metric_name = random.choice(["temp", "pressure", "load"])
        value = random.uniform(-5.0, 120.0)
        dev.update_metric(metric_name, value)
        history.append(
            {"step": step, "device_id": dev.device_id, "metric": metric_name, "value": value}
        )
        step += 1
    return history


def merge_remote_snapshot(fleet: Fleet, remote_raw: Optional[Dict[str, Any]]) -> int:
    if not remote_raw:
        return 0
    remote = Fleet.from_dict(remote_raw)
    added = 0
    for dev in remote.all():
        local = fleet.get(dev.device_id)
        if local is None:
            fleet.add(dev)
            added += 1
        else:
            if dev.last_seen > local.last_seen:
                local.last_seen = dev.last_seen
                local.metrics.update(dev.metrics)
                local.online = dev.online
    return added


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    fleet_path = base / "fleet.json"
    summary_path = base / "fleet_summary.json"

    fleet = load_fleet(fleet_path)
    client = TelemetryClient(base_url=base_url, timeout=5)

    remote = client.fetch_fleet_snapshot(fleet.fleet_id)
    merge_remote_snapshot(fleet, remote)

    simulate_fleet(fleet, steps=5)
    stats = compute_stats(fleet)
    stats["offline_devices"] = detect_offline(fleet)

    save_fleet(fleet_path, fleet)
    try:
        summary_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    except Exception:
        return 1

    client.push_aggregates(fleet.fleet_id, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
