from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class SensorReading:
    sensor_id: str
    timestamp: float
    value: float
    unit: str

    def is_valid(self) -> bool:
        if self.value != self.value:  # NaN check
            return False
        return self.unit in {"C", "F", "K", "percent", "ppm"}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "timestamp": self.timestamp,
            "value": self.value,
            "unit": self.unit,
        }


@dataclass
class Device:
    device_id: str
    location: str
    active: bool = True
    readings: List[SensorReading] = field(default_factory=list)

    def add_reading(self, reading: SensorReading) -> None:
        if not reading.is_valid():
            return
        self.readings.append(reading)

    def latest_value(self) -> Optional[SensorReading]:
        if not self.readings:
            return None
        return max(self.readings, key=lambda r: r.timestamp)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "location": self.location,
            "active": self.active,
            "readings": [r.to_dict() for r in self.readings],
        }


@dataclass
class Fleet:
    devices: Dict[str, Device] = field(default_factory=dict)

    def get_or_create(self, device_id: str, location: str) -> Device:
        if device_id in self.devices:
            return self.devices[device_id]
        dev = Device(device_id=device_id, location=location)
        self.devices[device_id] = dev
        return dev

    def all_readings(self) -> List[SensorReading]:
        result: List[SensorReading] = []
        for dev in self.devices.values():
            result.extend(dev.readings)
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {"devices": [d.to_dict() for d in self.devices.values()]}


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def fetch_remote_readings(url: str, retries: int = 2, timeout: int = 4) -> List[Dict[str, Any]]:
    attempt = 0
    while attempt <= retries:
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except (error.URLError, error.HTTPError):
            if attempt == retries:
                return []
            attempt += 1
            time.sleep(0.2)
            continue
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return []
        items = data.get("readings")
        if not isinstance(items, list):
            return []
        return [dict(item) for item in items]
    return []


def read_local_cache(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("readings")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows]


def normalize_row(row: Dict[str, Any]) -> Optional[SensorReading]:
    try:
        device_id = str(row["device_id"])
        sensor_id = str(row["sensor_id"])
        value = float(row["value"])
        unit = str(row.get("unit", "C"))
        ts = float(row.get("timestamp", time.time()))
        location = str(row.get("location", "unknown"))
    except (KeyError, ValueError, TypeError):
        return None
    reading = SensorReading(sensor_id=f"{device_id}:{sensor_id}", timestamp=ts, value=value, unit=unit)
    if not reading.is_valid():
        return None
    return reading


def ingest_readings(fleet: Fleet, rows: List[Dict[str, Any]]) -> None:
    for row in rows:
        reading = normalize_row(row)
        if reading is None:
            continue
        device_id = row.get("device_id", "unknown")
        location = row.get("location", "unknown")
        dev = fleet.get_or_create(str(device_id), str(location))
        dev.add_reading(reading)


def compute_statistics(readings: List[SensorReading]) -> Dict[str, Any]:
    if not readings:
        return {"count": 0, "min": 0.0, "max": 0.0, "avg": 0.0}
    values = [r.value for r in readings]
    total = sum(values)
    count = len(values)
    if count == 0:
        return {"count": 0, "min": 0.0, "max": 0.0, "avg": 0.0}
    return {
        "count": count,
        "min": min(values),
        "max": max(values),
        "avg": total / count,
    }


def group_by_unit(readings: List[SensorReading]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[SensorReading]] = {}
    for r in readings:
        grouped.setdefault(r.unit, []).append(r)
    result: Dict[str, Dict[str, Any]] = {}
    for unit, group in grouped.items():
        result[unit] = compute_statistics(group)
    return result


def save_report(path: Path, fleet: Fleet, stats: Dict[str, Any]) -> None:
    payload = {
        "fleet": fleet.to_dict(),
        "summary": stats,
        "generated_at": time.time(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def select_recent(readings: List[SensorReading], seconds: int = 600) -> List[SensorReading]:
    if not readings:
        return []
    threshold = time.time() - seconds
    return [r for r in readings if r.timestamp >= threshold]


def main(base_dir: str = "data") -> int:
    base = Path(base_dir)
    cfg = load_config(base / "fleet_config.json")
    api_url = str(cfg.get("api_url", ""))
    cache_path = base / "cache_readings.json"
    report_path = base / "fleet_report.json"

    fleet = Fleet()

    if api_url:
        remote_rows = fetch_remote_readings(api_url)
        ingest_readings(fleet, remote_rows)

    local_rows = read_local_cache(cache_path)
    ingest_readings(fleet, local_rows)

    all_readings = fleet.all_readings()
    if not all_readings:
        return 1

    recent = select_recent(all_readings, seconds=int(cfg.get("recent_window", 900)))
    stats = {
        "overall": compute_statistics(all_readings),
        "recent": compute_statistics(recent),
        "by_unit": group_by_unit(all_readings),
    }

    save_report(report_path, fleet, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
