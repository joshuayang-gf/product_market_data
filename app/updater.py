"""Pull the sources into the database. Every step is idempotent: re-running a month replaces it."""
import csv
import logging
import threading
from collections import defaultdict
from datetime import date
from pathlib import Path

from . import config, db, months
from .sources import Row, mops, tpex, twsa

log = logging.getLogger(__name__)
LOCK = threading.Lock()  # scheduler, admin endpoint and CLI must not write concurrently


def store(rows: list[Row], source: str) -> list[str]:
    """Write rows grouped per product/metric/month; returns 'product/metric/month' keys written."""
    grouped: dict[tuple, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    names = {}
    for r in rows:
        grouped[(r.product, r.metric, r.month)][r.code] += r.value  # aliased codes add up
        if r.name:
            names[r.code] = r.name
    with db.connect() as conn:
        for (product, metric, month), values in grouped.items():
            db.replace_month(conn, product, metric, month, dict(values), source)
        db.remember_names(conn, names)
    return sorted(f"{p}/{m}/{mo}" for p, m, mo in grouped)


def _run(source: str, fn) -> str:
    run_id = db.start_run(source)
    try:
        detail = fn()
    except Exception as e:
        log.exception("%s update failed", source)
        db.finish_run(run_id, "error", f"{type(e).__name__}: {e}")
        return "error"
    log.info("%s: %s", source, detail)
    db.finish_run(run_id, "ok", detail)
    return "ok"


def _summary(written: list[str]) -> str:
    if not written:
        return "沒有新資料"
    return f"更新 {len(written)} 組：{written[0]} … {written[-1]}" if len(written) > 3 else "更新 " + "、".join(written)


def update_tpex(month_list: list[str]) -> str:
    written, missing = [], []
    for m in month_list:
        rows = tpex.fetch_month(m)
        if rows is None:
            missing.append(m)
            continue
        written += store(rows, "tpex")
    detail = _summary(written)
    return detail + (f"（尚未公布：{', '.join(missing)}）" if missing else "")


def update_twsa(years: list[int]) -> str:
    written = []
    for y in years:
        rows = [r for r in twsa.fetch_year(y) if r.month >= config.START_MONTH]
        written += store(rows, "twsa")
    return _summary(written)


def update_mops() -> str:
    report_date, month, rows = mops.fetch()
    if month is None:
        return f"出表日期 {report_date}，未滿 {config.MOPS_MIN_DAY} 日，等待上月申報完成"
    return f"出表日期 {report_date} → {month}；" + _summary(store(rows, "mops"))


def import_csv(path: Path, source: str = "seed") -> str:
    """Long-format CSV: product,metric,month,broker_code,name,value (value in NT$).

    Codes are stored as written (no CODE_ALIASES), so imported history keeps the split it was recorded with.
    """
    with open(path, encoding="utf-8-sig") as f:
        rows = [Row(r["product"], r["metric"], r["month"], r["broker_code"].strip().upper(),
                    r.get("name", ""), float(r["value"])) for r in csv.DictReader(f)]
    return _summary(store(rows, source))


def daily(today: date | None = None):
    """Incremental run: refresh recent months (catches revisions) and anything newly published."""
    today = today or date.today()
    last_month = months.add(months.of(today), -1)
    with LOCK:
        with db.connect() as conn:
            tpex_last = db.latest_month(conn, "eln", "inventory")
        tpex_from = months.add(tpex_last, -2) if tpex_last else config.START_MONTH
        _run("tpex", lambda: update_tpex(months.span(max(tpex_from, config.START_MONTH), last_month)))
        years = sorted({months.parse(m)[0] for m in months.span(months.add(last_month, -2), last_month)})
        _run("twsa", lambda: update_twsa(years))
        _run("mops", update_mops)


def bootstrap(today: date | None = None):
    """First fill: seed files, then full history from START_MONTH."""
    today = today or date.today()
    last_month = months.add(months.of(today), -1)
    with LOCK:
        for path in sorted(config.SEED_DIR.glob("*.csv")):
            _run(f"seed:{path.name}", lambda p=path: import_csv(p))
        _run("tpex", lambda: update_tpex(months.span(config.START_MONTH, last_month)))
        years = list(range(months.parse(config.START_MONTH)[0], today.year + 1))
        _run("twsa", lambda: update_twsa(years))
        _run("mops", update_mops)
