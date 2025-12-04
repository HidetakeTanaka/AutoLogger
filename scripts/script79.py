from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Book:
    book_id: str
    title: str
    author: str
    pages: int
    tags: List[str] = field(default_factory=list)
    added_at: datetime = field(default_factory=datetime.utcnow)
    read: bool = False

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.title.lower() or q in self.author.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def is_long(self, threshold: int = 300) -> bool:
        if self.pages <= 0:
            return False
        return self.pages >= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "pages": self.pages,
            "tags": list(self.tags),
            "added_at": self.added_at.isoformat(),
            "read": self.read,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Book"]:
        try:
            ts_raw = raw.get("added_at")
            added = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            return cls(
                book_id=str(raw.get("book_id", "")),
                title=str(raw.get("title", "")),
                author=str(raw.get("author", "")),
                pages=int(raw.get("pages", 0)),
                tags=list(raw.get("tags", [])),
                added_at=added,
                read=bool(raw.get("read", False)),
            )
        except Exception:
            return None


@dataclass
class LibraryState:
    user_id: str
    books: Dict[str, Book] = field(default_factory=dict)

    def add_book(self, book: Book) -> None:
        if not book.book_id:
            book.book_id = f"b-{len(self.books) + 1}"
        self.books[book.book_id] = book

    def mark_read(self, book_id: str) -> bool:
        book = self.books.get(book_id)
        if not book:
            return False
        if book.read:
            return False
        book.read = True
        return True

    def search(self, query: str = "") -> List[Book]:
        return [b for b in self.books.values() if b.matches(query)]

    def recommendations_local(self, max_items: int = 5) -> List[Book]:
        unread = [b for b in self.books.values() if not b.read]
        if not unread:
            return []
        random.shuffle(unread)
        return unread[:max_items]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "books": [b.to_dict() for b in self.books.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "LibraryState":
        lib = cls(user_id=str(raw.get("user_id", "local")))
        for item in raw.get("books", []):
            b = Book.from_dict(item)
            if b is not None:
                lib.add_book(b)
        return lib


class RecommendationClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, topic: str) -> str:
        return f"{self.base_url}/recommend?topic={topic}"

    def fetch_recommendations(self, topic: str) -> Optional[List[Dict[str, Any]]]:
        if not self.base_url:
            return None
        url = self._url(topic)
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
        except (urllib.error.URLError, TimeoutError):
            return None
        try:
            payload = json.loads(data.decode("utf-8"))
            items = payload.get("items")
            if not isinstance(items, list):
                return None
            return items
        except Exception:
            return None


def load_library(path: Path) -> LibraryState:
    if not path.exists():
        return LibraryState(user_id="local")
    try:
        raw_text = path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
        return LibraryState.from_dict(raw)
    except Exception:
        return LibraryState(user_id="local")


def save_library(path: Path, library: LibraryState) -> None:
    payload = library.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def summarize_library(library: LibraryState) -> Dict[str, Any]:
    if not library.books:
        return {"count": 0, "read": 0, "long_books": 0}
    books = list(library.books.values())
    read_count = sum(1 for b in books if b.read)
    long_count = sum(1 for b in books if b.is_long())
    return {"count": len(books), "read": read_count, "long_books": long_count}


def simulate_reading(library: LibraryState, days: int = 3) -> int:
    if days <= 0:
        return 0
    read_total = 0
    day = 0
    while day < days:
        candidates = library.recommendations_local(max_items=2)
        for book in candidates:
            if not book.read and random.random() < 0.7:
                if library.mark_read(book.book_id):
                    read_total += 1
        day += 1
    return read_total


def pick_random_book(library: LibraryState, unread_only: bool = True) -> Optional[Book]:
    if not library.books:
        return None
    candidates = [b for b in library.books.values() if not b.read] if unread_only else list(library.books.values())
    if not candidates:
        return None
    return random.choice(candidates)


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    lib_path = base / "library.json"
    summary_path = base / "summary.json"

    library = load_library(lib_path)
    if not library.books:
        library.add_book(Book(book_id="1", title="Sample Book", author="Anon", pages=250))
        library.add_book(Book(book_id="2", title="Deep Learning", author="Scholar", pages=800, tags=["ai", "ml"]))

    try:
        client = RecommendationClient(base_url=base_url, timeout=5)
        recs = client.fetch_recommendations("technology")
        if recs:
            for rec in recs[:3]:
                title = str(rec.get("title", ""))
                author = str(rec.get("author", "Unknown"))
                bid = str(rec.get("id", f"r-{random.randint(100, 999)}"))
                pages = int(rec.get("pages", random.randint(150, 400)))
                tags = list(rec.get("tags", ["remote"]))
                if bid not in library.books:
                    library.add_book(Book(book_id=bid, title=title, author=author, pages=pages, tags=tags))
        simulate_reading(library, days=5)
        stats = summarize_library(library)
        save_library(lib_path, library)
        summary_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
