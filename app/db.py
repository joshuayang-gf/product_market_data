"""SQLite storage. Values are kept in NT$ (元) exactly as the sources report them."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    product     TEXT NOT NULL,
    metric      TEXT NOT NULL,
    month       TEXT NOT NULL,   -- YYYY-MM
    broker_code TEXT NOT NULL,
    value       REAL NOT NULL,   -- NT$
    source      TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (product, metric, month, broker_code)
);
CREATE TABLE IF NOT EXISTS broker_names (
    broker_code TEXT PRIMARY KEY,
    name        TEXT NOT NULL    -- latest name seen in a source, used when catalog.NAMES lacks the code
);
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL,   -- running / ok / error
    detail      TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init():
    with connect() as conn:
        conn.executescript(SCHEMA)


def replace_month(conn, product: str, metric: str, month: str, values: dict[str, float], source: str):
    """Swap in the full broker set for one product/metric/month, so revisions drop stale rows."""
    conn.execute("DELETE FROM observations WHERE product=? AND metric=? AND month=?", (product, metric, month))
    ts = now()
    conn.executemany(
        "INSERT INTO observations VALUES (?,?,?,?,?,?,?)",
        [(product, metric, month, code, v, source, ts) for code, v in values.items()],
    )


def remember_names(conn, names: dict[str, str]):
    conn.executemany(
        "INSERT INTO broker_names VALUES (?,?) ON CONFLICT(broker_code) DO UPDATE SET name=excluded.name",
        list(names.items()),
    )


def has_data(conn) -> bool:
    return conn.execute("SELECT 1 FROM observations LIMIT 1").fetchone() is not None


def latest_month(conn, product: str, metric: str) -> str | None:
    row = conn.execute(
        "SELECT MAX(month) FROM observations WHERE product=? AND metric=?", (product, metric)
    ).fetchone()
    return row[0]


def start_run(source: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs (source, started_at, status) VALUES (?,?, 'running')", (source, now())
        )
        return cur.lastrowid


def finish_run(run_id: int, status: str, detail: str):
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET finished_at=?, status=?, detail=? WHERE id=?", (now(), status, detail, run_id)
        )
