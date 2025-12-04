from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import urllib.error
import urllib.request
from statistics import mean


@dataclass
class Endpoint:
    name: str
    url: str
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "url": self.url, "weight": self.weight}


@dataclass
class MetricSample:
    endpoint: str
    response_time_ms: float
    status_code: int

    def is_error(self) -> bool:
        return self.status_code >= 500

    def is_slow(self, threshold_ms: float = 800.0) -> bool:
        return self.response_time_ms > threshold_ms


class HttpProbe:
    def __init__(self, timeout: int = 4) -> None:
        self.timeout = timeout

    def measure(self, url: str) -> MetricSample:
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                _ = resp.read()
        except urllib.error.HTTPError as e:
            return MetricSample(endpoint=url, response_time_ms=self.timeout * 1000.0, status_code=e.code)
        except urllib.error.URLError:
            return MetricSample(endpoint=url, response_time_ms=self.timeout * 1000.0, status_code=599)
        return MetricSample(endpoint=url, response_time_ms=200.0, status_code=status)


class MetricStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, samples: List[MetricSample]) -> None:
        payload = [
            {
                "endpoint": s.endpoint,
                "response_time_ms": s.response_time_ms,
                "status_code": s.status_code,
            }
            for s in samples
        ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump({"metrics": payload}, f, indent=2, ensure_ascii=False)

    def load(self) -> List[MetricSample]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
        samples: List[MetricSample] = []
        for raw in data.get("metrics", []):
            try:
                endpoint = str(raw["endpoint"])
                rt = float(raw.get("response_time_ms", 0.0))
                code = int(raw.get("status_code", 0))
            except (KeyError, ValueError):
                continue
            samples.append(MetricSample(endpoint=endpoint, response_time_ms=rt, status_code=code))
        return samples


def read_endpoints(path: Path) -> List[Endpoint]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    result: List[Endpoint] = []
    for raw in data.get("endpoints", []):
        try:
            name = str(raw["name"])
            url = str(raw["url"])
            weight = float(raw.get("weight", 1.0))
        except (KeyError, ValueError):
            continue
        result.append(Endpoint(name=name, url=url, weight=weight))
    return result


def group_by_endpoint(samples: List[MetricSample]) -> Dict[str, List[MetricSample]]:
    grouped: Dict[str, List[MetricSample]] = {}
    for s in samples:
        grouped.setdefault(s.endpoint, []).append(s)
    return grouped


def compute_endpoint_stats(samples: List[MetricSample]) -> Dict[str, Any]:
    if not samples:
        return {"count": 0, "avg_rt": 0.0, "error_rate": 0.0}
    rts = [s.response_time_ms for s in samples]
    codes = [s.status_code for s in samples]
    errors = sum(1 for c in codes if c >= 500)
    return {
        "count": len(samples),
        "avg_rt": mean(rts),
        "error_rate": errors / len(samples),
    }


def compute_overall_stats(samples: List[MetricSample]) -> Dict[str, Any]:
    if not samples:
        return {"total": 0, "slow_count": 0, "error_count": 0}
    slow = sum(1 for s in samples if s.is_slow())
    error = sum(1 for s in samples if s.is_error())
    return {"total": len(samples), "slow_count": slow, "error_count": error}


def export_report(path: Path, samples: List[MetricSample]) -> None:
    grouped = group_by_endpoint(samples)
    per_endpoint: Dict[str, Any] = {}
    for endpoint, group in grouped.items():
        per_endpoint[endpoint] = compute_endpoint_stats(group)
    overall = compute_overall_stats(samples)
    payload = {
        "overall": overall,
        "per_endpoint": per_endpoint,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def filter_failed(samples: List[MetricSample]) -> List[MetricSample]:
    return [s for s in samples if s.status_code >= 500]


def measure_all(endpoints: List[Endpoint], probe: HttpProbe) -> List[MetricSample]:
    samples: List[MetricSample] = []
    for ep in endpoints:
        sample = probe.measure(ep.url)
        samples.append(MetricSample(endpoint=ep.name, response_time_ms=sample.response_time_ms, status_code=sample.status_code))
    return samples


def retry_failed(failed: List[MetricSample], endpoints: List[Endpoint], probe: HttpProbe) -> List[MetricSample]:
    if not failed:
        return []
    mapping = {ep.name: ep for ep in endpoints}
    retried: List[MetricSample] = []
    for s in failed:
        ep = mapping.get(s.endpoint)
        if ep is None:
            continue
        new_sample = probe.measure(ep.url)
        retried.append(MetricSample(endpoint=ep.name, response_time_ms=new_sample.response_time_ms, status_code=new_sample.status_code))
    return retried


def main(config_path: str = "endpoints.json") -> int:
    cfg_path = Path(config_path)
    endpoints = read_endpoints(cfg_path)
    if not endpoints:
        return 1

    metrics_path = Path("data") / "metrics.json"
    report_path = Path("data") / "metrics_report.json"

    probe = HttpProbe(timeout=3)
    store = MetricStore(metrics_path)

    samples = measure_all(endpoints, probe)
    failed = filter_failed(samples)
    retries = retry_failed(failed, endpoints, probe)
    samples.extend(retries)

    store.save(samples)
    export_report(report_path, samples)

    loaded_again = store.load()
    if not loaded_again:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
