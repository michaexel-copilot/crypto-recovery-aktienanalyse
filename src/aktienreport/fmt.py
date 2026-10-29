"""Deutsche Zahlen- und Datumsformate."""
from __future__ import annotations

import datetime as dt

from .models import Kurs

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
          "September", "Oktober", "November", "Dezember"]


def fmt_score(v: float) -> str:
    return str(int(v)) if v == int(v) else f"{v:.1f}".replace(".", ",")


def fmt_num(v: float) -> str:
    """1925 -> '1.925', 436.87 -> '436,87'."""
    s = f"{v:,.2f}" if v != int(v) else f"{int(v):,}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_date_short(d: dt.date) -> str:
    return f"{d.day:02d}.{d.month:02d}."


def fmt_date_long(d: dt.date) -> str:
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def fmt_kurs(k: Kurs | None) -> str:
    if k is None:
        return "–"
    waehrung = "p" if k.waehrung == "GBp" else k.waehrung
    prefix = "~" if k.hinweis and ("ca." in k.hinweis or "Spanne" in k.hinweis) else ""
    s = f"{prefix}{fmt_num(k.wert)} {waehrung}"
    if k.datum:
        s += f" ({fmt_date_short(k.datum)})"
    return s
