"""Data access layer. Every write goes through the MySQL stored procedures
defined in sql/schema.sql so the database stays the single source of
business rules (rating range, delete protection, duplicate authors)."""
from __future__ import annotations

from typing import Any

import pymysql

from .db import call_proc, query


class DomainError(Exception):
    """Raised when MySQL signals a business-rule violation (SQLSTATE 45000)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _translate(exc: pymysql.MySQLError) -> Exception:
    # (1644, 'message') is what SIGNAL SQLSTATE '45000' produces.
    if exc.args and exc.args[0] == 1644:
        return DomainError(str(exc.args[1]))
    return exc


def _group_books(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The detail procedures return one row per (book, author). Fold the
    rows so each book carries a list of authors."""
    books: dict[int, dict[str, Any]] = {}
    for r in rows:
        b = books.setdefault(
            r["book_id"],
            {
                "book_id": r["book_id"],
                "title": r["title"],
                "english_title": r["englishtitle"],
                "genre": r["genre"],
                "status": r["status"],
                "authors": [],
            },
        )
        if r.get("author") and r["author"] not in b["authors"]:
            b["authors"].append(r["author"])
    return list(books.values())


def _review(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "book_id": r["book_id"],
        "review_number": r["review_number"],
        "rating": r["rating"],
        "notes": r["notes"],
    }


# --- reads ----------------------------------------------------------------

def list_books(conn) -> list[dict[str, Any]]:
    return _group_books(call_proc(conn, "get_all_book_detail"))


def get_book(conn, book_id: int) -> dict[str, Any] | None:
    # get_book_detail uses LIMIT 1, which drops co-authors; use the full
    # listing filtered in SQL instead so multi-author books are complete.
    rows = query(
        conn,
        """
        SELECT b.book_id, b.title, b.englishtitle, g.name AS genre,
               rs.name AS status, a.name AS author
        FROM book b
        LEFT JOIN genre g ON b.genre_id = g.genre_id
        LEFT JOIN read_status rs ON b.status_id = rs.status_id
        LEFT JOIN booktoauthor ba ON b.book_id = ba.book_id
        LEFT JOIN author a ON ba.author_id = a.author_id
        WHERE b.book_id = %s
        """,
        (book_id,),
    )
    books = _group_books(rows)
    if not books:
        return None
    book = books[0]
    book["reviews"] = [_review(r) for r in call_proc(conn, "get_review_detail_by_bookid", (book_id,))]
    return book


def search_books(conn, keyword: str) -> list[dict[str, Any]]:
    return _group_books(call_proc(conn, "search_books", (keyword,)))


def search_books_by_author(conn, author: str) -> list[dict[str, Any]]:
    return _group_books(call_proc(conn, "search_books_by_author", (author,)))


def list_reviews(conn) -> list[dict[str, Any]]:
    return [_review(r) for r in call_proc(conn, "get_all_review")]


def list_genres(conn) -> list[dict[str, Any]]:
    return query(conn, "SELECT genre_id AS id, name FROM genre ORDER BY name")


def list_statuses(conn) -> list[dict[str, Any]]:
    return query(conn, "SELECT status_id AS id, name FROM read_status ORDER BY status_id")


def list_authors(conn) -> list[dict[str, Any]]:
    return query(conn, "SELECT author_id AS id, name FROM author ORDER BY name")


# --- writes ---------------------------------------------------------------

def add_book(conn, title: str, english_title: str, genre: str, status: str, author: str) -> dict[str, Any]:
    try:
        call_proc(conn, "add_book_by_names", (title, english_title, genre, status, author))
        conn.commit()
    except pymysql.MySQLError as exc:
        conn.rollback()
        raise _translate(exc) from exc
    row = query(conn, "SELECT LAST_INSERT_ID() AS id")[0]
    book_id = int(row["id"])
    if book_id == 0:
        # LAST_INSERT_ID is 0 when the procedure's final insert was the
        # booktoauthor link; fall back to the newest matching book.
        row = query(
            conn,
            "SELECT MAX(book_id) AS id FROM book WHERE title=%s AND englishtitle=%s",
            (title, english_title),
        )[0]
        book_id = int(row["id"])
    return get_book(conn, book_id)


def add_review(conn, book_id: int, rating: int, notes: str | None) -> dict[str, Any]:
    try:
        call_proc(conn, "add_review", (book_id, rating, notes))
        conn.commit()
    except pymysql.MySQLError as exc:
        conn.rollback()
        raise _translate(exc) from exc
    reviews = call_proc(conn, "get_review_detail_by_bookid", (book_id,))
    return _review(reviews[-1])


def update_status(conn, book_id: int, status: str) -> dict[str, Any]:
    rows = query(conn, "SELECT status_id FROM read_status WHERE name=%s", (status,))
    if not rows:
        raise DomainError(f"Unknown status: {status}")
    try:
        call_proc(conn, "update_book_status", (book_id, rows[0]["status_id"]))
        conn.commit()
    except pymysql.MySQLError as exc:
        conn.rollback()
        raise _translate(exc) from exc
    return get_book(conn, book_id)


def delete_book(conn, book_id: int) -> None:
    try:
        call_proc(conn, "delete_book", (book_id,))
        conn.commit()
    except pymysql.MySQLError as exc:
        conn.rollback()
        raise _translate(exc) from exc
