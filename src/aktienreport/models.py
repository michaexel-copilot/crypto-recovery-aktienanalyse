"""Datenmodell: ein Analyse-Snapshot einer Aktie zu einem Datum."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

AMPELN = ("gruen", "gelb-gruen", "gelb", "rot")
AMPEL_LABEL = {"gruen": "GRÜN", "gelb-gruen": "GELB-GRÜN", "gelb": "GELB", "rot": "ROT"}
ANFAENGER = ("geeignet", "sparplan", "ungeeignet")


def _date(v: Any) -> dt.date | None:
    if v is None or isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v))


@dataclass
class Kurs:
    wert: float
    waehrung: str
    datum: dt.date | None = None
    hinweis: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Kurs":
        return cls(float(d["wert"]), d.get("waehrung", ""), _date(d.get("datum")), d.get("hinweis"))


@dataclass
class Termin:
    datum: dt.date
    text: str


@dataclass
class Snapshot:
    ticker: str
    name: str
    date: dt.date
    score: float
    ampel: str
    sektor: str
    kurz: str = ""
    sektor_gruppe: str | None = None
    ampel_hinweis: str | None = None
    tendenz: str | None = None
    land: str | None = None
    yahoo: str | None = None  # abweichendes Yahoo-Finance-Symbol, z. B. NESN.SW
    aufgenommen: dt.date | None = None
    kurs: Kurs | None = None
    bewertung: str | None = None
    quartal: str | None = None
    kommentar: str | None = None
    aenderungsgrund: str | None = None
    anfaenger: str | None = None
    anfaenger_hinweis: str | None = None
    risiko: str | None = None
    tags: list[str] = field(default_factory=list)
    termine: list[Termin] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.ampel not in AMPELN:
            raise ValueError(f"{self.ticker}: unbekannte Ampel {self.ampel!r} (erlaubt: {AMPELN})")
        if self.tendenz is not None and self.tendenz not in AMPELN:
            raise ValueError(f"{self.ticker}: unbekannte Tendenz {self.tendenz!r}")
        if not 0 <= self.score <= 10:
            raise ValueError(f"{self.ticker}: Score {self.score} außerhalb 0–10")
        if self.anfaenger is not None and self.anfaenger not in ANFAENGER:
            raise ValueError(f"{self.ticker}: unbekannte Anfänger-Kategorie {self.anfaenger!r}")

    @classmethod
    def from_dict(cls, d: dict) -> "Snapshot":
        d = dict(d)
        d["date"] = _date(d["date"])
        d["score"] = float(d["score"])
        d["aufgenommen"] = _date(d.get("aufgenommen"))
        if d.get("kurs"):
            d["kurs"] = Kurs.from_dict(d["kurs"])
        d["termine"] = [Termin(_date(t["datum"]), t["text"]) for t in d.get("termine") or []]
        d["tags"] = list(d.get("tags") or [])
        known = cls.__dataclass_fields__
        unknown = set(d) - set(known)
        if unknown:
            raise ValueError(f"{d.get('ticker')}: unbekannte Felder {sorted(unknown)}")
        return cls(**d)

    def to_dict(self) -> dict:
        out: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            v = getattr(self, name)
            if v is None or v == []:
                continue
            if isinstance(v, dt.date):
                v = v.isoformat()
            elif isinstance(v, Kurs):
                v = {k: (x.isoformat() if isinstance(x, dt.date) else x)
                     for k, x in vars(v).items() if x is not None}
            elif name == "termine":
                v = [{"datum": t.datum.isoformat(), "text": t.text} for t in v]
            out[name] = v
        return out
