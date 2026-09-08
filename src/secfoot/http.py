from __future__ import annotations

import hashlib
import pathlib
import time

import requests


class MissingUserAgentError(ValueError):
    """SEC requires a descriptive User-Agent that includes a contact address."""


def build_headers(user_agent: str | None = None) -> dict:
    ua = (user_agent or "").strip()
    if not ua:
        raise MissingUserAgentError("SEC requires a descriptive User-Agent")
    if "@" not in ua:
        raise MissingUserAgentError(
            f"User-Agent must include a contact email address, got {ua!r}"
        )
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}


class Fetcher:
    """Polite, disk-cached HTTP. One network call per URL, ever."""

    def __init__(self, cache_dir, user_agent: str | None = None, min_interval: float = 0.11):
        self.headers = build_headers(user_agent)
        self.cache_dir = pathlib.Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.network_calls = 0
        self._last_call = 0.0

    def _cache_path(self, url: str) -> pathlib.Path:
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".body")

    def _throttle(self) -> None:
        gap = time.monotonic() - self._last_call
        if self._last_call and gap < self.min_interval:
            time.sleep(self.min_interval - gap)

    def get(self, url: str) -> str:
        path = self._cache_path(url)
        if path.exists():
            return path.read_text(encoding="utf-8")
        self._throttle()
        response = requests.get(url, headers=self.headers, timeout=60)
        self._last_call = time.monotonic()
        self.network_calls += 1
        response.raise_for_status()
        body = response.text
        path.write_text(body, encoding="utf-8")
        return body
