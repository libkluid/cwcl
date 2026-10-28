"""Shared HTTP helpers for the load layer.

All sources are Korean public-sector sites, so requests stay polite: a
descriptive User-Agent, a cookie-persisting session, and a per-request delay.
``changwon.go.kr`` advertises ``Crawl-delay: 10`` in robots.txt, so its source
defaults to a 10 second delay.
"""

from __future__ import annotations

import html as _html
import re

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

_WS = re.compile(r"\s+")
_ISO_DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
_BR = re.compile(r"(?i)<br\s*/?>")
_BLOCK = re.compile(r"(?i)</(?:p|div|li|tr|h[1-6]|ul|ol)\s*>")
_TAG = re.compile(r"<[^>]+>")
_BLANKS = re.compile(r"\n{3,}")


def clean(value: str | None) -> str | None:
    """Collapse all whitespace runs (newlines, tabs, nbsp) into single spaces."""
    if value is None:
        return None
    value = value.replace("\u00a0", " ")
    return _WS.sub(" ", value).strip() or None


def iso_date(value: str | None) -> str | None:
    """Extract a ``YYYY-MM-DD`` date (accepts ``.``/``-``/``/`` separators)."""
    if not value:
        return None
    found = _ISO_DATE.search(value)
    if not found:
        return None
    year, month, day = found.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def html_to_text(fragment: str | None) -> str | None:
    """Turn an HTML body fragment into readable plain text."""
    if fragment is None:
        return None
    text = _BR.sub("\n", fragment)
    text = _BLOCK.sub("\n", text)
    text = _TAG.sub("", text)
    text = _html.unescape(text).replace("\u00a0", " ")
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return _BLANKS.sub("\n\n", text).strip() or None


def client(*, referer: str | None = None, timeout: float = 30.0) -> httpx.Client:
    """A cookie-persisting, redirect-following client for one source.

    Connection-level failures are retried a few times by the transport.
    """
    headers = dict(DEFAULT_HEADERS)
    if referer:
        headers["Referer"] = referer
    return httpx.Client(
        headers=headers,
        timeout=timeout,
        follow_redirects=True,
        transport=httpx.HTTPTransport(retries=3),
    )


def fetch(http: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response | None:
    """Request a URL, returning ``None`` on any HTTP/connection error.

    Lets a single flaky page stop its source gracefully instead of aborting the
    whole run.
    """
    try:
        resp = http.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp
    except httpx.HTTPError as exc:
        print(f"[load] request failed: {method} {url}: {exc}")
        return None
