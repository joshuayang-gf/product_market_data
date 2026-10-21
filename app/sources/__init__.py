"""Source adapters. Each one downloads a public file and turns it into Rows."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    product: str
    metric: str
    month: str   # YYYY-MM
    code: str    # canonical broker code (catalog.canonical_code applied)
    name: str    # broker name as published, cleaned
    value: float  # NT$
