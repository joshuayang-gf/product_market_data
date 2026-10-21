"""證券商公會 外國有價證券統計資料 — monthly 複委託 turnover per broker.

One xlsx per ROC year ("115年外國買賣彙總統計表.xlsx"), first sheet, NT$. Each broker row is
followed by investor-type breakdown rows without a code, which are skipped. Months not yet
published are zero for every broker.
"""
import io
import re
from urllib.parse import quote, urljoin

import openpyxl

from .. import catalog, months
from . import Row, http

PAGE = "https://www.twsa.org.tw/E01/E011.html"
FILE = "{roc}年外國買賣彙總統計表.xlsx"


def year_url(year: int) -> str:
    """Link from the E011 page, falling back to the usual file name."""
    fname = FILE.format(roc=months.roc_year(year))
    page = http.download(PAGE)
    if page:
        for href in re.findall(r'href\s*=\s*"([^"]+)"', page.decode("utf-8", "replace")):
            if fname in href:
                return urljoin(PAGE, quote(href, safe="/:.()"))
    return urljoin(PAGE, "doc/" + quote(fname))


def fetch_year(year: int) -> list[Row]:
    body = http.download(year_url(year), archive_as=f"twsa/{months.roc_year(year)}.xlsx")
    if body is None:
        return []
    return parse_year(body)


def _code(v) -> str | None:
    if v is None:
        return None
    s = str(int(v)) if isinstance(v, (int, float)) else str(v).strip()
    s = s.zfill(4) if s.isdigit() else s
    return s if re.fullmatch(r"[0-9A-Z]{4}", s) else None


def parse_year(content: bytes) -> list[Row]:
    ws = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True).worksheets[0]
    table = list(ws.iter_rows(values_only=True))
    hdr = next((i for i, r in enumerate(table[:10]) if any(str(c).strip() == "券商代號" for c in r if c)), None)
    if hdr is None:
        raise ValueError("TWSA file has no 券商代號 header row")
    header = [str(c or "").strip() for c in table[hdr]]
    code_col = header.index("券商代號")
    name_col = code_col + 1
    month_cols = {}
    for i, h in enumerate(header):
        m = re.fullmatch(r"(\d+)年(\d+)月份", h)
        if m:
            month_cols[i] = months.fmt(int(m.group(1)) + 1911, int(m.group(2)))
    if not month_cols:
        raise ValueError("TWSA file has no 月份 columns")

    brokers = []
    for r in table[hdr + 1:]:
        code = _code(r[code_col] if len(r) > code_col else None)
        if code:
            brokers.append((catalog.canonical_code(code), catalog.clean_name(str(r[name_col] or "")), r))
    rows = []
    for col, month in month_cols.items():
        vals = [(code, name, float(r[col] or 0)) for code, name, r in brokers]
        if sum(v for _, _, v in vals) == 0:
            continue  # not published yet
        rows += [Row("sub_brokerage", "volume", month, code, name, v) for code, name, v in vals]
    return rows
