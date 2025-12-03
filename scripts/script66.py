from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import random
import urllib.request
import urllib.error


@dataclass
class Reading:
    station_id: str
    timestamp: datetime
    temperature: float
    humidity: float

    def is_recent(self, minutes: int = 60) -> bool:
        ref = datetime.utcnow() - timedelta(minutes=minutes)
        return self.timestamp >= ref

    def to_dict(self) -> Dict[str, Any]:
        return {
            "station_id": self.station_id,
            "timestamp": self.timestamp.isoformat(),
            "temperature": self.temperature,
            "humidity": self.humidity,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Reading"]:
        try:
            ts_raw = raw.get("timestamp")
            if not ts_raw:
                return None
            ts = datetime.fromisoformat(ts_raw)
            return cls(
                station_id=str(raw.get("station_id", "")),
                timestamp=ts,
                temperature=float(raw.get("temperature", 0.0)),
                humidity=float(raw.get("humidity", 0.0)),
            )
        except Exception:
            return None


class Station:
    def __init__(self, station_id: str, name: str) -> None:
        self.station_id = station_id
        self.name = name
        self._readings: List[Reading] = []

    def add_reading(self, reading: Reading) -> None:
        if reading.station_id != self.station_id:
            return
        self._readings.append(reading)
        self._readings = sorted(self._readings, key=lambda r: r.timestamp)[-500:]

    def latest(self) -> Optional[Reading]:
        if not self._readings:
            return None
        return self._readings[-1]

    def average_temperature(self, recent_minutes: int = 60) -> float:
        recents = [r.temperature for r in self._readings if r.is_recent(recent_minutes)]
        if not recents:
            return 0.0
        return sum(recents) / len(recents)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "station_id": self.station_id,
            "name": self.name,
            "readings": [r.to_dict() for r in self._readings],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Station":
        station = cls(
            station_id=str(raw.get("station_id", "")),
            name=str(raw.get("name", "Unnamed")),
        )
        for r_raw in raw.get("readings", []):
            r = Reading.from_dict(r_raw)
            if r is not None:
                station.add_reading(r)
        return station


class WeatherClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, station_id: str) -> str:
        return f"{self.base_url}/stations/{station_id}.json"

    def fetch_station_data(self, station_id: str) -> Optional[Dict[str, Any]]:
        if not self.base_url:
            return None
        url = self._url(station_id)
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except (urllib.error.URLError, ValueError, TimeoutError):
            return None


def load_station(path: Path) -> Station:
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return Station.from_dict(raw)
    except Exception:
        return Station(station_id="local", name="Local Station")


def save_station(path: Path, station: Station) -> None:
    payload = json.dumps(station.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(payload)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def summarize_station(station: Station) -> Dict[str, Any]:
    latest = station.latest()
    if latest is None:
        return {"station_id": station.station_id, "name": station.name, "count": 0}
    temps = [r.temperature for r in station._readings]
    return {
        "station_id": station.station_id,
        "name": station.name,
        "count": len(station._readings),
        "avg_temp_all": sum(temps) / len(temps) if temps else 0.0,
        "avg_temp_recent": station.average_temperature(60),
        "latest_temp": latest.temperature,
    }


def merge_remote(station: Station, remote_raw: Optional[Dict[str, Any]]) -> int:
    if not remote_raw:
        return 0
    added = 0
    remote = Station.from_dict(remote_raw)
    existing_times = {r.timestamp for r in station._readings}
    for r in remote._readings:
        if r.timestamp not in existing_times:
            station.add_reading(r)
            added += 1
    return added


def simulate_station(station: Station, steps: int = 3) -> List[Reading]:
    history: List[Reading] = []
    for _ in range(steps):
        base_temp = 20.0 + random.uniform(-5, 5)
        base_hum = 50.0 + random.uniform(-20, 20)
        r = Reading(
            station_id=station.station_id,
            timestamp=datetime.utcnow(),
            temperature=base_temp,
            humidity=max(0.0, min(100.0, base_hum)),
        )
        station.add_reading(r)
        history.append(r)
    return history


def filter_hot_readings(station: Station, threshold: float = 30.0) -> List[Reading]:
    return [r for r in station._readings if r.temperature >= threshold]


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    station_path = base / "station.json"

    station = load_station(station_path)
    simulate_station(station, steps=5)

    client = WeatherClient(base_url=base_url)
    remote = client.fetch_station_data(station.station_id)
    merge_remote(station, remote)

    summary = summarize_station(station)
    summary_path = base / "summary.json"
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except Exception:
        return 1

    save_station(station_path, station)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
