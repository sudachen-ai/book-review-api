"""Book Review API — FastAPI service over the MySQL book-review schema.

Run locally:
    uvicorn app.main:app --reload
Docs:
    /docs (Swagger UI), /redoc
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pymysql
from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import repository as repo
from .db import get_conn, run_script
from .repository import DomainError

app = FastAPI(
    title="Book Review API",
    version="1.0.0",
    description="CRUD and search over books, authors, genres, reading statuses, and reviews. "
    "Writes go through MySQL stored procedures; triggers enforce rating range and delete protection.",
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


@app.on_event("startup")
def auto_init_db() -> None:
    """Create the schema on first boot so a fresh hosted database works
    without a manual step. Set AUTO_INIT_DB=0 to disable."""
    if os.getenv("AUTO_INIT_DB", "1") != "1":
        return
    try:
        with get_conn() as conn:
            tables = {list(r.values())[0] for r in repo.query(conn, "SHOW TABLES")}
            if "book" in tables:
                return
            run_script(conn, str(SQL_DIR / "schema.sql"))
            run_script(conn, str(SQL_DIR / "seed.sql"))
    except pymysql.MySQLError as exc:  # pragma: no cover - logged, app still starts
        print(f"[auto_init_db] skipped: {exc}")


# --- schemas --------------------------------------------------------------

class BookIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    english_title: str = Field(default="", max_length=200)
    genre: str = Field(min_length=1, max_length=60)
    status: str = Field(min_length=1, max_length=40)
    author: str = Field(min_length=1, max_length=120)


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5, description="1–5; the DB trigger enforces the same range")
    notes: str | None = Field(default=None, max_length=1000)


class StatusIn(BaseModel):
    status: str = Field(min_length=1, max_length=40)


# --- error handling -------------------------------------------------------

@app.exception_handler(DomainError)
async def domain_error_handler(_, exc: DomainError):
    msg = exc.message
    code = status.HTTP_422_UNPROCESSABLE_ENTITY
    if "does not exist" in msg.lower():
        code = status.HTTP_404_NOT_FOUND
    elif "cannot delete" in msg.lower():
        code = status.HTTP_409_CONFLICT
    return Response(content=f'{{"detail": "{msg}"}}', status_code=code, media_type="application/json")


@app.exception_handler(pymysql.MySQLError)
async def mysql_error_handler(_, exc: pymysql.MySQLError):
    return Response(
        content='{"detail": "database error"}',
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        media_type="application/json",
    )


# --- routes ---------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, Any]:
    with get_conn() as conn:
        n = repo.query(conn, "SELECT COUNT(*) AS n FROM book")[0]["n"]
    return {"status": "ok", "books": n}


@app.get("/api/books")
def list_books(
    q: str | None = Query(default=None, description="keyword in title or English title"),
    author: str | None = Query(default=None, description="author name, partial match"),
) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if q:
            return repo.search_books(conn, q)
        if author:
            return repo.search_books_by_author(conn, author)
        return repo.list_books(conn)


@app.get("/api/books/{book_id}")
def get_book(book_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        book = repo.get_book(conn, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book does not exist")
    return book


@app.post("/api/books", status_code=status.HTTP_201_CREATED)
def create_book(body: BookIn) -> dict[str, Any]:
    with get_conn() as conn:
        return repo.add_book(conn, body.title, body.english_title, body.genre, body.status, body.author)


@app.patch("/api/books/{book_id}/status")
def update_status(book_id: int, body: StatusIn) -> dict[str, Any]:
    with get_conn() as conn:
        return repo.update_status(conn, book_id, body.status)


@app.delete("/api/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int) -> Response:
    with get_conn() as conn:
        repo.delete_book(conn, book_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/books/{book_id}/reviews")
def book_reviews(book_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        book = repo.get_book(conn, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book does not exist")
    return book["reviews"]


@app.post("/api/books/{book_id}/reviews", status_code=status.HTTP_201_CREATED)
def create_review(book_id: int, body: ReviewIn) -> dict[str, Any]:
    with get_conn() as conn:
        if repo.get_book(conn, book_id) is None:
            raise HTTPException(status_code=404, detail="Book does not exist")
        return repo.add_review(conn, book_id, body.rating, body.notes)


@app.get("/api/reviews")
def list_reviews() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return repo.list_reviews(conn)


@app.get("/api/genres")
def genres() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return repo.list_genres(conn)


@app.get("/api/statuses")
def statuses() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return repo.list_statuses(conn)


@app.get("/api/authors")
def authors() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return repo.list_authors(conn)


# --- static front end -----------------------------------------------------

@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
