from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from urllib import request, error


@dataclass
class Book:
    book_id: str
    title: str
    author: str
    year: int
    tags: List[str] = field(default_factory=list)
    available: bool = True

    def is_recent(self, years: int = 5) -> bool:
        current_year = datetime.utcnow().year
        return self.year >= current_year - years

    def matches_query(self, query: str) -> bool:
        q = query.lower().strip()
        if not q:
            return False
        if q in self.title.lower() or q in self.author.lower():
            return True
        return any(q in t.lower() for t in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "year": self.year,
            "tags": self.tags,
            "available": self.available,
        }


@dataclass
class Member:
    member_id: str
    name: str
    active: bool
    joined_at: datetime
    borrowed_ids: List[str] = field(default_factory=list)

    def can_borrow(self, limit: int = 5) -> bool:
        if not self.active:
            return False
        return len(self.borrowed_ids) < limit

    def borrow(self, book_id: str, limit: int = 5) -> bool:
        if not self.can_borrow(limit=limit):
            return False
        if book_id in self.borrowed_ids:
            return False
        self.borrowed_ids.append(book_id)
        return True

    def return_book(self, book_id: str) -> bool:
        if book_id not in self.borrowed_ids:
            return False
        self.borrowed_ids.remove(book_id)
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "member_id": self.member_id,
            "name": self.name,
            "active": self.active,
            "joined_at": self.joined_at.isoformat(),
            "borrowed_ids": list(self.borrowed_ids),
        }


class LibraryStore:
    def __init__(self, books_path: Path, members_path: Path) -> None:
        self.books_path = books_path
        self.members_path = members_path
        self._books: Dict[str, Book] = {}
        self._members: Dict[str, Member] = {}

    def load_books(self) -> None:
        self._books = {}
        data = load_json_safely(self.books_path)
        for row in data.get("books", []):
            try:
                b = Book(
                    book_id=str(row["book_id"]),
                    title=str(row.get("title", "")),
                    author=str(row.get("author", "")),
                    year=int(row.get("year", 0)),
                    tags=list(row.get("tags", [])),
                    available=bool(row.get("available", True)),
                )
            except (KeyError, ValueError, TypeError):
                continue
            self._books[b.book_id] = b

    def load_members(self) -> None:
        self._members = {}
        data = load_json_safely(self.members_path)
        for row in data.get("members", []):
            try:
                joined = datetime.fromisoformat(str(row.get("joined_at")))
                m = Member(
                    member_id=str(row["member_id"]),
                    name=str(row.get("name", "")),
                    active=bool(row.get("active", True)),
                    joined_at=joined,
                    borrowed_ids=list(row.get("borrowed_ids", [])),
                )
            except (KeyError, ValueError, TypeError):
                continue
            self._members[m.member_id] = m

    def save_books(self) -> None:
        payload = {"books": [b.to_dict() for b in self._books.values()]}
        self.books_path.parent.mkdir(parents=True, exist_ok=True)
        with self.books_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def save_members(self) -> None:
        payload = {"members": [m.to_dict() for m in self._members.values()]}
        self.members_path.parent.mkdir(parents=True, exist_ok=True)
        with self.members_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def get_book(self, book_id: str) -> Optional[Book]:
        return self._books.get(book_id)

    def get_member(self, member_id: str) -> Optional[Member]:
        return self._members.get(member_id)

    def all_books(self) -> List[Book]:
        return list(self._books.values())

    def all_members(self) -> List[Member]:
        return list(self._members.values())


class RemoteCatalogClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, book_id: str) -> str:
        return f"{self.base_url}/books/{book_id}"

    def fetch_metadata(self, book_id: str) -> Optional[Dict[str, Any]]:
        url = self._url(book_id)
        req = request.Request(url, headers={"Accept": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
        except error.URLError:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None


def load_json_safely(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def search_books(books: List[Book], query: str, limit: int = 10) -> List[Book]:
    if not query.strip():
        return []
    matches = [b for b in books if b.matches_query(query)]
    if not matches:
        return []
    matches.sort(key=lambda b: (not b.is_recent(), b.title.lower()))
    return matches[:limit]


def borrow_book(store: LibraryStore, member_id: str, book_id: str) -> bool:
    member = store.get_member(member_id)
    if member is None:
        return False
    book = store.get_book(book_id)
    if book is None or not book.available:
        return False
    if not member.borrow(book_id):
        return False
    book.available = False
    return True


def return_book(store: LibraryStore, member_id: str, book_id: str) -> bool:
    member = store.get_member(member_id)
    book = store.get_book(book_id)
    if member is None or book is None:
        return False
    if not member.return_book(book_id):
        return False
    book.available = True
    return True


def sync_remote_metadata(store: LibraryStore, client: RemoteCatalogClient, limit: int = 5) -> int:
    updated = 0
    for book in store.all_books():
        if updated >= limit:
            break
        meta = client.fetch_metadata(book.book_id)
        if not meta:
            continue
        title = str(meta.get("title", "")).strip()
        if title:
            book.title = title
        author = str(meta.get("author", "")).strip()
        if author:
            book.author = author
        tags = meta.get("tags")
        if isinstance(tags, list):
            book.tags = [str(t) for t in tags]
        updated += 1
    return updated


def export_summary(path: Path, store: LibraryStore) -> None:
    books = store.all_books()
    members = store.all_members()
    total_books = len(books)
    available = sum(1 for b in books if b.available)
    active_members = sum(1 for m in members if m.active)
    borrowed = total_books - available
    payload = {
        "total_books": total_books,
        "available_books": available,
        "borrowed_books": borrowed,
        "active_members": active_members,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def purge_inactive_members(store: LibraryStore, older_than_days: int = 365) -> int:
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    removed = 0
    for member in list(store._members.values()):
        if member.joined_at < cutoff and not member.active:
            del store._members[member.member_id]
            removed += 1
    return removed


def main(base_dir: str = "data") -> int:
    base = Path(base_dir)
    books_path = base / "books.json"
    members_path = base / "members.json"
    summary_path = base / "summary.json"

    store = LibraryStore(books_path, members_path)
    store.load_books()
    store.load_members()

    if not store.all_books() or not store.all_members():
        return 1

    cfg_path = base / "library_config.json"
    cfg = load_json_safely(cfg_path)
    base_url = str(cfg.get("remote_catalog_url", "")).strip()
    if base_url:
        client = RemoteCatalogClient(base_url=base_url)
        sync_remote_metadata(store, client, limit=int(cfg.get("sync_limit", 5)))

    purge_inactive_members(store, older_than_days=int(cfg.get("purge_days", 365)))
    store.save_books()
    store.save_members()
    export_summary(summary_path, store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
