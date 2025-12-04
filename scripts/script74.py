from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class SensorReading:
    timestamp: datetime
    value: float
    status: str = "ok"

    def is_ok(self, threshold: float = 0.0) -> bool:
        if self.status != "ok":
            return False
        return self.value >= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["SensorReading"]:
        try:
            ts_raw = str(raw.get("timestamp", ""))
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                timestamp=ts,
                value=float(raw.get("value", 0.0)),
                status=str(raw.get("status", "ok")),
            )
        except Exception:
            return None


@dataclass
class DeviceStatus:
    device_id: str
    name: str
    readings: List[SensorReading] = field(default_factory=list)

    def add_reading(self, reading: SensorReading) -> None:
        self.readings.append(reading)

    def recent_readings(self, minutes: int = 30) -> List[SensorReading]:
        ref = datetime.utcnow() - timedelta(minutes=minutes)
        return [r for r in self.readings if r.timestamp >= ref]

    def avg_value(self, minutes: int = 60) -> float:
        recents = self.recent_readings(minutes)
        if not recents:
            return 0.0
        return sum(r.value for r in recents) / len(recents)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "readings": [r.to_dict() for r in self.readings],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "DeviceStatus":
        dev = cls(
            device_id=str(raw.get("device_id", "")),
            name=str(raw.get("name", "")),
        )
        for sr in raw.get("readings", []):
            reading = SensorReading.from_dict(sr)
            if reading is not None:
                dev.add_reading(reading)
        return dev


class MetricsClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_thresholds(self) -> Optional[Dict[str, float]]:
        if not self.base_url:
            return None
        url = self._url("thresholds.json")
        try:
            req = request.Request(url)
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None

    def push_summary(self, summary: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = self._url("summaries")
        body = json.dumps(summary).encode("utf-8")
        req = request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except error.URLError:
            return False
        except Exception:
            return False


def load_devices(path: Path) -> List[DeviceStatus]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [DeviceStatus.from_dict(d) for d in raw]
    except FileNotFoundError:
        return []
    except Exception:
        return []


def save_devices(path: Path, devices: List[DeviceStatus]) -> None:
    payload = [d.to_dict() for d in devices]
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            return


def summarize_devices(devices: List[DeviceStatus]) -> Dict[str, Any]:
    if not devices:
        return {"count": 0, "avg_values": {}, "overall_avg": 0.0}
    avg_values = {d.device_id: d.avg_value() for d in devices}
    overall_vals = [v for v in avg_values.values() if v > 0]
    if not overall_vals:
        overall_avg = 0.0
    else:
        overall_avg = sum(overall_vals) / len(overall_vals)
    return {
        "count": len(devices),
        "avg_values": avg_values,
        "overall_avg": overall_avg,
    }


def detect_anomalies(
    devices: List[DeviceStatus], thresholds: Optional[Dict[str, float]]
) -> List[str]:
    if thresholds is None:
        return []
    incidents: List[str] = []
    for d in devices:
        limit = thresholds.get(d.device_id, thresholds.get("default", 0.0))
        if d.avg_value() < limit:
            incidents.append(d.device_id)
    return incidents


def simulate_cycle(devices: List[DeviceStatus], cycles: int = 3) -> None:
    if cycles <= 0 or not devices:
        return
    step = 0
    while step < cycles:
        step += 1
        for d in devices:
            base = random.uniform(10.0, 100.0)
            jitter = random.uniform(-5.0, 5.0)
            value = max(0.0, base + jitter)
            status = "ok" if random.random() > 0.1 else "error"
            d.add_reading(SensorReading(datetime.utcnow(), value, status))


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    store_path = base / "devices.json"
    devices = load_devices(store_path)
    if not devices:
        devices = [
            DeviceStatus("svc-a", "Service A"),
            DeviceStatus("svc-b", "Service B"),
        ]
    simulate_cycle(devices, cycles=5)
    summary = summarize_devices(devices)
    client = MetricsClient(base_url=base_url, timeout=5)
    thresholds = client.fetch_thresholds()
    incidents = detect_anomalies(devices, thresholds)
    summary["incidents"] = incidents
    save_devices(store_path, devices)
    output_path = base / "summary.json"
    try:
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        return 1
    pushed = client.push_summary(summary)
    if not pushed and base_url:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
