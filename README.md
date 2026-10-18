# Book Review API

A small full-stack app over the MySQL schema from my database course:
a FastAPI service with a REST API, a vanilla-JS front end, and tests that
run against a real MySQL/MariaDB. All writes go through the course's
stored procedures; MySQL triggers enforce the rating range (1–5) and block
deleting a book that still has reviews.

**Live demo:** https://book-review-api-snqu.onrender.com · **API docs:** https://book-review-api-snqu.onrender.com/docs

_Free tier: the first request after idle can take ~50 s while the service and database wake up._

## Stack

- Python 3.12, FastAPI, Uvicorn, PyMySQL
- MySQL 8 / MariaDB 10.11 — 6 tables, 11 stored procedures, 3 triggers (`sql/schema.sql`)
- Static front end (`static/index.html`), no build step
- pytest + FastAPI TestClient (`tests/`)
- Docker image, Render blueprint (`render.yaml`)

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | liveness + book count |
| GET | `/api/books?q=&author=` | list, keyword search, or author search |
| GET | `/api/books/{id}` | one book with its reviews |
| POST | `/api/books` | add a book by genre/status/author *names* (`add_book_by_names`) |
| PATCH | `/api/books/{id}/status` | change reading status (`update_book_status`) |
| DELETE | `/api/books/{id}` | delete; 409 if the trigger blocks it |
| GET/POST | `/api/books/{id}/reviews` | list / add a review (`add_review`); 422 on bad rating |
| GET | `/api/reviews`, `/api/genres`, `/api/statuses`, `/api/authors` | reference lists |

Business-rule errors raised with `SIGNAL SQLSTATE '45000'` inside MySQL are
mapped to 404 / 409 / 422 with the procedure's message.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # edit if your MySQL differs
export $(cat .env | xargs)
mysql -u root -p -e "CREATE DATABASE bookreview; CREATE USER 'app'@'localhost' IDENTIFIED BY 'apppass'; GRANT ALL ON bookreview.* TO 'app'@'localhost';"
uvicorn app.main:app --reload   # first start creates tables, triggers, procedures, and sample data
# open http://127.0.0.1:8000
```

## Tests

```bash
export $(cat .env | xargs)
pytest -q                   # resets the schema in MYSQL_DB, then runs 10 end-to-end tests
```

## Deploy (free tier)

1. **Database** — create a free MySQL on [Aiven](https://aiven.io) (real MySQL 8, triggers and procedures supported).
   Copy host, port, user, password, database name. TLS is required (`MYSQL_SSL=1`).
2. **Schema** — nothing to do. On startup the app checks for the `book` table and, if the
   database is empty, runs `sql/schema.sql` and `sql/seed.sql` itself (`AUTO_INIT_DB=1`, the default).
   `scripts/init_db.py` is still there for a manual reset.
3. **Web service** — push this repo to GitHub, then on [Render](https://render.com)
   choose *New → Blueprint*, pick the repo, and fill in the `MYSQL_*` secrets when asked.
   Render builds the Dockerfile and serves the app on a public URL.
4. Put the URL in this README and on the resume. (Done: see the top of this file.)

## Project layout

```
app/main.py         routes, request models, error mapping
app/repository.py   calls to stored procedures, row shaping
app/db.py           connection from env vars; mysql-client-style script loader (handles DELIMITER)
sql/schema.sql      tables, triggers, procedures (from the course project)
sql/seed.sql        neutral sample data
static/index.html   UI
tests/test_api.py   end-to-end tests
scripts/init_db.py  create/reset schema and seed
```
