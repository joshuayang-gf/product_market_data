"""證交所 各券商每月月計表 (data.gov.tw 20764, CSV 2) — per-broker balances of selected accounts.

The CSV is regenerated every few days and only ever holds the latest filed month, so history
exists only in what this app has stored. 出表日期 is the generation date (ROC yyyMMdd); brokers
file the previous month by the 10th, so from config.MOPS_MIN_DAY on the file is treated as last month.
"""
import csv
import io
from datetime import date

from .. import catalog, config, months
from . import Row, http

URL = "https://mopsfin.twse.com.tw/opendata/t187ap20.csv"
# 會計科目 -> product; the 借方餘額 column of each account becomes that product's inventory.
ACCOUNTS = {
    "119095": "split_account",  # 專戶分戶帳留存客戶款項
    "214010": "rp",             # 附買回債券負債
}


def target_month(report_date: date, min_day: int) -> str | None:
    if report_date.day < min_day:
        return None
    return months.add(months.of(report_date), -1)


def parse(content: bytes) -> tuple[date, list[tuple[str, str, str, float]]]:
    """Returns (出表日期, [(product, canonical code, name, 借方餘額)])."""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    report_date, out = None, []
    for r in reader:
        product = ACCOUNTS.get(r["科目"].strip())
        if product is None:
            continue
        roc = r["出表日期"].strip()
        report_date = date(int(roc[:-4]) + 1911, int(roc[-4:-2]), int(roc[-2:]))
        out.append((product, catalog.canonical_code(r["券商代號"]), catalog.clean_name(r["券商名稱"]),
                    float(r["借方餘額"].replace(",", "") or 0)))
    missing = set(ACCOUNTS.values()) - {p for p, *_ in out}
    if missing:
        raise ValueError(f"MOPS file has no rows for {sorted(missing)}")
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
    return report_date, month, [Row(p, "inventory", month, c, n, v) for p, c, n, v in entries]
