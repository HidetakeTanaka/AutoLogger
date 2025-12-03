import json
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Iterable


class Reading:
    def __init__(self, reading_id: str, value: float, ts: datetime, tags: Iterable[str]) -> None:
        self.reading_id = reading_id
        self.value = value
        self.ts = ts
        self.tags = list(tags)

    def is_recent(self, hours: int = 24) -> bool:
        if hours <= 0:
            return False
        return self.ts >= datetime.utcnow() - timedelta(hours=hours)

    def matches(self, keyword: str) -> bool:
        q = keyword.lower().strip()
        if not q:
            return True
        if q in str(self.value).lower():
            return True
        return any((q in t.lower() for t in self.tags))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "value": self.value,
            "ts": self.ts.isoformat(),
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Reading"]:
        try:
            ts_raw = raw.get("ts", "")
            ts = datetime.fromisoformat(ts_raw)
            return cls(
                reading_id=str(raw.get("reading_id", "")),
                value=float(raw.get("value", 0.0)),
                ts=ts,
                tags=list(raw.get("tags", []))
            )
        except Exception:
            return None


class Sensor:
    def __init__(self, sensor_id: str, location: str) -> None:
        self.sensor_id = sensor_id
        self.location = location
        self.readings: List[Reading] = []

    def add_reading(self, r: Reading) -> None:
        self.readings.append(r)

    def recent(self, hours: int = 24) -> List[Reading]:
        return [r for r in self.readings if r.is_recent(hours)]

    def filter_by_tag(self, tag: str) -> List[Reading]:
        return [r for r in self.readings if tag.lower() in (t.lower() for t in r.tags)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "location": self.location,
            "readings": [r.to_dict() for r in self.readings]
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Sensor"]:
        try:
            s = cls(
                sensor_id=str(raw.get("sensor_id", "")),
                location=str(raw.get("location", ""))
            )
            for r_raw in raw.get("readings", []):
                r = Reading.from_dict(r_raw)
                if r:
                    s.add_reading(r)
            return s
        except Exception:
            return None


class SyncClient:
    def __init__(self, base_url: str, timeout: int = 4) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, sensor_id: str) -> str:
        return f"{self.base_url}/sensors/{sensor_id}"

    def fetch_remote(self, sensor_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(sensor_id)
        try:
            # simulated http request
            body = json.dumps({"sensor_id": sensor_id, "location": "remote"}).encode("utf-8")
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None


def load_sensors(path: Path) -> Dict[str, Sensor]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    result: Dict[str, Sensor] = {}
    for k, v in data.items():
        s = Sensor.from_dict(v)
        if s:
            result[k] = s
    return result


def save_sensors(path: Path, sensors: Dict[str, Sensor]) -> None:
    payload = {k: v.to_dict() for k, v in sensors.items()}
    tmp = path.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def merge_sensor(local: Sensor, remote: Sensor) -> Sensor:
    merged = Sensor(local.sensor_id, local.location or remote.location)
    merged.readings = local.readings + remote.readings
    return merged


def summarize(sens: Iterable[Sensor]) -> Dict[str, Any]:
    items = list(sens)
    if not items:
        return {"count": 0, "avg_readings": 0.0}
    rcounts = [len(s.readings) for s in items]
    return {"count": len(items), "avg_readings": sum(rcounts) / len(items)}


def pick_random_recent(sensor: Sensor) -> Optional[Reading]:
    cands = sensor.recent(24)
    if not cands:
        return None
    return random.choice(cands)


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    sensors_path = base / "sensors.json"
    sensors = load_sensors(sensors_path)

    client = SyncClient(base_url)
    for sid, s in list(sensors.items()):
        rdata = client.fetch_remote(sid)
        if rdata:
            r = Sensor.from_dict(rdata)
            if r:
                sensors[sid] = merge_sensor(s, r)

    save_sensors(sensors_path, sensors)

    report = summarize(sensors.values())
    report_path = base / "summary.json"
    try:
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f)
    except Exception:
        return 1

    return 0
