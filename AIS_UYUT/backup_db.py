"""Create a consistent SQLite backup using SQLite's online backup API."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from db import DB_NAME, get_db


def backup(destination: Path) -> Path:
    source = Path(DB_NAME)
    if not source.is_file():
        raise FileNotFoundError(f"Database does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = get_db()
    try:
        # SQLite backup API safely includes committed data when WAL is enabled.
        import sqlite3

        with sqlite3.connect(destination) as target:
            src.backup(target)
    finally:
        src.close()
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", nargs="?", type=Path)
    args = parser.parse_args()
    destination = args.destination or Path("backups") / f"hotel-{datetime.now():%Y%m%d-%H%M%S}.db"
    print(f"Backup created: {backup(destination)}")


if __name__ == "__main__":
    main()
