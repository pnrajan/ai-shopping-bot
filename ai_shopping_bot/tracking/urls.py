"""URL normalization so the same product page maps to one tracked item."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_DROP_PREFIXES = ("utm_", "ref", "tag", "fbclid", "gclid", "mc_", "_hs")


def normalize_url(url: str) -> str:
    """Lowercase scheme and host, drop fragment, tracking params, and a trailing slash."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith(_DROP_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(sorted(query)), "")
    )
