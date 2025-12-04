from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Iterable, Any, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


@dataclass
class SensorReading:
    device_id: str
    ts: datetime
    value: float
    status: str = "ok"
    meta: Dict[str, Any] = field(default_factory=dict)

    def is_recent(self, hours: int = 1) -> bool:
        now = datetime.utcnow()
        return self.ts >= now - timedelta(hours=hours)

    def is_anomalous(self, min_val: float = 0.0, max_val: float = 100.0) -> bool:
        if self.status != "ok":
            return True
        if self.value < min_val:
            return True
        if self.value > max_val:
            return True
        return False

    def to_row(self) -> List[str]:
        return [
            self.device_id,
            self.ts.isoformat(),
            str(self.value),
            self.status,
        ]

    @classmethod
    def from_row(cls, row: Dict[str, str]) -> Optional["SensorReading"]:
        try:
            ts = datetime.fromisoformat(row["timestamp"])
            value = float(row["value"])
            device_id = row.get("device_id", "").strip()
            status = row.get("status", "ok").strip()
            if not device_id:
                return None
            return cls(device_id=device_id, ts=ts, value=value, status=status)
        except (KeyError, ValueError):
            return None


@dataclass
class DeviceState:
    device_id: str
    last_seen: Optional[datetime] = None
    values: List[float] = field(default_factory=list)
    statuses: List[str] = field(default_factory=list)

    def update(self, reading: SensorReading) -> None:
        self.last_seen = reading.ts
        self.values.append(reading.value)
        self.statuses.append(reading.status)

    def average_value(self) -> Optional[float]:
        if not self.values:
            return None
        return sum(self.values) / len(self.values)

    def is_stale(self, max_age_minutes: int = 10) -> bool:
        if self.last_seen is None:
            return True
        return self.last_seen < datetime.utcnow() - timedelta(minutes=max_age_minutes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "average": self.average_value(),
            "count": len(self.values),
            "stale": self.is_stale(),
        }


class TelemetryClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def fetch_remote_config(self, device_id: str) -> Dict[str, Any]:
        if not self.base_url:
            return {}
        url = self._url(f"/config/{device_id}")
        req = Request(url, method="GET")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            if not isinstance(data, dict):
                return {}
            return data
        except (URLError, HTTPError, ValueError):
            return {}

    def push_aggregate(self, payload: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = self._url("/aggregate")
        body = json.dumps(payload).encode("utf-8")
        req = Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                code = resp.getcode()
            return 200 <= code < 300
        except (URLError, HTTPError):
            return False


def parse_csv(path: Path) -> List[SensorReading]:
    readings: List[SensorReading] = []
    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                reading = SensorReading.from_row(row)
                if reading is None:
                    continue
                readings.append(reading)
    except FileNotFoundError:
        return []
    return readings


def aggregate_by_device(readings: Iterable[SensorReading]) -> Dict[str, DeviceState]:
    devices: Dict[str, DeviceState] = {}
    for r in readings:
        if r.device_id not in devices:
            devices[r.device_id] = DeviceState(device_id=r.device_id)
        devices[r.device_id].update(r)
    return devices


def detect_anomalies(
    readings: Iterable[SensorReading],
    min_val: float = 0.0,
    max_val: float = 100.0,
) -> List[SensorReading]:
    anomalies: List[SensorReading] = []
    for r in readings:
        if r.is_anomalous(min_val=min_val, max_val=max_val):
            anomalies.append(r)
    return anomalies


def save_report(
    path: Path,
    devices: Dict[str, DeviceState],
    anomalies: List[SensorReading],
) -> None:
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "devices": [d.to_dict() for d in devices.values()],
        "anomalies": [a.to_row() for a in anomalies],
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    tmp.replace(path)


def load_config(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (FileNotFoundError, ValueError):
        return {}


def summarize_anomalies(anomalies: Iterable[SensorReading]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in anomalies:
        counts[r.device_id] = counts.get(r.device_id, 0) + 1
    return counts


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    csv_path = base / "readings.csv"
    report_path = base / "report.json"
    cfg_path = base / "config.json"
    cfg = load_config(cfg_path)
    min_val = float(cfg.get("min_value", 0.0))
    max_val = float(cfg.get("max_value", 100.0))
    readings = parse_csv(csv_path)
    if not readings:
        return 1
    recent = [r for r in readings if r.is_recent(hours=cfg.get("recent_hours", 1))]
    devices = aggregate_by_device(recent)
    anomalies = detect_anomalies(recent, min_val=min_val, max_val=max_val)
    save_report(report_path, devices, anomalies)
    client = TelemetryClient(base_url=base_url or cfg.get("api_url", ""), timeout=5)
    summary = summarize_anomalies(anomalies)
    payload = {"summary": summary, "device_count": len(devices)}
    client.push_aggregate(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
