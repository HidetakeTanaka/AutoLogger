from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class Sensor:
    sensor_id: str
    location: str
    unit: str
    threshold: float

    def is_temperature(self) -> bool:
        return self.unit.lower() in {"c", "celsius", "k", "kelvin"}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "location": self.location,
            "unit": self.unit,
            "threshold": self.threshold,
        }


@dataclass
class Reading:
    sensor_id: str
    value: float
    ts: str

    def exceeds(self, threshold: float) -> bool:
        return self.value > threshold

    def to_tuple(self) -> Tuple[str, float]:
        return self.sensor_id, self.value


class SensorStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._sensors: Dict[str, Sensor] = {}

    def load(self) -> None:
        if not self.path.exists():
            self._sensors = {}
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._sensors = {}
            return
        sensors: Dict[str, Sensor] = {}
        for raw in data.get("sensors", []):
            try:
                sid = str(raw["sensor_id"])
                loc = str(raw.get("location", ""))
                unit = str(raw.get("unit", "C"))
                thr = float(raw.get("threshold", 0.0))
            except (KeyError, ValueError):
                continue
            sensors[sid] = Sensor(sensor_id=sid, location=loc, unit=unit, threshold=thr)
        self._sensors = sensors

    def get(self, sensor_id: str) -> Optional[Sensor]:
        return self._sensors.get(sensor_id)

    def all(self) -> List[Sensor]:
        return list(self._sensors.values())


def load_readings_csv(path: Path) -> List[Reading]:
    readings: List[Reading] = []
    if not path.exists():
        return readings
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    sid = str(row["sensor_id"])
                    value = float(row["value"])
                    ts = str(row.get("timestamp", ""))
                except (KeyError, ValueError):
                    continue
                readings.append(Reading(sensor_id=sid, value=value, ts=ts))
    except OSError:
        return readings
    return readings


def group_by_sensor(readings: List[Reading]) -> Dict[str, List[Reading]]:
    grouped: Dict[str, List[Reading]] = {}
    for r in readings:
        grouped.setdefault(r.sensor_id, []).append(r)
    return grouped


def compute_statistics(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "avg": 0.0}
    mn = min(values)
    mx = max(values)
    avg = sum(values) / len(values)
    return {"min": mn, "max": mx, "avg": avg}


def find_alarms(grouped: Dict[str, List[Reading]], store: SensorStore) -> List[Dict[str, Any]]:
    alarms: List[Dict[str, Any]] = []
    for sid, readings in grouped.items():
        sensor = store.get(sid)
        if sensor is None:
            continue
        for r in readings:
            if r.exceeds(sensor.threshold):
                alarms.append(
                    {
                        "sensor_id": sid,
                        "location": sensor.location,
                        "value": r.value,
                        "threshold": sensor.threshold,
                        "timestamp": r.ts,
                    }
                )
    return alarms


def export_alarms(path: Path, alarms: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"alarms": alarms}, f, indent=2, ensure_ascii=False)


def export_stats(path: Path, stats: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def summarize_sensors(grouped: Dict[str, List[Reading]], store: SensorStore) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for sid, readings in grouped.items():
        sensor = store.get(sid)
        if sensor is None:
            continue
        values = [r.value for r in readings]
        summary[sid] = {
            "location": sensor.location,
            "unit": sensor.unit,
            "stats": compute_statistics(values),
        }
    return summary


def main() -> int:
    base = Path("data")
    sensors_path = base / "sensors.json"
    readings_path = base / "readings.csv"
    alarms_path = base / "alarms.json"
    stats_path = base / "sensor_stats.json"
    config_path = base / "sensors_config.json"

    store = SensorStore(sensors_path)
    store.load()

    readings = load_readings_csv(readings_path)
    grouped = group_by_sensor(readings)

    alarms = find_alarms(grouped, store)
    export_alarms(alarms_path, alarms)

    stats = summarize_sensors(grouped, store)
    export_stats(stats_path, stats)

    cfg = load_config(config_path)
    if cfg.get("extra", False):
        _ = compute_statistics([1.0, 2.0, 3.0])

    if not readings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
