"""Page numbers and page ranges (as in py-imposition).

Page numbers are 1-based and may be written relative to the last page:
``LAST``, ``LAST-1``. Ranges are written ``a-b`` or ``a..b``, and an open
range ``a-`` goes on to the last page. Items are separated by commas or
spaces. ``all``, ``odd`` and ``even`` are whole specs.
"""

from __future__ import annotations

import re

from .interface import tr

_NUM = r"(?:LAST(?:-\d+)?|\d+)"


class PageError(ValueError):
    """A list of pages that cannot be read."""


def page_number(token: str, n: int) -> int:
    """One page number (1-based, LAST allowed) as a 1-based int."""
    t = token.strip().upper().replace(" ", "")
    if t.startswith("LAST"):
        rest = t[4:]
        if not rest:
            return n
        if rest.startswith("-") and rest[1:].isdigit():
            return n - int(rest[1:])
    elif t.isdigit():
        return int(t)
    raise PageError(tr("{token} is not a page number", token=token.strip()))


def _split_range(token: str) -> tuple[str, str] | None:
    t = token.strip().upper().replace(" ", "")
    if ".." in t:
        a, b = t.split("..", 1)
        return a, b or "LAST"
    if re.fullmatch(r"LAST-\d+", t):
        return None
    m = re.fullmatch(rf"({_NUM})-({_NUM})?", t)
    if m:
        return m.group(1), m.group(2) or "LAST"
    return None


def parse_pages(spec: str | None, n: int) -> list[int]:
    """The 0-based indices of the pages SPEC names, sorted, each once.
    Pages beyond the last are left out (raises PageError if SPEC can't be read)."""
    s = (spec or "").strip().lower()
    if s in ("", "all"):
        return list(range(n))
    if s == "odd":
        return list(range(0, n, 2))
    if s == "even":
        return list(range(1, n, 2))
    out: set[int] = set()
    for token in re.split(r"[,;\s]+", s):
        if not token:
            continue
        rng = _split_range(token)
        if rng:
            a, b = page_number(rng[0], n), page_number(rng[1], n)
            nums = range(min(a, b), max(a, b) + 1)
        else:
            nums = [page_number(token, n)]
        out.update(p - 1 for p in nums if 1 <= p <= n)
    return sorted(out)


def check(spec: str) -> str:
    """'' if SPEC can be read, else why not."""
    try:
        parse_pages(spec, 1000)
    except PageError as e:
        return str(e)
    return ""
