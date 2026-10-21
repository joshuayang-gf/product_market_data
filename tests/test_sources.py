"""Parsers against real files downloaded on 2026-10-21. Expected values were checked against the
Google Sheet the dashboard used to read from."""
from datetime import date
from pathlib import Path

import pytest

from app.sources import mops, tpex, twsa

FIX = Path(__file__).parent / "fixtures"


def by(rows, product, metric):
    return {r.code: r.value for r in rows if r.product == product and r.metric == metric}


@pytest.fixture(scope="module")
def tpex_rows():
    vol, name_codes = tpex.parse_volume((FIX / "CBmss102.202609.xls").read_bytes(), "2026-09")
    inv = tpex.parse_inventory((FIX / "CBmcs006.202609.xls").read_bytes(), "2026-09", name_codes)
    return vol + inv


def test_tpex_inventory(tpex_rows):
    eln = by(tpex_rows, "eln", "inventory")
    pgn = by(tpex_rows, "pgn", "inventory")
    assert eln["5260"] == 592_700_000
    assert pgn["5260"] == 1_044_200_000
    assert pgn["5850"] == 20_116_600_000
    assert eln["F020"] == 32_300_000  # 221T 群益期貨 matched to F020 by name
    assert len(eln) == 13


def test_tpex_volume_eln_excludes_cln(tpex_rows):
    eln = by(tpex_rows, "eln", "volume")
    pgn = by(tpex_rows, "pgn", "volume")
    assert eln["5850"] == 7_929_000      # 386,329 non-PG − 378,400 CLN (thousands)
    assert eln["9800"] == 560_147_000
    assert pgn["9800"] == 6_738_427_000


def test_tpex_rejects_wrong_month():
    with pytest.raises(ValueError, match="expected 2026/08"):
        tpex.parse_volume((FIX / "CBmss102.202609.xls").read_bytes(), "2026-08")


def test_tpex_inventory_code_rules():
    assert tpex.inventory_code("526T", "x", {}) == "5260"
    assert tpex.inventory_code("9A0T", "x", {}) == "9A00"
    assert tpex.inventory_code("221T", "x", {}) == "F020"
    assert tpex.inventory_code("592T", "x", {}) == "9B00"  # 元富 folded into 台新


def test_twsa():
    rows = twsa.parse_year((FIX / "twsa_115.xlsx").read_bytes())
    months = sorted({r.month for r in rows})
    assert months[0] == "2026-01" and months[-1] == "2026-09"  # Oct–Dec are unpublished zeros
    aug = {r.code: r.value for r in rows if r.month == "2026-08"}
    assert aug["0200"] == 5_032_418_632
    assert aug["5260"] == 49_647_679
    jan = [r for r in rows if r.month == "2026-01" and r.code == "9B00"]
    assert sum(r.value for r in jan) == 19_441_055_339 + 27_469_650_249 + 0  # 元富 + 台新 + 9B00


def test_mops():
    report_date, entries = mops.parse((FIX / "t187ap20_sample.csv").read_bytes())
    assert report_date == date(2026, 10, 21)
    vals = {c: v for c, _, v in entries}
    assert vals["9800"] == 199_648_629_096
    assert vals["5260"] == 3_455_508_052
    assert len(entries) == 65


def test_mops_target_month():
    assert mops.target_month(date(2026, 10, 21), 11) == "2026-09"
    assert mops.target_month(date(2026, 1, 15), 11) == "2025-12"
    assert mops.target_month(date(2026, 10, 5), 11) is None
