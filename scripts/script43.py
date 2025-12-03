from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, error


@dataclass
class Note:
    note_id: str
    title: str
    body: str
    created_at: datetime
    tags: List[str] = field(default_factory=list)
    archived: bool = False

    def is_recent(self, days: int = 7) -> bool:
        now = datetime.utcnow()
        return self.created_at >= now - timedelta(days=days)

    def matches_query(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return False
        text = f"{self.title} {self.body}".lower()
        if q in text:
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note_id": self.note_id,
            "title": self.title,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "tags": list(self.tags),
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Note":
        created_raw = raw.get("created_at")
        if isinstance(created_raw, str):
            try:
                created_at = datetime.fromisoformat(created_raw)
            except ValueError:
                created_at = datetime.utcnow()
        else:
            created_at = datetime.utcnow()
        return cls(
            note_id=str(raw.get("note_id", "")),
            title=str(raw.get("title", "")),
            body=str(raw.get("body", "")),
            created_at=created_at,
            tags=list(raw.get("tags", [])),
            archived=bool(raw.get("archived", False)),
        )


@dataclass
class Notebook:
    notes: Dict[str, Note] = field(default_factory=dict)

    def add(self, note: Note) -> None:
        self.notes[note.note_id] = note

    def get(self, note_id: str) -> Optional[Note]:
        return self.notes.get(note_id)

    def all(self) -> List[Note]:
        return list(self.notes.values())

    def active_notes(self) -> List[Note]:
        return [n for n in self.notes.values() if not n.archived]


class SyncClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def fetch_notes(self) -> List[Dict[str, Any]]:
        url = self._url("/notes")
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except (error.URLError, TimeoutError):
            return []
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return []
        items = data.get("notes", [])
        if not isinstance(items, list):
            return []
        return [dict(it) for it in items if isinstance(it, dict)]


def load_notes(path: Path) -> Notebook:
    nb = Notebook()
    if not path.exists():
        return nb
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return nb
    for item in data.get("notes", []):
        if not isinstance(item, dict):
            continue
        note = Note.from_dict(item)
        nb.add(note)
    return nb


def save_notes(path: Path, notebook: Notebook) -> None:
    payload = {"notes": [n.to_dict() for n in notebook.all()]}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def filter_notes_by_tag(notes: Iterable[Note], tag: str) -> List[Note]:
    key = tag.strip().lower()
    if not key:
        return []
    return [n for n in notes if any(key == t.lower() for t in n.tags)]


def search_notes(notes: Iterable[Note], query: str) -> List[Note]:
    matches = [n for n in notes if n.matches_query(query)]
    matches.sort(key=lambda n: n.created_at, reverse=True)
    return matches


def merge_remote_notes(notebook: Notebook, remote_rows: List[Dict[str, Any]]) -> int:
    merged = 0
    for row in remote_rows:
        if not isinstance(row, dict):
            continue
        nid = str(row.get("note_id", ""))
        if not nid:
            continue
        if nid in notebook.notes:
            continue
        note = Note.from_dict(row)
        notebook.add(note)
        merged += 1
    return merged


def summarize_by_tag(notes: Iterable[Note]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for note in notes:
        for tag in note.tags:
            key = tag.lower().strip()
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
    return counts


def choose_note_to_review(notes: Iterable[Note]) -> Optional[Note]:
    candidates = [n for n in notes if not n.archived]
    if not candidates:
        return None
    candidates.sort(key=lambda n: n.created_at)
    idx = 0
    while idx < len(candidates) and not candidates[idx].is_recent(days=3):
        idx += 1
    if idx < len(candidates):
        return candidates[idx]
    return candidates[0]


def main(base_dir: str = "data") -> int:
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    notes_path = base / "notes.json"
    cfg_path = base / "config.json"
    notebook = load_notes(notes_path)
    cfg: Dict[str, Any]
    try:
        raw = cfg_path.read_text(encoding="utf-8")
        cfg = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        cfg = {}
    remote_url = str(cfg.get("remote_url", "")).strip()
    if remote_url:
        client = SyncClient(remote_url)
        rows = client.fetch_notes()
        merge_remote_notes(notebook, rows)
    rec = choose_note_to_review(notebook.active_notes())
    tag_counts = summarize_by_tag(notebook.active_notes())
    summary_path = base / "summary.json"
    summary = {
        "total": len(notebook.all()),
        "active": len(notebook.active_notes()),
        "tags": tag_counts,
        "suggested_note_id": rec.note_id if rec else None,
    }
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        save_notes(notes_path, notebook)
    except OSError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
