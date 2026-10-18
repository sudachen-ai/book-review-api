"""End-to-end API tests against a real MySQL/MariaDB.

Set MYSQL_* env vars (see app/db.py). The schema is reset before the
module runs, so point these tests at a throwaway database.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import get_conn, run_script  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def reset_db():
    with get_conn() as conn:
        run_script(conn, str(ROOT / "sql" / "schema.sql"))
        run_script(conn, str(ROOT / "sql" / "seed.sql"))
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["books"] == 4


def test_list_books_groups_authors(client):
    books = client.get("/api/books").json()
    assert len(books) == 4
    first = books[0]
    assert set(first) == {"book_id", "title", "english_title", "genre", "status", "authors"}
    assert first["authors"] == ["Ursula K. Le Guin"]


def test_get_book_includes_reviews(client):
    r = client.get("/api/books/4")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Exhalation"
    assert [rv["rating"] for rv in body["reviews"]] == [4, 5]


def test_get_missing_book_404(client):
    assert client.get("/api/books/999").status_code == 404


def test_search_keyword_and_author(client):
    by_kw = client.get("/api/books", params={"q": "Rome"}).json()
    assert [b["book_id"] for b in by_kw] == [3]
    by_author = client.get("/api/books", params={"author": "Knuth"}).json()
    assert [b["book_id"] for b in by_author] == [2]


def test_create_book_reuses_existing_author_and_creates_new_genre(client):
    r = client.post(
        "/api/books",
        json={
            "title": "The Dispossessed",
            "english_title": "The Dispossessed",
            "genre": "fiction",
            "status": "to read",
            "author": "Ursula K. Le Guin",
        },
    )
    assert r.status_code == 201, r.text
    book = r.json()
    assert book["authors"] == ["Ursula K. Le Guin"]
    assert book["status"] == "to read"
    authors = client.get("/api/authors").json()
    assert sum(a["name"] == "Ursula K. Le Guin" for a in authors) == 1  # not duplicated


def test_review_rating_range_enforced_by_api_and_db(client):
    # Pydantic rejects out-of-range before the DB sees it.
    r = client.post("/api/books/1/reviews", json={"rating": 6, "notes": "x"})
    assert r.status_code == 422
    # The DB trigger is the second line of defense; call it directly.
    import pymysql

    with get_conn() as conn:
        with pytest.raises(pymysql.MySQLError) as ei:
            with conn.cursor() as cur:
                cur.callproc("add_review", (1, 0, "bad"))
        assert ei.value.args[0] == 1644
        conn.rollback()


def test_add_review_appends_review_number(client):
    r = client.post("/api/books/1/reviews", json={"rating": 3, "notes": "second read"})
    assert r.status_code == 201
    assert r.json()["review_number"] == 2


def test_update_status(client):
    r = client.patch("/api/books/3/status", json={"status": "reading"})
    assert r.status_code == 200
    assert r.json()["status"] == "reading"
    r = client.patch("/api/books/3/status", json={"status": "nope"})
    assert r.status_code == 422


def test_delete_protected_by_trigger_then_allowed(client):
    # Book 1 has reviews -> trigger blocks delete -> 409
    r = client.delete("/api/books/1")
    assert r.status_code == 409
    assert "Cannot delete" in r.json()["detail"]
    # Book 3 has no reviews -> 204, then 404
    assert client.delete("/api/books/3").status_code == 204
    assert client.get("/api/books/3").status_code == 404
    assert client.delete("/api/books/3").status_code == 404
