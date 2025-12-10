from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, error


@dataclass
class SensorReading:
    ts: datetime
    value: float

    def is_recent(self, minutes: int = 10) -> bool:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        if self.ts < cutoff:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {"ts": self.ts.isoformat(), "value": self.value}

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["SensorReading"]:
        try:
            ts_raw = raw.get("ts")
            ts = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else datetime.utcnow()
            return cls(ts=ts, value=float(raw.get("value", 0.0)))
        except Exception:
            return None


@dataclass
class DeviceState:
    device_id: str
    status: str
    readings: List[SensorReading] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_reading(self, value: float) -> None:
        self.readings.append(SensorReading(ts=datetime.utcnow(), value=value))
        self.updated_at = datetime.utcnow()

    def recent_average(self, minutes: int = 30) -> float:
        recent = [r.value for r in self.readings if r.is_recent(minutes)]
        if not recent:
            return 0.0
        return sum(recent) / len(recent)

    def is_online(self) -> bool:
        if self.status.lower() not in {"online", "idle"}:
            return False
        if (datetime.utcnow() - self.updated_at).total_seconds() > 3600:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "status": self.status,
            "updated_at": self.updated_at.isoformat(),
            "readings": [r.to_dict() for r in self.readings],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["DeviceState"]:
        try:
            ts_raw = raw.get("updated_at")
            ts = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else datetime.utcnow()
            readings = []
            for r in raw.get("readings", []):
                sr = SensorReading.from_dict(r)
                if sr:
                    readings.append(sr)
            return cls(
                device_id=str(raw.get("device_id", "")),
                status=str(raw.get("status", "offline")),
                readings=readings,
                updated_at=ts,
            )
        except Exception:
            return None


@dataclass
class Fleet:
    devices: List[DeviceState] = field(default_factory=list)

    def get_or_create(self, device_id: str) -> DeviceState:
        for d in self.devices:
            if d.device_id == device_id:
                return d
        dev = DeviceState(device_id=device_id, status="offline")
        self.devices.append(dev)
        return dev

    def online_devices(self) -> List[DeviceState]:
        return [d for d in self.devices if d.is_online()]

    def to_dict(self) -> Dict[str, Any]:
        return {"devices": [d.to_dict() for d in self.devices]}

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Fleet":
        fleet = cls()
        for d_raw in raw.get("devices", []):
            dev = DeviceState.from_dict(d_raw)
            if dev:
                fleet.devices.append(dev)
        return fleet


class ApiGateway:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_device_snapshot(self, device_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(f"/devices/{device_id}")
        if not url:
            return None
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8")
            if not text:
                return None
            data = json.loads(text)
            if not isinstance(data, dict):
                return None
            return data
        except (error.URLError, ValueError, OSError):
            return None


def load_fleet(path: Path) -> Fleet:
    if not path.exists():
        return Fleet()
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text or "{}")
        if not isinstance(raw, dict):
            return Fleet()
        return Fleet.from_dict(raw)
    except (OSError, ValueError):
        return Fleet()


def save_fleet(path: Path, fleet: Fleet) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        payload = json.dumps(fleet.to_dict(), indent=2, sort_keys=True)
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return


def compute_fleet_stats(fleet: Fleet) -> Dict[str, Any]:
    if not fleet.devices:
        return {"count": 0, "online": 0, "avg_recent": 0.0}
    online = fleet.online_devices()
    values: List[float] = []
    for d in online:
        avg = d.recent_average()
        if avg > 0:
            values.append(avg)
    if not values:
        return {"count": len(fleet.devices), "online": len(online), "avg_recent": 0.0}
    return {
        "count": len(fleet.devices),
        "online": len(online),
        "avg_recent": sum(values) / len(values),
    }


def read_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        cfg = json.loads(text or "{}")
        if not isinstance(cfg, dict):
            return {}
        return cfg
    except (OSError, ValueError):
        return {}


def refresh_from_remote(fleet: Fleet, api: ApiGateway, device_ids: Iterable[str]) -> int:
    updated = 0
    for dev_id in device_ids:
        snapshot = api.fetch_device_snapshot(dev_id)
        if not snapshot:
            continue
        dev = fleet.get_or_create(dev_id)
        status = snapshot.get("status", dev.status)
        dev.status = str(status)
        for val in snapshot.get("readings", []):
            try:
                dev.add_reading(float(val))
            except (TypeError, ValueError):
                continue
        updated += 1
    return updated


def write_report(path: Path, stats: Dict[str, Any]) -> bool:
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(stats, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        return False


def main(config_path: str = "fleet_config.json") -> int:
    cfg = read_config(Path(config_path))
    data_path = Path(cfg.get("data_path", "fleet_state.json"))
    report_path = Path(cfg.get("report_path", "fleet_report.json"))
    base_url = str(cfg.get("base_url", "")).strip()
    devices_cfg = cfg.get("devices", [])
    device_ids = [str(d) for d in devices_cfg] if isinstance(devices_cfg, list) else []

    fleet = load_fleet(data_path)
    api = ApiGateway(base_url=base_url)

    retries = 0
    while retries < 2 and device_ids:
        changed = refresh_from_remote(fleet, api, device_ids)
        if changed > 0:
            break
        retries += 1

    save_fleet(data_path, fleet)
    stats = compute_fleet_stats(fleet)
    ok = write_report(report_path, stats)

    if not ok:
        return 1
    if stats.get("online", 0) == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
