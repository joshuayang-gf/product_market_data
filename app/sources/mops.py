"""證交所 各券商每月月計表 (data.gov.tw 20764, CSV 2) — 分戶帳 balance per broker.

The CSV is regenerated daily and only ever holds the latest filed month, so history exists
only in what this app has stored. 出表日期 is the generation date (ROC yyyMMdd); brokers file the
previous month by the 10th, so from config.MOPS_MIN_DAY on the file is treated as last month.
"""
import csv
import io
from datetime import date

from .. import catalog, config, months
from . import Row, http

URL = "https://mopsfin.twse.com.tw/opendata/t187ap20.csv"
ACCOUNT = "119095"  # 專戶分戶帳留存客戶款項


def target_month(report_date: date, min_day: int) -> str | None:
    if report_date.day < min_day:
        return None
    return months.add(months.of(report_date), -1)


def parse(content: bytes) -> tuple[date, list[tuple[str, str, float]]]:
    """Returns (出表日期, [(canonical code, name, 借方餘額)])."""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    report_date, out = None, []
    for r in reader:
        if r["科目"].strip() != ACCOUNT:
            continue
        roc = r["出表日期"].strip()
        report_date = date(int(roc[:-4]) + 1911, int(roc[-4:-2]), int(roc[-2:]))
        out.append((catalog.canonical_code(r["券商代號"]), catalog.clean_name(r["券商名稱"]),
                    float(r["借方餘額"].replace(",", "") or 0)))
    if report_date is None:
        raise ValueError(f"MOPS file has no account {ACCOUNT} rows")
    return report_date, out


def fetch() -> tuple[date, str | None, list[Row]]:
    """Returns (出表日期, month the snapshot is stored as or None if too early, rows)."""
    body = http.download(URL)
    if body is None:
        raise RuntimeError(f"{URL} not found")
    report_date, entries = parse(body)
    month = target_month(report_date, config.MOPS_MIN_DAY)
    (config.RAW_DIR / "mops").mkdir(parents=True, exist_ok=True)
    (config.RAW_DIR / "mops" / f"t187ap20.{report_date:%Y%m%d}.csv").write_bytes(body)
    if month is None:
        return report_date, None, []
    return report_date, month, [Row("split_account", "inventory", month, c, n, v) for c, n, v in entries]
