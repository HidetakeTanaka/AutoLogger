import json
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional
from urllib import request, error


class Note:
    def __init__(
        self,
        note_id: str,
        title: str,
        content: str,
        created: datetime,
        tags: Iterable[str],
    ) -> None:
        self.note_id = note_id
        self.title = title
        self.content = content
        self.created = created
        self.tags = list(tags)

    def is_recent(self, days: int = 7) -> bool:
        if days <= 0:
            return False
        return self.created >= datetime.utcnow() - timedelta(days=days)

    def matches_query(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.title.lower():
            return True
        if q in self.content.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note_id": self.note_id,
            "title": self.title,
            "content": self.content,
            "created": self.created.isoformat(),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Note"]:
        try:
            created_raw = str(raw.get("created", ""))
            created = (
                datetime.fromisoformat(created_raw)
                if created_raw
                else datetime.utcnow()
            )
            return cls(
                note_id=str(raw.get("note_id", "")),
                title=str(raw.get("title", "")),
                content=str(raw.get("content", "")),
                created=created,
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None


class Notebook:
    def __init__(self, notebook_id: str, owner: str) -> None:
        self.notebook_id = notebook_id
        self.owner = owner
        self._notes: Dict[str, Note] = {}

    def add(self, note: Note) -> None:
        self._notes[note.note_id] = note

    def get(self, note_id: str) -> Optional[Note]:
        return self._notes.get(note_id)

    def all(self) -> List[Note]:
        return list(self._notes.values())

    def search(self, query: str = "", recent_days: Optional[int] = None) -> List[Note]:
        items: List[Note] = []
        for note in self._notes.values():
            if not note.matches_query(query):
                continue
            if recent_days is not None and not note.is_recent(recent_days):
                continue
            items.append(note)
        return items

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notebook_id": self.notebook_id,
            "owner": self.owner,
            "notes": [n.to_dict() for n in self._notes.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Notebook":
        nb = cls(
            notebook_id=str(raw.get("notebook_id", "")),
            owner=str(raw.get("owner", "")),
        )
        for item in raw.get("notes", []):
            note = Note.from_dict(item)
            if note is not None:
                nb.add(note)
        return nb


class SyncClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def fetch_remote_notebook(self, notebook_id: str) -> Optional[Dict[str, Any]]:
        if not self.base_url:
            return None
        url = self._url(f"notebooks/{notebook_id}")
        try:
            with request.urlopen(url, timeout=self.timeout) as resp:
                body = resp.read()
        except error.URLError:
            return None
        except Exception:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None

    def push_notebook(self, payload: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        data = json.dumps(payload).encode("utf-8")
        url = self._url("notebooks")
        req = request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                code = resp.getcode()
        except Exception:
            return False
        return 200 <= code < 300


def load_notebook(path: Path) -> Notebook:
    if not path.exists():
        return Notebook(notebook_id="local", owner="unknown")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return Notebook.from_dict(data)
    except Exception:
        return Notebook(notebook_id="local", owner="unknown")


def save_notebook(path: Path, notebook: Notebook) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = notebook.to_dict()
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def summarize_tags(notes: Iterable[Note]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for note in notes:
        seen: set[str] = set()
        for tag in note.tags:
            t = tag.strip().lower()
            if not t or t in seen:
                continue
            seen.add(t)
            counts[t] = counts.get(t, 0) + 1
    return counts


def merge_notebooks(local: Notebook, remote: Notebook) -> Notebook:
    result = Notebook(notebook_id=local.notebook_id, owner=local.owner or remote.owner)
    for note in remote.all():
        result.add(note)
    for note in local.all():
        if result.get(note.note_id) is None:
            result.add(note)
    return result


def pick_random_note(notebook: Notebook, only_recent: bool = False) -> Optional[Note]:
    candidates = notebook.all()
    if only_recent:
        candidates = [n for n in candidates if n.is_recent(14)]
    if not candidates:
        return None
    idx = random.randrange(len(candidates))
    return candidates[idx]


def main(base_dir: str = "data", base_url: str = "") -> int:
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / "notebook.json"

    local_nb = load_notebook(path)
    client = SyncClient(base_url=base_url, timeout=5)

    remote_data = client.fetch_remote_notebook(local_nb.notebook_id)
    if remote_data is None and not local_nb.all():
        now = datetime.utcnow()
        sample = Note(
            note_id="welcome",
            title="Welcome",
            content="Start writing your notes here.",
            created=now,
            tags=["info", "getting-started"],
        )
        local_nb.add(sample)
    elif remote_data is not None:
        remote_nb = Notebook.from_dict(remote_data)
        local_nb = merge_notebooks(local_nb, remote_nb)

    tags_summary = summarize_tags(local_nb.all())
    picked = pick_random_note(local_nb, only_recent=True)

    report = {
        "notebook_id": local_nb.notebook_id,
        "owner": local_nb.owner,
        "note_count": len(local_nb.all()),
        "tags": tags_summary,
        "picked_note_id": picked.note_id if picked else None,
    }

    save_notebook(path, local_nb)
    client.push_notebook(report)

    if not local_nb.all():
        return 1
    if picked is None:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
