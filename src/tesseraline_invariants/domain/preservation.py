"""What `preserves` compares: numbers, dates, quotes and links, normalised one documented way.

`tesseraline-invariants/src/tesseraline_invariants/domain/preservation.py`

Normalisation: thousands separators dropped ("1,000" == "1000"); "percent", "per
cent" and "pct" become "%"; a trailing ".0" is kept as written. Dates become ISO (2026-11-17) from
ISO, "17 November 2026" and "November 17, 2026". Quotes are text between straight or curly double
quotes. Links are http(s) URLs without trailing punctuation. Anything this misses is a known gap,
never a silent pass: it simply is not compared.
"""

from __future__ import annotations

import re
from collections import Counter
from enum import StrEnum


class Kind(StrEnum):
    """What a `preserves` promise keeps."""

    NUMBERS = "numbers"
    DATES = "dates"
    QUOTES = "quotes"
    LINKS = "links"


_MONTHS = {
    m: i
    for i, m in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        start=1,
    )
}
_PERCENT = re.compile(r"\s*(?:per\s?cent|percent|pct)\b", re.IGNORECASE)
_NUMBER = re.compile(
    r"(?<![\w.])[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|(?<![\w.])[-+]?\d+(?:\.\d+)?%?"
)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_MONTH = re.compile(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b")
_MONTH_DAY = re.compile(r"\b([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\b")
_QUOTE = re.compile(r"\"([^\"\n]{1,500})\"|“([^”\n]{1,500})”")
_LINK = re.compile(r"https?://[^\s<>\"']+")


def extract(kind: Kind, text: str) -> Counter[str]:
    """Collect the normalised items of one kind, with how often each appears.

    :param kind: numbers, dates, quotes or links.
    :param text: any text.
    :returns: a multiset of normalised items.

    Examples:
        >>> sorted(extract(Kind.NUMBERS, "Attendance 1,000 rose 15 percent"))
        ['1000', '15%']
        >>> sorted(extract(Kind.DATES, "on 17 November 2026 and 2026-11-18"))
        ['2026-11-17', '2026-11-18']
    """
    if kind is Kind.NUMBERS:
        return Counter(_number(m) for m in _NUMBER.findall(_without_dates(_PERCENT.sub("%", text))))
    if kind is Kind.DATES:
        return Counter(_dates(text))
    if kind is Kind.QUOTES:
        return Counter((a or b).strip() for a, b in _QUOTE.findall(text))
    return Counter(link.rstrip(".,;:)]}") for link in _LINK.findall(text))


def difference(kind: Kind, before: str, after: str, both_ways: bool) -> tuple[list[str], list[str]]:
    """Compare what an input carried with what the output carries.

    :param kind: what to compare.
    :param before: the input, rendered as text.
    :param after: the output, rendered as text.
    :param both_ways: also report items that appear only in the output.
    :returns: (lost items, new items); new items is empty when both_ways is False.

    Examples:
        >>> difference(Kind.NUMBERS, "up 15% to 1,200", "up 15 percent to 1200", True)
        ([], [])
        >>> difference(Kind.NUMBERS, "up 15%", "up 51%", True)
        (['15%'], ['51%'])
    """
    have, got = extract(kind, before), extract(kind, after)
    lost = sorted((have - got).elements())
    new = sorted((got - have).elements()) if both_ways else []
    return lost, new


def _number(raw: str) -> str:
    return raw.replace(",", "").lstrip("+")


def _without_dates(text: str) -> str:
    """Dates are compared as dates; their digits must not count again as numbers."""
    for pattern in (_ISO, _DAY_MONTH, _MONTH_DAY):
        text = pattern.sub(lambda m: " " if _date_of(m) else m.group(0), text)
    return text


def _dates(text: str) -> list[str]:
    found = []
    for pattern in (_ISO, _DAY_MONTH, _MONTH_DAY):
        found += [d for m in pattern.finditer(text) if (d := _date_of(m))]
    return found


def _date_of(m: re.Match[str]) -> str | None:
    a, b, c = m.groups()
    if m.re is _ISO:
        year, month, day = int(a), int(b), int(c)
    elif m.re is _DAY_MONTH:
        day, month, year = int(a), _MONTHS.get(b.lower(), 0), int(c)
    else:
        month, day, year = _MONTHS.get(a.lower(), 0), int(b), int(c)
    if not (1 <= month <= 12 and 1 <= day <= 31):  # noqa: PLR2004 - calendar bounds
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"
