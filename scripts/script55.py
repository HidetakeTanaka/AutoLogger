from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from urllib import request, error


@dataclass
class Book:
    book_id: str
    title: str
    author: str
    published: datetime
    tags: List[str] = field(default_factory=list)
    rating: float = 0.0

    def is_recent(self, years: int = 2) -> bool:
        if years <= 0:
            return False
        return self.published >= datetime.utcnow() - timedelta(days=365 * years)

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        if q in self.title.lower():
            return True
        if q in self.author.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "published": self.published.isoformat(),
            "tags": list(self.tags),
            "rating": self.rating,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Book"]:
        try:
            published_raw = raw.get("published", "")
            published = datetime.fromisoformat(published_raw) if published_raw else datetime.utcnow()
            return cls(
                book_id=str(raw.get("book_id", "")),
                title=str(raw.get("title", "")),
                author=str(raw.get("author", "")),
                published=published,
                tags=list(raw.get("tags", [])),
                rating=float(raw.get("rating", 0.0)),
            )
        except Exception:
            return None


class Library:
    def __init__(self, library_id: str, name: str) -> None:
        self.library_id = library_id
        self.name = name
        self._books: Dict[str, Book] = {}

    def add(self, book: Book) -> None:
        self._books[book.book_id] = book

    def get(self, book_id: str) -> Optional[Book]:
        return self._books.get(book_id)

    def all(self) -> List[Book]:
        return list(self._books.values())

    def search(self, query: str = "") -> List[Book]:
        items = [b for b in self._books.values() if b.matches(query)]
        return sorted(items, key=lambda b: b.title.lower())

    def recent(self, years: int = 2) -> List[Book]:
        return [b for b in self._books.values() if b.is_recent(years)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "library_id": self.library_id,
            "name": self.name,
            "books": [b.to_dict() for b in self._books.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Library":
        lib = cls(library_id=str(raw.get("library_id", "local")), name=str(raw.get("name", "Local Library")))
        for item in raw.get("books", []):
            book = Book.from_dict(item)
            if book:
                lib.add(book)
        return lib


class LibraryClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, library_id: str) -> str:
        return f"{self.base_url}/libraries/{library_id}.json"

    def fetch_remote(self, library_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(library_id)
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
            return json.loads(body.decode("utf-8"))
        except (error.URLError, ValueError, OSError):
            return None


def load_library(path: Path) -> Library:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Library.from_dict(data)
    except FileNotFoundError:
        return Library(library_id="local", name="Local Library")
    except Exception:
        return Library(library_id="local", name="Local Library")


def save_library(path: Path, lib: Library) -> None:
    payload = json.dumps(lib.to_dict(), indent=2)
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


def summarize_library(lib: Library) -> Dict[str, Any]:
    books = lib.all()
    if not books:
        return {"count": 0, "avg_rating": 0.0, "recent": 0}
    total_rating = sum(b.rating for b in books)
    recent = sum(1 for b in books if b.is_recent())
    return {
        "count": len(books),
        "avg_rating": total_rating / len(books),
        "recent": recent,
    }


def filter_books(lib: Library, min_rating: float = 0.0, recent_only: bool = False) -> List[Book]:
    result: List[Book] = []
    for b in lib.all():
        if b.rating < min_rating:
            continue
        if recent_only and not b.is_recent():
            continue
        result.append(b)
    return result


def pick_random_book(lib: Library, prefer_recent: bool = False) -> Optional[Book]:
    books = lib.all()
    if not books:
        return None
    if prefer_recent:
        recent = [b for b in books if b.is_recent()]
        if recent:
            return random.choice(recent)
    return random.choice(books)


def merge_remote_library(local: Library, remote_data: Optional[Dict[str, Any]]) -> int:
    if not remote_data:
        return 0
    remote = Library.from_dict(remote_data)
    added = 0
    for book in remote.all():
        if local.get(book.book_id) is None:
            local.add(book)
            added += 1
    return added


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    lib_path = base / "library.json"
    lib = load_library(lib_path)

    if base_url:
        client = LibraryClient(base_url=base_url)
        remote_data = client.fetch_remote(lib.library_id)
        merge_remote_library(lib, remote_data)

    summary = summarize_library(lib)
    report_path = base / "library_report.json"
    try:
        report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except OSError:
        return 1

    save_library(lib_path, lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
