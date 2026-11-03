"""GET HTTP poli : User-Agent explicite, délai par hôte, retries 5xx/réseau."""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from . import __version__

USER_AGENT = f"composants-watch/{__version__} (usage personnel)"
TIMEOUT = 20
RETRIES = 2
MIN_SPACING = 2.0
BACKOFF = (2, 5)

_last_hit: dict[str, float] = {}


class FetchError(Exception):
    pass


def http_get(url: str, headers: dict | None = None, *, opener=None,
             sleep=time.sleep) -> bytes:
    opener = opener or urllib.request.urlopen
    host = urlsplit(url).netloc
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               **(headers or {})})
    last_err: Exception | None = None
    for attempt in range(RETRIES + 1):
        wait = MIN_SPACING - (time.monotonic() - _last_hit.get(host, -1e9))
        if wait > 0:
            sleep(wait)
        _last_hit[host] = time.monotonic()
        try:
            with opener(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code < 500:
                raise FetchError(f"HTTP {e.code} {url}") from e
            last_err = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
        if attempt < RETRIES:
            sleep(BACKOFF[attempt])
    raise FetchError(f"échec après {RETRIES + 1} essais : {url} ({last_err})")
