"""Command line: python -m app.cli {update,bootstrap,backfill,import-csv,status}."""
import argparse
import json
import logging
from datetime import date
from pathlib import Path

from . import config, db, months, updater


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("update", help="daily incremental update (what the scheduler runs)")
    sub.add_parser("bootstrap", help="seed files + full history from START_MONTH")
    bf = sub.add_parser("backfill", help="re-download TPEx months and TWSA years for a range")
    bf.add_argument("--from", dest="start", required=True, help="YYYY-MM")
    bf.add_argument("--to", dest="end", default=months.add(months.of(date.today()), -1), help="YYYY-MM")
    ic = sub.add_parser("import-csv", help="load product,metric,month,broker_code,name,value rows")
    ic.add_argument("path", type=Path)
    sub.add_parser("status", help="print the latest run of each source")
    args = ap.parse_args()

    db.init()
    if args.cmd == "update":
        updater.daily()
    elif args.cmd == "bootstrap":
        updater.bootstrap()
    elif args.cmd == "backfill":
        config.START_MONTH = min(config.START_MONTH, args.start)
        with updater.LOCK:
            print(updater.update_tpex(months.span(args.start, args.end)))
            print(updater.update_twsa(list(range(months.parse(args.start)[0], months.parse(args.end)[0] + 1))))
    elif args.cmd == "import-csv":
        with updater.LOCK:
            print(updater.import_csv(args.path, source="manual"))
    if args.cmd in ("update", "bootstrap", "status"):
        from .main import status
        print(json.dumps(status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
