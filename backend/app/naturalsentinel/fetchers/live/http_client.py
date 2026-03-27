"""Rate-limited HTTP client for live regulatory source fetching.

Uses only stdlib (urllib) to keep the zero-dependency core intact.
Rate limiting is per-client-instance so each source can have its own
independent throttle.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

USER_AGENT = (
    "NaturalSentinel/1.0 regulatory monitoring research tool — "
    "respectful automated access; contact: opensource@example.com"
)
DEFAULT_RATE_LIMIT = 1.5  # seconds between requests
DEFAULT_TIMEOUT = 30  # seconds


class HTTPClient:
    """Thin rate-limited wrapper over urllib.request.

    Args:
        rate_limit_seconds: Minimum seconds between consecutive requests.
        timeout: Per-request network timeout in seconds.
        user_agent: User-Agent header sent with every request.
    """

    def __init__(
        self,
        rate_limit_seconds: float = DEFAULT_RATE_LIMIT,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str = USER_AGENT,
    ):
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout = timeout
        self.user_agent = user_agent
        self._last_request_time: float = 0.0

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)

    def get(self, url: str, params: dict | None = None) -> str:
        """Fetch *url* and return the response body as a decoded string.

        Raises :class:`urllib.error.URLError` on network failure.
        """
        if params:
            url = url + "?" + urllib.parse.urlencode(params, doseq=True)
        self._throttle()
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self._last_request_time = time.monotonic()
                raw = resp.read()
                charset = "utf-8"
                content_type = resp.headers.get("Content-Type", "")
                if "charset=" in content_type:
                    charset = content_type.split("charset=")[-1].split(";")[0].strip()
                return raw.decode(charset, errors="replace")
        except urllib.error.URLError:
            self._last_request_time = time.monotonic()
            raise

    def get_json(self, url: str, params: dict | None = None) -> dict | list:
        """Fetch *url* and parse the response as JSON."""
        text = self.get(url, params=params)
        return json.loads(text)
