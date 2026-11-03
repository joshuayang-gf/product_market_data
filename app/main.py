"""Web server: dashboard page, JSON API and the daily update schedule."""
import logging
import secrets
import threading
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles

from . import catalog, config, db, months, updater

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

YI = 1e8  # the page shows 億元
CATCH_UP_AFTER = timedelta(hours=20)


def _stale(last_ok: str | None) -> bool:
    return last_ok is None or datetime.now(timezone.utc) - datetime.fromisoformat(last_ok) > CATCH_UP_AFTER


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    with db.connect() as conn:
        empty = not db.has_data(conn)
        last_ok = db.last_success(conn)
        new_products = [p["id"] for p in catalog.PRODUCTS if not db.has_data(conn, p["id"])]
    if empty and config.AUTO_BOOTSTRAP:
        log.info("empty database, bootstrapping from %s in the background", config.START_MONTH)
        threading.Thread(target=updater.bootstrap, daemon=True).start()
    elif config.SCHEDULER_ENABLED and (_stale(last_ok) or new_products):
        # The host was off at the scheduled time, or a product was just added; don't wait for tomorrow.
        log.info("catching up now: last success %s, products without data %s", last_ok or "never", new_products)
        threading.Thread(target=updater.daily, daemon=True).start()
    scheduler = None
    if config.SCHEDULER_ENABLED:
        hour, minute = (int(x) for x in config.UPDATE_TIME.split(":"))
        scheduler = BackgroundScheduler(timezone=config.TIMEZONE)
        scheduler.add_job(updater.daily, CronTrigger(hour=hour, minute=minute, timezone=config.TIMEZONE),
                          id="daily", misfire_grace_time=6 * 3600, coalesce=True)
        scheduler.start()
        log.info("daily update scheduled at %s %s", config.UPDATE_TIME, config.TIMEZONE)
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="券商月度資料看板", lifespan=lifespan)


def _dataset(conn, names: dict[str, str], product: str, metric: str) -> dict:
    rows = conn.execute(
        "SELECT month, broker_code, value FROM observations WHERE product=? AND metric=?", (product, metric)
    ).fetchall()
    if not rows:
        return {"months": [], "brokers": []}
    cells = defaultdict(dict)
    for r in rows:
        cells[r["broker_code"]][r["month"]] = r["value"]
    month_list = months.span(min(r["month"] for r in rows), max(r["month"] for r in rows))
    last = month_list[-1]
    brokers = [
        {"code": code,
         "name": catalog.display_name(code, names.get(code, "")),
         "values": [None if m not in by_month else round(by_month[m] / YI, 6) for m in month_list]}
        for code, by_month in cells.items()
        if any(by_month.values())  # drop firms that are zero throughout
    ]
    brokers.sort(key=lambda b: -(cells[b["code"]].get(last) or 0))
    return {"months": month_list, "brokers": brokers}


@app.get("/api/data")
def data():
    with db.connect() as conn:
        names = {r["broker_code"]: r["name"] for r in conn.execute("SELECT * FROM broker_names")}
        products = []
        for p in catalog.PRODUCTS:
            products.append({
                **p,
                "metrics": {m: {"label": catalog.METRIC_LABELS[m], **_dataset(conn, names, p["id"], m)}
                            for m in p["metrics"]},
            })
    return {"unit": "億元", "products": products, "status": status()}


@app.get("/api/status")
def status():
    with db.connect() as conn:
        runs = [dict(r) for r in conn.execute(
            "SELECT source, started_at, finished_at, status, detail FROM runs "
            "WHERE id IN (SELECT MAX(id) FROM runs GROUP BY source) ORDER BY source")]
        latest = {p["id"]: {m: db.latest_month(conn, p["id"], m) for m in p["metrics"]} for p in catalog.PRODUCTS}
        last_ok = db.last_success(conn)
    return {"updating": updater.LOCK.locked(), "last_success": last_ok, "latest_month": latest, "runs": runs}


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/refresh", status_code=202)
def refresh(x_admin_token: str = Header(default="")):
    if not config.ADMIN_TOKEN:
        raise HTTPException(404)
    if not secrets.compare_digest(x_admin_token, config.ADMIN_TOKEN):
        raise HTTPException(403, "bad token")
    if updater.LOCK.locked():
        raise HTTPException(409, "update already running")
    threading.Thread(target=updater.daily, daemon=True).start()
    return {"started": True}


app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
