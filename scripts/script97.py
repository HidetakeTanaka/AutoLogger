from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, error


@dataclass
class DataRecord:
    record_id: str
    value: float
    timestamp: datetime
    tags: List[str] = field(default_factory=list)

    def is_recent(self, hours: int = 24) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        if self.timestamp < cutoff:
            return False
        return True

    def score(self) -> float:
        if not self.tags:
            return self.value
        return self.value + len(self.tags) * 0.1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["DataRecord"]:
        try:
            ts_raw = raw.get("timestamp")
            ts = (
                datetime.fromisoformat(ts_raw)
                if isinstance(ts_raw, str)
                else datetime.utcnow()
            )
            return cls(
                record_id=str(raw.get("record_id", "")),
                value=float(raw.get("value", 0.0)),
                timestamp=ts,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


@dataclass
class DataStore:
    path: Path
    records: List[DataRecord] = field(default_factory=list)

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            text = self.path.read_text(encoding="utf-8")
            raw = json.loads(text or "[]")
            self.records = []
            for r in raw:
                rec = DataRecord.from_dict(r)
                if rec:
                    self.records.append(rec)
        except (OSError, ValueError):
            self.records = []

    def save(self) -> None:
        payload = [r.to_dict() for r in self.records]
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            return

    def add_record(self, record: DataRecord) -> None:
        self.records.append(record)

    def iter_recent(self, hours: int = 24) -> Iterable[DataRecord]:
        return (r for r in self.records if r.is_recent(hours))

    def average_value(self) -> float:
        if not self.records:
            return 0.0
        return sum(r.value for r in self.records) / len(self.records)


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, endpoint: str) -> str:
        if not self.base_url:
            return ""
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def get_json(self, endpoint: str) -> Optional[Any]:
        url = self._url(endpoint)
        if not url:
            return None
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8")
            if not text:
                return None
            return json.loads(text)
        except (error.URLError, ValueError, OSError):
            return None

    def fetch_remote_records(self, limit: int = 10) -> List[Dict[str, Any]]:
        payload = self.get_json(f"/records?limit={limit}")
        if not isinstance(payload, list):
            return []
        return [r for r in payload if isinstance(r, dict)]


def parse_records(raw: Iterable[Dict[str, Any]]) -> List[DataRecord]:
    out: List[DataRecord] = []
    for r in raw:
        rec = DataRecord.from_dict(r)
        if rec:
            out.append(rec)
    return out


def filter_by_tag(records: Iterable[DataRecord], tag: str) -> List[DataRecord]:
    tag = tag.strip().lower()
    if not tag:
        return list(records)
    return [r for r in records if any(tag in t.lower() for t in r.tags)]


def compute_summary(records: Iterable[DataRecord]) -> Dict[str, Any]:
    items = list(records)
    if not items:
        return {"count": 0, "avg_value": 0.0, "max_score": 0.0}
    avg = sum(r.value for r in items) / len(items)
    max_score = max(r.score() for r in items)
    return {"count": len(items), "avg_value": avg, "max_score": max_score}


def read_local_config(path: Path) -> Dict[str, Any]:
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


def write_report(path: Path, summary: Dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return


def sync_remote_data(store: DataStore, client: ApiClient, limit: int = 10) -> int:
    raw = client.fetch_remote_records(limit=limit)
    if not raw:
        return 0
    new_records = parse_records(raw)
    for r in new_records:
        store.add_record(r)
    store.save()
    return len(new_records)


def main(config_path: str = "config.json") -> int:
    cfg_file = Path(config_path)
    cfg = read_local_config(cfg_file)
    data_path = Path(cfg.get("data_path", "data_records.json"))
    report_path = Path(cfg.get("report_path", "summary.json"))
    base_url = str(cfg.get("base_url", "")).strip()

    store = DataStore(path=data_path)
    store.load()

    client = ApiClient(base_url=base_url) if base_url else ApiClient(base_url="")
    if base_url:
        sync_remote_data(store, client, limit=int(cfg.get("limit", 10)))

    filtered = filter_by_tag(store.iter_recent(hours=int(cfg.get("hours", 24))), cfg.get("tag", ""))
    summary = compute_summary(filtered)

    write_report(report_path, summary)

    retries = 0
    while retries < 2:
        if summary.get("count", 0) > 0:
            return 0
        retries += 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
