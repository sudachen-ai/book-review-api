"""Create (or reset) the schema and optionally load sample data.

    python scripts/init_db.py            # schema + seed
    python scripts/init_db.py --no-seed  # schema only

Reads the same MYSQL_* environment variables as the app. The target
database must already exist; this script creates tables, triggers, and
stored procedures inside it and DROPS existing tables first.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_conn, run_script  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-seed", action="store_true")
    args = ap.parse_args()
    with get_conn() as conn:
        n = run_script(conn, str(ROOT / "sql" / "schema.sql"))
        print(f"schema: {n} statements")
        if not args.no_seed:
            n = run_script(conn, str(ROOT / "sql" / "seed.sql"))
            print(f"seed: {n} statements")


if __name__ == "__main__":
    main()
