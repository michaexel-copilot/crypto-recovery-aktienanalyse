"""Übersetzt einen Report in formatneutrale Blöcke, die alle Renderer teilen."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .analysis import COLUMN_TITLES, Report, column_value
from .fmt import fmt_date_long, fmt_date_short, fmt_score
from .models import Snapshot


@dataclass
class Heading:
    text: str
    level: int = 2


@dataclass
class Para:
    text: str
    style: str = "normal"  # normal | small | muted


@dataclass
class Callout:
    lines: list[str]
    bullets: list[str] = field(default_factory=list)
    tone: str = "info"  # info | warn


@dataclass
class Bullets:
    items: list[str]
    title: str | None = None
    ordered: bool = False


@dataclass
class Table:
    header: list[str]
    rows: list[list[str]]
    ampel: list[str | None] = field(default_factory=list)  # Ampel je Zeile, für die Farbmarkierung
    ampel_col: int | None = None
    widths: list[float] | None = None


Block = Heading | Para | Callout | Bullets | Table


def tickers(snaps: list[Snapshot]) -> str:
    return ", ".join(s.ticker for s in snaps)


def build_document(r: Report) -> tuple[str, list[Block]]:
    c = r.config
    title = c.title.format(n=r.count)
    blocks: list[Block] = [
        Para(f"Stand: {fmt_date_long(r.stand)} (letzte Aktualisierung)", "muted"),
        Para(f"Disclaimer: {c.disclaimer}", "small"),
    ]

    # --- Update-Kasten ---
    lines, bullets = [], []
    if r.window_updated:
        today = r.updated_today
        lines.append(f"Update ({fmt_date_short(r.window_start + dt.timedelta(days=1))}–{fmt_date_short(r.stand)}"
                     f"{r.stand.year}): {len(r.window_updated)} von {r.count} Aktien aktualisiert. "
                     f"Am {fmt_date_short(r.stand)} kamen {len(today)} dazu ({tickers(today)}).")
    if r.stale:
        lines.append(f"Älter als {c.max_age_days} Tage: {tickers(r.stale)}.")
    else:
        lines.append(f"Alle {r.count} Aktien sind höchstens {c.max_age_days} Tage alt.")
    if r.new:
        neu = " und ".join(f"{s.ticker} {s.name} ({fmt_score(s.score)}, {r.ampel_text(s).title()})" for s in r.new)
        lines.append(f"Neu aufgenommen ({fmt_date_short(r.stand)}): {neu} — jetzt {r.count} Aktien.")
    if r.upgrades:
        bullets.append("Heraufgestuft: " + " · ".join(ch.text() for ch in r.upgrades))
    if r.downgrades:
        bullets.append("Herabgestuft: " + " · ".join(ch.text() for ch in r.downgrades))
    if r.upgrades or r.downgrades:
        bullets.append(f"Unverändert: die übrigen {len(r.unchanged)}")
    tail = list(c.notizen)
    if c.wochen_ereignisse:
        tail.append("Wichtige Ereignisse der Woche: " + " · ".join(c.wochen_ereignisse))
    if c.transparenz:
        tail.append(f"Transparenzhinweis: {c.transparenz}")
    blocks.append(Callout(lines, bullets))
    if tail:
        blocks.append(Callout(tail))

    # --- Ranking ---
    blocks.append(Heading("Übersicht sortiert nach Score"))
    cols = ["Rang", "Ticker", "Unternehmen", "Score", "Ampel", "Stand", "Sektor", "Kurz-Einschätzung"]
    rows = [[str(i), s.ticker, s.name, fmt_score(s.score), r.ampel_text(s), fmt_date_short(s.date), s.sektor, s.kurz]
            for i, s in enumerate(r.ranking, 1)]
    blocks.append(Table(cols, rows, [s.ampel for s in r.ranking], ampel_col=4,
                        widths=[5, 7, 14, 5, 13, 6, 16, 34]))

    # --- Ampel-Gruppen ---
    blocks.append(Heading("Gruppierung nach Ampel"))
    g = r.groups
    gruen = [f"{s.ticker} — {s.name}" + (f" ({s.ampel_hinweis} Grün)" if s.ampel_hinweis else "") for s in g["gruen"]]
    extra = []
    if g["gelb-gruen"]:
        extra.append(f"{tickers(g['gelb-gruen'])} Gelb-Grün")
    if r.tendenz_gruen:
        extra.append(f"Tendenz Grün: {tickers(r.tendenz_gruen)}")
    if extra:
        gruen.append("(" + "; ".join(extra) + ")")
    blocks.append(Bullets(gruen or ["–"], "● GRÜN — grundsätzlich attraktiv"))
    gelb = f"{len(g['gelb'])} von {r.count} Aktien"
    if g["gelb-gruen"]:
        gelb += f" (plus {tickers(g['gelb-gruen'])} Gelb-Grün)"
    if r.tendenz_rot:
        gelb += f". Mit Rot-Tendenz: {tickers(r.tendenz_rot)}"
    blocks.append(Bullets([gelb + "."], "● GELB — interessant, aber Risiken prüfen"))
    blocks.append(Bullets([tickers(g["rot"]) or "–"], "● ROT — hohe Risiken / nicht für Anfänger"))

    # --- Quervergleiche ---
    blocks.append(Heading(f"Quervergleiche (Stand {fmt_date_short(r.stand)})"))
    for cmp in r.comparisons:
        blocks.append(Heading(cmp.title, 3))
        if cmp.table and cmp.rows:
            blocks.append(Table([COLUMN_TITLES[col] for col in cmp.columns],
                                [[column_value(r, s, col) for col in cmp.columns] for s in cmp.rows],
                                [s.ampel for s in cmp.rows]))
        elif cmp.rows:
            blocks.append(Para(" vs. ".join(f"{s.ticker} ({fmt_score(s.score)}, {s.kurz})" for s in cmp.rows)))
        if cmp.text:
            blocks.append(Para(cmp.text))

    # --- Anfänger ---
    blocks.append(Heading("Anfänger-Orientierung"))
    b = r.beginner
    blocks.append(Bullets([f"{s.ticker} ({s.sektor})" for s in b["geeignet"].get("", [])] or ["–"],
                          "Eher geeignet (defensiv, fair bewertet)"))
    blocks.append(Bullets([f"{k}: {_with_hint(v)}" for k, v in b["sparplan"].items()],
                          "Mit Sparplan / gestaffelt denkbar"))
    items = [f"{k}: {tickers(v)}" for k, v in b["ungeeignet"].items()]
    blocks.append(Bullets(items, "Eher ungeeignet (zu spekulativ / zu teuer / zu volatil)"))
    if c.etf_hinweis:
        blocks.append(Para(c.etf_hinweis, "small"))

    # --- Termine ---
    blocks.append(Heading("Anstehende Termine"))
    rows = []
    for day, entries in r.calendar:
        label = fmt_date_short(day) + (" (heute)" if day == r.stand else "")
        by_text: dict[str, list[str]] = {}
        for s, text in entries:
            by_text.setdefault(text, []).append(s.ticker)
        rows.append([label, " · ".join(f"{', '.join(ts)} ({t})" for t, ts in by_text.items())])
    blocks.append(Table(["Datum", "Aktien"], rows, widths=[12, 88]))
    if r.refresh_hint:
        blocks.append(Callout([f"Hinweis: {tickers(r.refresh_hint)} sollten nach ihren Zahlen per "
                               "Update aufgefrischt werden."], tone="warn"))

    # --- Sektoren ---
    blocks.append(Heading("Sektor-Verteilung"))
    blocks.append(Table(["Sektor", "Anzahl", "Aktien"],
                        [[name, str(len(m)), tickers(m)] for name, m in r.sectors], widths=[30, 8, 62]))
    if r.observations:
        blocks.append(Callout(["Beobachtung: " + " ".join(r.observations)]))

    # --- Hinweise ---
    blocks.append(Heading("Wichtige Hinweise"))
    gelb_hinweis = f"Gelb ist die häufigste Bewertung ({len(g['gelb'])} von {r.count})."
    blocks.append(Bullets([c.hinweise[0], gelb_hinweis, *c.hinweise[1:]] if c.hinweise else [gelb_hinweis],
                          ordered=True))
    if c.details_pfad:
        blocks.append(Heading("Wo finde ich die Details?", 3))
        blocks.append(Para(c.details_pfad, "mono"))
    return title, blocks


def _with_hint(snaps: list[Snapshot]) -> str:
    return ", ".join(s.ticker + (f" ({s.anfaenger_hinweis})" if s.anfaenger_hinweis else "") for s in snaps)

