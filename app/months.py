"""Month arithmetic on 'YYYY-MM' strings."""
from datetime import date


def parse(month: str) -> tuple[int, int]:
    y, m = month.split("-")
    return int(y), int(m)


def fmt(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def add(month: str, n: int) -> str:
    y, m = parse(month)
    i = y * 12 + (m - 1) + n
    return fmt(i // 12, i % 12 + 1)


def of(d: date) -> str:
    return fmt(d.year, d.month)


def span(start: str, end: str) -> list[str]:
    """Inclusive list of months from start to end."""
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur = add(cur, 1)
    return out


def roc_year(year: int) -> int:
    return year - 1911
