from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass
class MetricSample:
    timestamp: datetime
    latency_ms: float
    ok: bool

    def is_recent(self, minutes: int = 5) -> bool:
        ref = datetime.utcnow() - timedelta(minutes=minutes)
        if self.timestamp < ref:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": self.latency_ms,
            "ok": self.ok,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["MetricSample"]:
        try:
            ts_raw = raw.get("timestamp")
            ts = datetime.fromisoformat(ts_raw)
            return cls(
                timestamp=ts,
                latency_ms=float(raw.get("latency_ms", 0.0)),
                ok=bool(raw.get("ok", False)),
            )
        except Exception:
            return None


@dataclass
class ServiceStatus:
    service_id: str
    url: str
    samples: List[MetricSample] = field(default_factory=list)

    def add_sample(self, sample: MetricSample) -> None:
        self.samples.append(sample)

    def recent_samples(self, minutes: int = 5) -> List[MetricSample]:
        return [s for s in self.samples if s.is_recent(minutes)]

    def availability(self, minutes: int = 60) -> float:
        recents = self.recent_samples(minutes)
        if not recents:
            return 0.0
        oks = sum(1 for s in recents if s.ok)
        return oks / len(recents)

    def avg_latency(self, minutes: int = 60) -> float:
        recents = self.recent_samples(minutes)
        if not recents:
            return 0.0
        return sum(s.latency_ms for s in recents) / len(recents)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "url": self.url,
            "samples": [s.to_dict() for s in self.samples],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ServiceStatus":
        svc = cls(service_id=str(raw.get("service_id", "")), url=str(raw.get("url", "")))
        for r in raw.get("samples", []):
            s = MetricSample.from_dict(r)
            if s is not None:
                svc.add_sample(s)
        return svc


class HealthClient:
    def __init__(self, timeout: int = 5) -> None:
        self.timeout = timeout

    def check(self, url: str) -> MetricSample:
        start = time.time()
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=self.timeout) as resp:
                _ = resp.read(128)
            latency = (time.time() - start) * 1000.0
            return MetricSample(datetime.utcnow(), latency, True)
        except URLError:
            latency = (time.time() - start) * 1000.0
            return MetricSample(datetime.utcnow(), latency, False)
        except Exception:
            latency = (time.time() - start) * 1000.0
            return MetricSample(datetime.utcnow(), latency, False)


def load_statuses(path: Path) -> List[ServiceStatus]:
    if not path.exists():
        return []
    try:
        data = path.read_text(encoding="utf-8")
        raw = json.loads(data)
        return [ServiceStatus.from_dict(r) for r in raw]
    except Exception:
        return []


def save_statuses(path: Path, statuses: List[ServiceStatus]) -> None:
    payload = [s.to_dict() for s in statuses]
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def summarize_statuses(statuses: List[ServiceStatus]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for s in statuses:
        result.append(
            {
                "service_id": s.service_id,
                "availability_1h": s.availability(60),
                "avg_latency_1h": s.avg_latency(60),
                "samples": len(s.samples),
            }
        )
    return result


def detect_incidents(statuses: List[ServiceStatus], avail_threshold: float = 0.95) -> List[str]:
    incidents: List[str] = []
    for s in statuses:
        avail = s.availability(15)
        if avail == 0.0:
            incidents.append(f"{s.service_id}: no recent data")
        elif avail < avail_threshold:
            incidents.append(f"{s.service_id}: low availability {avail:.2%}")
    return incidents


def simulate_checks(statuses: List[ServiceStatus], rounds: int = 3) -> None:
    now = datetime.utcnow()
    for _ in range(rounds):
        for s in statuses:
            # synthetic jitter
            latency = random.uniform(50, 400)
            ok = random.random() > 0.1
            sample = MetricSample(timestamp=now, latency_ms=latency, ok=ok)
            s.add_sample(sample)
        now += timedelta(minutes=5)


def ensure_services(statuses: List[ServiceStatus], targets: Dict[str, str]) -> List[ServiceStatus]:
    index = {s.service_id: s for s in statuses}
    for sid, url in targets.items():
        if sid not in index:
            index[sid] = ServiceStatus(service_id=sid, url=url)
    return list(index.values())


def main(data_dir: str = "data", run_live: bool = False) -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    store_path = base / "services.json"
    statuses = load_statuses(store_path)

    targets = {
        "search": "https://example.com",
        "api": "https://example.com/api",
        "auth": "https://example.com/login",
    }
    statuses = ensure_services(statuses, targets)

    if run_live:
        client = HealthClient()
        for s in statuses:
            sample = client.check(s.url)
            s.add_sample(sample)
    else:
        simulate_checks(statuses, rounds=4)

    summary = summarize_statuses(statuses)
    incidents = detect_incidents(statuses)

    output_path = base / "summary.json"
    try:
        output_path.write_text(json.dumps({"summary": summary, "incidents": incidents}, indent=2), encoding="utf-8")
    except Exception:
        return 1

    save_statuses(store_path, statuses)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
