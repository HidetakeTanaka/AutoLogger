from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import random
import urllib.request
import urllib.error

@dataclass
class Book:
    book_id: str
    title: str
    author: str
    pages: int
    added_at: datetime
    finished_pages: int = 0
    tags: List[str] = field(default_factory=list)

    def is_finished(self) -> bool:
        if self.pages <= 0:
            return False
        return self.finished_pages >= self.pages

    def progress(self) -> float:
        if self.pages <= 0:
            return 0.0
        return min(1.0, self.finished_pages / self.pages)

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.title.lower() or q in self.author.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "pages": self.pages,
            "added_at": self.added_at.isoformat(),
            "finished_pages": self.finished_pages,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Book"]:
        try:
            added_raw = str(raw.get("added_at", ""))
            added = datetime.fromisoformat(added_raw) if added_raw else datetime.utcnow()
            return cls(
                book_id=str(raw.get("book_id", "")),
                title=str(raw.get("title", "")),
                author=str(raw.get("author", "")),
                pages=int(raw.get("pages", 0)),
                added_at=added,
                finished_pages=int(raw.get("finished_pages", 0)),
                tags=list(raw.get("tags", [])),
            )
        except Exception:
            return None

@dataclass
class UserLibrary:
    user_id: str
    books: Dict[str, Book] = field(default_factory=dict)

    def add_book(self, book: Book) -> None:
        self.books[book.book_id] = book

    def get_book(self, book_id: str) -> Optional[Book]:
        return self.books.get(book_id)

    def search(self, query: str = "") -> List[Book]:
        return [b for b in self.books.values() if b.matches(query)]

    def finished_books(self) -> List[Book]:
        return [b for b in self.books.values() if b.is_finished()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "books": [b.to_dict() for b in self.books.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "UserLibrary":
        lib = cls(user_id=str(raw.get("user_id", "anonymous")))
        for b_raw in raw.get("books", []):
            book = Book.from_dict(b_raw)
            if book is not None:
                lib.add_book(book)
        return lib

class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, user_id: str) -> str:
        return f"{self.base_url}/users/{user_id}/recommendations.json"

    def fetch_recommendations(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        if not self.base_url:
            return None
        url = self._url(user_id)
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            parsed = json.loads(data.decode("utf-8"))
            if not isinstance(parsed, list):
                return None
            return parsed
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None

def load_library(path: Path) -> UserLibrary:
    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return UserLibrary.from_dict(raw)
    except FileNotFoundError:
        return UserLibrary(user_id="local")
    except Exception:
        return UserLibrary(user_id="local")

def save_library(path: Path, lib: UserLibrary) -> None:
    payload = json.dumps(lib.to_dict(), indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(payload)
        tmp.replace(path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass

def compute_stats(lib: UserLibrary) -> Dict[str, Any]:
    books = list(lib.books.values())
    if not books:
        return {"count": 0, "finished": 0, "avg_progress": 0.0}
    finished = sum(1 for b in books if b.is_finished())
    avg = sum(b.progress() for b in books) / len(books)
    return {"count": len(books), "finished": finished, "avg_progress": avg}

def simulate_reading(lib: UserLibrary, sessions: int = 5) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    if not lib.books or sessions <= 0:
        return history
    keys = list(lib.books.keys())
    step = 0
    while step < sessions:
        book_id = random.choice(keys)
        book = lib.books[book_id]
        delta = random.randint(5, 30)
        before = book.finished_pages
        book.finished_pages = min(book.pages, book.finished_pages + delta)
        history.append(
            {
                "book_id": book.book_id,
                "delta": delta,
                "before": before,
                "after": book.finished_pages,
            }
        )
        step += 1
    return history

def apply_recommendations(lib: UserLibrary, recs: Optional[List[Dict[str, Any]]]) -> int:
    if not recs:
        return 0
    added = 0
    for r in recs:
        book = Book.from_dict(r)
        if book is None:
            continue
        if book.book_id in lib.books:
            continue
        lib.add_book(book)
        added += 1
    return added

def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    lib_path = base / "library.json"
    summary_path = base / "summary.json"
    try:
        lib = load_library(lib_path)
        client = RecommendationClient(base_url=base_url) if base_url else None
        recs = None
        if client is not None:
            recs = client.fetch_recommendations(lib.user_id)
        apply_recommendations(lib, recs)
        simulate_reading(lib, sessions=5)
        summary = compute_stats(lib)
        save_library(lib_path, lib)
        try:
            with summary_path.open("w", encoding="utf-8") as fh:
                json.dump(summary, fh, indent=2)
        except Exception:
            return 1
    except Exception:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
