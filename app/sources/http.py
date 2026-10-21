import logging
import time

import requests

from .. import config

log = logging.getLogger(__name__)


def download(url: str, archive_as: str | None = None, *, follow_redirects: bool = True,
             retries: int = 3) -> bytes | None:
    """GET url and return the body; None when the server says the file doesn't exist.

    archive_as is a path under RAW_DIR where a copy of the body is kept.
    """
    last_err = None
    for attempt in range(retries):
        try:
            res = requests.get(url, headers={"User-Agent": config.USER_AGENT},
                               timeout=config.HTTP_TIMEOUT, allow_redirects=follow_redirects)
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
            continue
        if res.status_code in (301, 302, 404):
            return None
        if res.status_code >= 500:
            last_err = RuntimeError(f"HTTP {res.status_code} from {url}")
            time.sleep(2 * (attempt + 1))
            continue
        res.raise_for_status()
        if archive_as:
            path = config.RAW_DIR / archive_as
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(res.content)
        return res.content
    raise RuntimeError(f"download failed: {url}: {last_err}")
