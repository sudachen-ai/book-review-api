"""MySQL connection helpers.

Configuration comes from environment variables so the same code runs
locally, in tests, and on the hosting provider:

    MYSQL_HOST      default 127.0.0.1
    MYSQL_PORT      default 3306
    MYSQL_USER      default app
    MYSQL_PASSWORD  default apppass
    MYSQL_DB        default bookreview
    MYSQL_SSL       "1" to require TLS (needed for most hosted MySQL services)
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import Any, Iterator

import pymysql
import pymysql.cursors


def _config() -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "app"),
        "password": os.getenv("MYSQL_PASSWORD", "apppass"),
        "database": os.getenv("MYSQL_DB", "bookreview"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
    }
    if os.getenv("MYSQL_SSL", "0") == "1":
        # Hosted MySQL providers (Aiven, PlanetScale-style services) require TLS.
        cfg["ssl"] = {"ssl": {}}
    return cfg


@contextmanager
def get_conn() -> Iterator[pymysql.connections.Connection]:
    conn = pymysql.connect(**_config())
    try:
        yield conn
    finally:
        conn.close()


def call_proc(conn: pymysql.connections.Connection, name: str, args: tuple = ()) -> list[dict[str, Any]]:
    """Call a stored procedure and return the first result set as a list of dicts."""
    with conn.cursor() as cur:
        cur.callproc(name, args)
        rows = cur.fetchall()
        # Drain any extra result sets so the connection is reusable.
        while cur.nextset():
            cur.fetchall()
    return list(rows)


def query(conn: pymysql.connections.Connection, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return list(cur.fetchall())


# --- schema loading -------------------------------------------------------

_DELIM_RE = re.compile(r"^\s*DELIMITER\s+(\S+)\s*$", re.IGNORECASE)


def split_sql_script(text: str) -> list[str]:
    """Split a mysql-client style script (with DELIMITER lines) into statements.

    The mysql CLI understands `DELIMITER $$`; the server does not. This
    function re-creates that client behavior so the same schema file can be
    loaded with PyMySQL.
    """
    statements: list[str] = []
    delimiter = ";"
    buf: list[str] = []
    for line in text.splitlines():
        m = _DELIM_RE.match(line)
        if m:
            delimiter = m.group(1)
            continue
        stripped = line.strip()
        if not buf and (not stripped or stripped.startswith("--")):
            continue
        buf.append(line)
        if stripped.endswith(delimiter):
            stmt = "\n".join(buf).strip()
            stmt = stmt[: -len(delimiter)].strip()
            if stmt:
                statements.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def run_script(conn: pymysql.connections.Connection, path: str) -> int:
    with open(path, encoding="utf-8") as f:
        statements = split_sql_script(f.read())
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    conn.commit()
    return len(statements)
