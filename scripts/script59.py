from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class MetricSample:
    timestamp: datetime
    value: float

    def is_recent(self, minutes: int = 10) -> bool:
        if minutes <= 0:
            return False
        return self.timestamp >= datetime.utcnow() - timedelta(minutes=minutes)


@dataclass
class Sensor:
    sensor_id: str
    kind: str
    samples: List[MetricSample] = field(default_factory=list)
    enabled: bool = True

    def add_sample(self, value: float) -> None:
        if not self.enabled:
            return
        self.samples.append(MetricSample(timestamp=datetime.utcnow(), value=value))

    def latest(self) -> Optional[MetricSample]:
        if not self.samples:
            return None
        return max(self.samples, key=lambda s: s.timestamp)

    def recent_values(self, minutes: int = 10) -> List[float]:
        return [s.value for s in self.samples if s.is_recent(minutes)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "kind": self.kind,
            "enabled": self.enabled,
            "samples": [
                {"timestamp": s.timestamp.isoformat(), "value": s.value}
                for s in self.samples
            ],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional[Sensor]:
        try:
            samples: List[MetricSample] = []
            for item in raw.get("samples", []):
                ts_raw = str(item.get("timestamp", ""))
                ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
                samples.append(MetricSample(timestamp=ts, value=float(item.get("value", 0.0))))
            return cls(
                sensor_id=str(raw.get("sensor_id", "")),
                kind=str(raw.get("kind", "")),
                samples=samples,
                enabled=bool(raw.get("enabled", True)),
            )
        except Exception:
            return None


class SensorNetwork:
    def __init__(self, network_id: str) -> None:
        self.network_id = network_id
        self._sensors: Dict[str, Sensor] = {}

    def add(self, sensor: Sensor) -> None:
        self._sensors[sensor.sensor_id] = sensor

    def get(self, sensor_id: str) -> Optional[Sensor]:
        return self._sensors.get(sensor_id)

    def all(self) -> List[Sensor]:
        return list(self._sensors.values())

    def enabled_sensors(self) -> List[Sensor]:
        return [s for s in self._sensors.values() if s.enabled]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "network_id": self.network_id,
            "sensors": [s.to_dict() for s in self._sensors.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> SensorNetwork:
        net = cls(network_id=str(raw.get("network_id", "local")))
        for item in raw.get("sensors", []):
            s = Sensor.from_dict(item)
            if s:
                net.add(s)
        return net


class MetricsClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, network_id: str) -> str:
        return f"{self.base_url}/networks/{network_id}.json"

    def fetch(self, network_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(network_id)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
            return json.loads(body.decode("utf-8"))
        except (error.URLError, OSError, ValueError):
            return None

    def push(self, network_id: str, payload: Dict[str, Any]) -> bool:
        url = self._url(network_id)
        data = json.dumps(payload).encode("utf-8")
        try:
            req = request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (error.URLError, OSError):
            return False


def load_network(path: Path) -> SensorNetwork:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return SensorNetwork.from_dict(raw)
    except FileNotFoundError:
        return SensorNetwork(network_id="local")
    except Exception:
        return SensorNetwork(network_id="local")


def save_network(path: Path, net: SensorNetwork) -> None:
    payload = json.dumps(net.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def aggregate_metrics(net: SensorNetwork) -> Dict[str, Any]:
    sensors = net.enabled_sensors()
    if not sensors:
        return {"sensor_count": 0, "avg_value": 0.0}
    values: List[float] = []
    for s in sensors:
        latest = s.latest()
        if latest:
            values.append(latest.value)
    if not values:
        return {"sensor_count": len(sensors), "avg_value": 0.0}
    avg = sum(values) / len(values)
    return {"sensor_count": len(sensors), "avg_value": avg}


def detect_anomalies(net: SensorNetwork, threshold: float = 100.0) -> List[str]:
    outliers: List[str] = []
    for s in net.enabled_sensors():
        for sample in s.samples:
            if abs(sample.value) > threshold:
                outliers.append(s.sensor_id)
                break
    return outliers


def sync_remote_metrics(net: SensorNetwork, client: MetricsClient) -> int:
    data = client.fetch(net.network_id)
    if not data:
        return 0
    remote = SensorNetwork.from_dict(data)
    added = 0
    for s in remote.all():
        if net.get(s.sensor_id) is None:
            net.add(s)
            added += 1
    return added


def simulate_network(net: SensorNetwork, rounds: int = 3) -> None:
    step = 0
    while step < rounds:
        for s in net.enabled_sensors():
            value = random.uniform(-50, 150)
            s.add_sample(value)
        step += 1


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    net_path = base / "network.json"
    report_path = base / "network_report.json"

    net = load_network(net_path)

    if base_url:
        client = MetricsClient(base_url=base_url)
        sync_remote_metrics(net, client)

    simulate_network(net)
    summary = aggregate_metrics(net)
    summary["anomalies"] = detect_anomalies(net)

    try:
        report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except OSError:
        return 1

    save_network(net_path, net)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
