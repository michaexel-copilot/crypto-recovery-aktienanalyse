"""Optionale Kursaktualisierung über Yahoo Finance (Paket `yfinance`, braucht Internetzugang)."""
from __future__ import annotations

from .models import Kurs, Snapshot

# Standard-Zuordnung für Nicht-US-Ticker. Pro Aktie überschreibbar über das Feld `yahoo`.
YAHOO_SYMBOLS = {
    "NESN": "NESN.SW", "ROG": "ROG.SW", "NVS": "NOVN.SW", "ZURN": "ZURN.SW", "HOLN": "HOLN.SW", "ALC": "ALC.SW",
    "AMRZ": "AMRZ.SW", "MUV2": "MUV2.DE", "RHM": "RHM.DE", "BAYN": "BAYN.DE", "TKMS": "TKMS.DE", "NLM": "NLM.DE",
    "VUL": "VUL.DE", "SAN": "SAN.PA", "HO": "HO.PA", "MC": "MC.PA", "RNO": "RNO.PA", "BAES": "BA.L", "LDO": "LDO.MI",
    "DAIKIN": "6367.T", "CATL": "300750.SZ", "1810": "1810.HK", "DRO": "DRO.AX", "GGD": "GGD.TO", "NVO": "NVO",
}


def symbol_for(s: Snapshot) -> str:
    return s.yahoo or YAHOO_SYMBOLS.get(s.ticker, s.ticker)


def fetch_kurs(s: Snapshot) -> Kurs:
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Für Kursabfragen bitte installieren: pip install 'aktienreport[markt]'") from exc
    t = yf.Ticker(symbol_for(s))
    hist = t.history(period="5d")
    if hist.empty:
        raise ValueError(f"{s.ticker}: keine Kursdaten für {symbol_for(s)}")
    last = hist.iloc[-1]
    waehrung = (t.fast_info.get("currency") or (s.kurs.waehrung if s.kurs else "")) if t.fast_info else ""
    return Kurs(round(float(last["Close"]), 2), waehrung, hist.index[-1].date())

