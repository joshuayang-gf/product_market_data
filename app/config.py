"""Runtime settings, all overridable through environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "market.db"
RAW_DIR = DATA_DIR / "raw"          # every downloaded source file is archived here
SEED_DIR = BASE_DIR / "seed"        # history that no public source can rebuild
STATIC_DIR = BASE_DIR / "static"

# Earliest month pulled from the sources on first start / backfill (YYYY-MM).
START_MONTH = os.getenv("START_MONTH", "2025-01")

TIMEZONE = os.getenv("TZ", "Asia/Taipei")
# Daily update time, HH:MM in TIMEZONE.
UPDATE_TIME = os.getenv("UPDATE_TIME", "08:30")
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "1") == "1"
# Fill the database in the background the first time the server starts on an empty DB.
AUTO_BOOTSTRAP = os.getenv("AUTO_BOOTSTRAP", "1") == "1"

# POST /api/refresh needs this token in the X-Admin-Token header; unset disables the endpoint.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Brokers file the previous month's 月計表 by the 10th, so the MOPS snapshot is only
# taken as "last month" from this day of the month on.
MOPS_MIN_DAY = int(os.getenv("MOPS_MIN_DAY", "11"))

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "60"))
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (compatible; product-market-data/1.0; +https://github.com/joshuayang-gf/product_market_data)",
)
