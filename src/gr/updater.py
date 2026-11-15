"""Update check against the project's GitHub releases.

Deliberately dependency-free (urllib) and failure-tolerant: no network, a rate
limit, or a malformed payload all resolve to "no update" rather than an error.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass

RELEASES_URL = "https://api.github.com/repos/zvanderburgt/ghost-hand/releases/latest"
TIMEOUT = 6.0
USER_AGENT = "GhostHand-update-check"


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    name: str = ""


def parse_version(text: str) -> tuple[int, ...]:
    """'v0.7.1' -> (0, 7, 1). Missing pieces become zero."""
    if not text:
        return (0,)
    numbers = re.findall(r"\d+", text)
    if not numbers:
        return (0,)
    return tuple(int(part) for part in numbers)


def is_newer(candidate: str, current: str) -> bool:
    a = list(parse_version(candidate))
    b = list(parse_version(current))
    width = max(len(a), len(b))
    a += [0] * (width - len(a))
    b += [0] * (width - len(b))
    return a > b


def _default_fetch(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def latest_release(url: str = RELEASES_URL, timeout: float = TIMEOUT,
                   fetch=None) -> Release | None:
    """Newest published release, or None if it can't be read."""
    fetch = fetch or _default_fetch
    try:
        payload = fetch(url, timeout)
        data = json.loads(payload)
    except Exception:  # noqa: BLE001 - offline, rate limited, bad JSON
        return None
    if not isinstance(data, dict):
        return None
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        return None
    return Release(
        version=tag,
        url=str(data.get("html_url") or ""),
        name=str(data.get("name") or tag),
    )


def check(current: str, url: str = RELEASES_URL, fetch=None) -> Release | None:
    """Release to offer, or None when up to date / unreachable."""
    release = latest_release(url, fetch=fetch)
    if release is None:
        return None
    return release if is_newer(release.version, current) else None
