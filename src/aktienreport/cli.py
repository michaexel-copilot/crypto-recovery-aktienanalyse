"""Kommandozeile: aktienreport <befehl> ..."""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import sys
from pathlib import Path

from .analysis import build_report
from .config import ReportConfig
from .document import build_document
from .fmt import fmt_date_short, fmt_kurs, fmt_score
from .models import AMPELN, ANFAENGER, Snapshot
from .render import render_html, render_markdown, render_pdf
from .store import Store


def _date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def cmd_build(a) -> int:
    store, cfg = Store(a.data), ReportConfig.load(a.config)
    report = build_report(store, cfg, a.stand)
    title, blocks = build_document(report)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    base = out / f"zusammenfassung-{report.stand.isoformat()}"
    for f in a.format.split(","):
        f = f.strip()
        if f == "md":
            path = base.with_suffix(".md")
            path.write_text(render_markdown(title, blocks, cfg.footer), encoding="utf-8")
        elif f == "html":
            path = base.with_suffix(".html")
            path.write_text(render_html(title, blocks, cfg.footer), encoding="utf-8")
        elif f == "pdf":
            path = base.with_suffix(".pdf")
            render_pdf(title, blocks, path, cfg.footer, f"erstellt {report.stand.strftime('%d.%m.%Y')}")
        else:
            print(f"Unbekanntes Format: {f}", file=sys.stderr)
            return 2
        print(path)
    return 0


def cmd_list(a) -> int:
    report = build_report(Store(a.data), ReportConfig.load(a.config), a.stand)
    for i, s in enumerate(report.ranking, 1):
        print(f"{i:>3}  {s.ticker:<7} {s.name[:26]:<26} {fmt_score(s.score):>4}  "
              f"{report.ampel_text(s):<18} {fmt_date_short(s.date)}  {s.kurz}")
    return 0


def cmd_show(a) -> int:
    hist = Store(a.data).history(a.ticker.upper())
    if not hist:
        print(f"Keine Analysen für {a.ticker}", file=sys.stderr)
        return 1
    for s in hist:
        print(f"{s.date}  Score {fmt_score(s.score):>4}  {s.ampel:<10}  Kurs {fmt_kurs(s.kurs):<22} {s.kurz}")
    return 0


FIELDS = ["name", "score", "ampel", "tendenz", "sektor", "sektor_gruppe", "land", "kurz", "bewertung",
          "quartal", "kommentar", "grund", "anfaenger", "risiko"]


def cmd_update(a) -> int:
    """Neuen Snapshot anlegen – basierend auf dem letzten, mit geänderten Feldern."""
    store = Store(a.data)
    ticker = a.ticker.upper()
    hist = store.history(ticker)
    if not hist and not a.neu:
        print(f"{ticker} existiert noch nicht – mit --neu anlegen.", file=sys.stderr)
        return 1
    if hist and a.neu:
        print(f"{ticker} existiert bereits.", file=sys.stderr)
        return 1
    date = a.datum or dt.date.today()
    base = hist[-1].to_dict() if hist else {"ticker": ticker, "aufgenommen": date.isoformat()}
    base.pop("aenderungsgrund", None)
    base["date"] = date.isoformat()
    for f in FIELDS:
        v = getattr(a, f)
        if v is not None:
            base["aenderungsgrund" if f == "grund" else f] = v
    if a.kurs:
        wert, _, waehrung = a.kurs.partition(" ")
        base["kurs"] = {"wert": float(wert.replace(",", ".")), "waehrung": waehrung or
                        (base.get("kurs") or {}).get("waehrung", ""), "datum": date.isoformat()}
    for t in a.termin or []:
        d, _, text = t.partition(":")
        base.setdefault("termine", []).append({"datum": d, "text": text or "Termin"})
    if a.tag:
        base["tags"] = sorted(set(base.get("tags", [])) | set(a.tag))
    missing = [k for k in ("name", "score", "ampel", "sektor") if k not in base]
    if missing:
        print(f"Pflichtfelder fehlen: {', '.join(missing)}", file=sys.stderr)
        return 1
    snap = Snapshot.from_dict(base)
    print(store.save(snap))
    if hist and hist[-1].score != snap.score:
        print(f"Score {fmt_score(hist[-1].score)} → {fmt_score(snap.score)}")
    return 0


def cmd_kurse(a) -> int:
    from .market import fetch_kurs
    store = Store(a.data)
    latest = store.latest()
    tickers = [t.upper() for t in a.tickers] or list(latest)
    failed = 0
    for t in tickers:
        s = latest.get(t)
        if s is None:
            print(f"{t}: unbekannt", file=sys.stderr)
            failed += 1
            continue
        try:
            kurs = fetch_kurs(s)
        except Exception as exc:  # noqa: BLE001 – einzelne Fehlschläge sollen den Lauf nicht abbrechen
            print(f"{t}: {exc}", file=sys.stderr)
            failed += 1
            continue
        store.save(dataclasses.replace(s, kurs=kurs))
        print(f"{t}: {fmt_kurs(kurs)}")
    return 1 if failed else 0


def cmd_check(a) -> int:
    store = Store(a.data)
    problems = []
    for t in store.tickers():
        try:
            hist = store.history(t)
        except (ValueError, KeyError, TypeError) as exc:
            problems.append(f"{t}: {exc}")
            continue
        s = hist[-1]
        if s.score <= 3 and s.ampel != "rot":
            problems.append(f"{t}: Score {fmt_score(s.score)}, aber Ampel {s.ampel}")
        if s.score >= 7 and s.ampel == "rot":
            problems.append(f"{t}: Score {fmt_score(s.score)}, aber Ampel rot")
        if not s.sektor_gruppe:
            problems.append(f"{t}: keine sektor_gruppe")
    for p in problems:
        print(p)
    print(f"{len(store.tickers())} Aktien geprüft, {len(problems)} Hinweise.")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aktienreport", description="Zusammenfassungen von Aktienanalysen erzeugen")
    p.add_argument("--data", default="data/aktien", help="Ordner mit den Snapshots (Standard: data/aktien)")
    p.add_argument("--config", default="config/report.yaml", help="Report-Konfiguration")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="Report erzeugen")
    b.add_argument("--stand", type=_date, help="Stichtag (YYYY-MM-DD), Standard: jüngster Snapshot")
    b.add_argument("--format", default="pdf,html,md", help="Kommagetrennt: pdf,html,md")
    b.add_argument("--out", default="reports")
    b.set_defaults(func=cmd_build)

    ls = sub.add_parser("list", help="Ranking im Terminal anzeigen")
    ls.add_argument("--stand", type=_date)
    ls.set_defaults(func=cmd_list)

    sh = sub.add_parser("show", help="Historie einer Aktie")
    sh.add_argument("ticker")
    sh.set_defaults(func=cmd_show)

    u = sub.add_parser("update", help="Neuen Analyse-Snapshot anlegen (übernimmt Felder vom letzten)")
    u.add_argument("ticker")
    u.add_argument("--neu", action="store_true", help="Aktie neu aufnehmen")
    u.add_argument("--datum", type=_date, help="Analysedatum, Standard: heute")
    u.add_argument("--name")
    u.add_argument("--score", type=lambda v: float(v.replace(",", ".")))
    u.add_argument("--ampel", choices=AMPELN)
    u.add_argument("--tendenz", choices=AMPELN)
    u.add_argument("--sektor")
    u.add_argument("--sektor-gruppe", dest="sektor_gruppe")
    u.add_argument("--land")
    u.add_argument("--kurz", help="Kurz-Einschätzung")
    u.add_argument("--bewertung", help='z. B. "KGV ~20"')
    u.add_argument("--quartal", help='Quartalskennzahl, z. B. "Azure +48 %%"')
    u.add_argument("--kommentar")
    u.add_argument("--grund", help="Begründung einer Score-Änderung")
    u.add_argument("--anfaenger", choices=ANFAENGER)
    u.add_argument("--risiko", help='Risiko-Kategorie, z. B. "Hoch bewertet"')
    u.add_argument("--kurs", help='z. B. "531 USD"')
    u.add_argument("--termin", action="append", help='"YYYY-MM-DD:Text", mehrfach möglich')
    u.add_argument("--tag", action="append", help="Tag für Quervergleiche, mehrfach möglich")
    u.set_defaults(func=cmd_update)

    k = sub.add_parser("kurse", help="Aktuelle Kurse von Yahoo Finance holen (braucht Internet + yfinance)")
    k.add_argument("tickers", nargs="*")
    k.set_defaults(func=cmd_kurse)

    c = sub.add_parser("check", help="Daten auf Plausibilität prüfen")
    c.set_defaults(func=cmd_check)

    a = p.parse_args(argv)
    return a.func(a)
