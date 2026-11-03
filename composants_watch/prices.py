"""Lecture tolérante des prix affichés (formats FR et US)."""
from __future__ import annotations

import re

_NUM = re.compile(r"\d[\d\s  .,]*")


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    if "gratuit" in text.lower():
        return 0.0
    m = _NUM.search(text)
    if not m:
        return None
    s = re.sub(r"[\s  ]", "", m.group(0)).rstrip(".,")
    if "," in s and "." in s:
        # le dernier séparateur est le décimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = s.replace(",", "") if len(tail) == 3 and "$" in text else head.replace(",", "") + "." + tail
    try:
        return round(float(s), 2)
    except ValueError:
        return None
