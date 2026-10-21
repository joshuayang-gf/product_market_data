"""櫃買中心 結構型商品統計資料 — monthly per-broker ELN/PGN outstanding and trading.

CBmcs006 證券商及槓桿交易商結構型商品流通在外餘額月報表 -> inventory
CBmss102 證券商及槓桿交易商結構型商品交易月報表       -> volume
Both are .xls in NT$ thousands, one file per month, published around the 1st of the next month.
"""
import re

import xlrd

from .. import catalog
from . import Row, http

URL = "https://www.tpex.org.tw/www/zh-tw/extendProduct/monthlyRptDl?name={report}.{yyyymm}-C.xls"
INVENTORY_REPORT = "CBmcs006"
VOLUME_REPORT = "CBmss102"
UNIT = 1000  # files are in NT$ thousands
OLE2_MAGIC = b"\xd0\xcf\x11\xe0"


def fetch_month(month: str) -> list[Row] | None:
    """Rows for one month, or None when TPEx hasn't published it yet."""
    files = {}
    for report in (INVENTORY_REPORT, VOLUME_REPORT):
        yyyymm = month.replace("-", "")
        body = http.download(URL.format(report=report, yyyymm=yyyymm),
                             archive_as=f"tpex/{report}.{yyyymm}.xls", follow_redirects=False)
        if body is None or not body.startswith(OLE2_MAGIC):
            return None
        files[report] = body
    volume, name_codes = parse_volume(files[VOLUME_REPORT], month)
    return volume + parse_inventory(files[INVENTORY_REPORT], month, name_codes)


def _sheet(content: bytes, month: str):
    sh = xlrd.open_workbook(file_contents=content).sheet_by_index(0)
    want = month.replace("-", "/")
    for r in range(min(sh.nrows, 6)):
        text = " ".join(str(v) for v in sh.row_values(r))
        m = re.search(r"(\d{4}/\d{2})", text)
        if "Month" in text and m:
            if m.group(1) != want:
                raise ValueError(f"TPEx file is for {m.group(1)}, expected {want}")
            return sh
    raise ValueError("TPEx file has no 月份 Month row")


def _header_row(sh) -> int:
    for r in range(min(sh.nrows, 10)):
        if "代號" in str(sh.cell_value(r, 0)):
            return r
    raise ValueError("TPEx file has no 代號 header row")


def _col(cells: list, test, what: str) -> int:
    for i, c in enumerate(cells):
        if test(str(c)):
            return i
    raise ValueError(f"TPEx file has no {what} column")


def _broker_rows(sh, start: int):
    for r in range(start, sh.nrows):
        code = str(sh.cell_value(r, 0)).strip()
        if not code or code.startswith("合計"):
            return
        yield r, code, catalog.clean_name(str(sh.cell_value(r, 1)))


def parse_volume(content: bytes, month: str) -> tuple[list[Row], dict[str, str]]:
    """Returns rows plus {cleaned name: canonical code} for matching the inventory file."""
    sh = _sheet(content, month)
    hdr = _header_row(sh)
    groups = sh.row_values(hdr - 1)  # merged group titles sit on each group's first (契約本金) column
    pg = _col(groups, lambda s: "保本型" in s and "非保本" not in s, "保本型")
    npg = _col(groups, lambda s: "非保本" in s, "非保本型")
    cln = _col(groups, lambda s: "信用連結" in s, "信用連結型")
    rows, name_codes = [], {}
    for r, raw, name in _broker_rows(sh, hdr + 1):
        code = catalog.canonical_code(raw[:4])
        name_codes[name] = code
        v = lambda c: float(sh.cell_value(r, c) or 0) * UNIT  # noqa: E731
        rows.append(Row("pgn", "volume", month, code, name, v(pg)))
        rows.append(Row("eln", "volume", month, code, name, v(npg) - v(cln)))
    return rows, name_codes


def inventory_code(raw: str, name: str, name_codes: dict[str, str]) -> str:
    if name in name_codes:
        return name_codes[name]
    if raw in catalog.TPEX_INVENTORY_CODES:
        return catalog.canonical_code(catalog.TPEX_INVENTORY_CODES[raw])
    if re.fullmatch(r"[0-9A-Z]{3}T", raw):
        return catalog.canonical_code(raw[:3] + "0")
    raise ValueError(f"unknown TPEx inventory code {raw} ({name})")


def parse_inventory(content: bytes, month: str, name_codes: dict[str, str]) -> list[Row]:
    sh = _sheet(content, month)
    hdr = _header_row(sh)
    cells = sh.row_values(hdr)
    pgn = _col(cells, lambda s: "PGN" in s, "PGN")
    eln = _col(cells, lambda s: "ELN" in s, "ELN")
    rows = []
    for r, raw, name in _broker_rows(sh, hdr + 1):
        code = inventory_code(raw, name, name_codes)
        rows.append(Row("pgn", "inventory", month, code, name, float(sh.cell_value(r, pgn) or 0) * UNIT))
        rows.append(Row("eln", "inventory", month, code, name, float(sh.cell_value(r, eln) or 0) * UNIT))
    return rows
