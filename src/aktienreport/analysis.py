"""Verdichtet die jüngsten Snapshots zu den Abschnitten der Zusammenfassung."""
from __future__ import annotations

import datetime as dt
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field

from .config import ReportConfig
from .fmt import fmt_date_short, fmt_score
from .models import AMPEL_LABEL, Snapshot
from .store import Store

AMPEL_RANK = {"gruen": 0, "gelb-gruen": 1, "gelb": 2, "rot": 3}


@dataclass
class Change:
    snap: Snapshot
    old: float
    new: float

    @property
    def up(self) -> bool:
        return self.new > self.old

    def text(self) -> str:
        grund = f" ({self.snap.aenderungsgrund})" if self.snap.aenderungsgrund else ""
        return f"{self.snap.ticker} {fmt_score(self.old)}→{fmt_score(self.new)}{grund}"


@dataclass
class Comparison:
    title: str
    columns: list[str]
    rows: list[Snapshot]
    text: str | None = None
    table: bool = True


@dataclass
class Report:
    config: ReportConfig
    stand: dt.date
    ranking: list[Snapshot]
    updated_today: list[Snapshot]
    window_updated: list[Snapshot]
    new: list[Snapshot]
    upgrades: list[Change]
    downgrades: list[Change]
    unchanged: list[Snapshot]
    stale: list[Snapshot]
    groups: dict[str, list[Snapshot]]
    tendenz_gruen: list[Snapshot]
    tendenz_rot: list[Snapshot]
    comparisons: list[Comparison]
    beginner: dict[str, "OrderedDict[str, list[Snapshot]]"]
    calendar: list[tuple[dt.date, list[tuple[Snapshot, str]]]]
    refresh_hint: list[Snapshot]
    sectors: list[tuple[str, list[Snapshot]]]
    observations: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.ranking)

    @property
    def window_start(self) -> dt.date:
        return self.stand - dt.timedelta(days=self.config.update_window_days)

    def ampel_text(self, s: Snapshot) -> str:
        label = AMPEL_LABEL[s.ampel]
        extra = []
        if s.ampel_hinweis:
            extra.append(s.ampel_hinweis)
        if s.tendenz and s.tendenz != s.ampel:
            extra.append(f"→ {AMPEL_LABEL[s.tendenz].title()}")
        return f"{label} ({', '.join(extra)})" if extra else label


def _sort_key(s: Snapshot):
    return (-s.score, AMPEL_RANK[s.ampel], s.date, s.ticker)


def build_report(store: Store, config: ReportConfig, stand: dt.date | None = None) -> Report:
    latest = store.latest(until=stand)
    if not latest:
        raise ValueError(f"Keine Analysen in {store.root} gefunden")
    stand = stand or max(s.date for s in latest.values())
    snaps = sorted(latest.values(), key=_sort_key)
    window_start = stand - dt.timedelta(days=config.update_window_days)

    # Score-Änderungen: jüngster Snapshot vs. letzter Snapshot vor dem Update-Fenster
    upgrades, downgrades, unchanged = [], [], []
    for s in snaps:
        if s.date != stand:
            continue
        prev = [h for h in store.history(s.ticker, until=stand) if h.date < s.date]
        if not prev:
            continue
        old = prev[-1].score
        if old == s.score:
            unchanged.append(s)
        else:
            (upgrades if s.score > old else downgrades).append(Change(s, old, s.score))
    upgrades.sort(key=lambda c: -c.new)
    downgrades.sort(key=lambda c: -c.old)

    new = [s for s in snaps if s.aufgenommen and window_start < s.aufgenommen <= stand]
    updated_today = [s for s in snaps if s.date == stand]
    unchanged += [s for s in updated_today
                  if s not in unchanged and s not in new
                  and not any(c.snap is s for c in upgrades + downgrades)]
    stale = [s for s in snaps if (stand - s.date).days > config.max_age_days]

    groups: dict[str, list[Snapshot]] = {a: [s for s in snaps if s.ampel == a] for a in AMPEL_RANK}
    tendenz_gruen = [s for s in snaps if s.tendenz == "gruen" and s.ampel != "gruen"]
    tendenz_rot = [s for s in snaps if s.tendenz == "rot" and s.ampel != "rot"]

    comparisons = []
    for c in config.comparisons:
        rows = [s for s in snaps if c.tag in s.tags]
        if not rows and not c.text:
            continue
        comparisons.append(Comparison(c.title, c.columns, rows, c.text, c.table))

    beginner = {
        "geeignet": OrderedDict([("", [s for s in snaps if s.anfaenger == "geeignet"])]),
        "sparplan": _group(
            [s for s in snaps if s.anfaenger in ("geeignet", "sparplan")],
            lambda s: config.sparplan_gruppe(s.sektor_gruppe), order=config.sparplan_order()),
        "ungeeignet": _group([s for s in snaps if s.anfaenger == "ungeeignet"],
                             lambda s: s.risiko or "Sonstige", order=config.risiko_order),
    }

    by_day: dict[dt.date, list[tuple[Snapshot, str]]] = defaultdict(list)
    refresh = []
    for s in snaps:
        for t in s.termine:
            if t.datum >= stand:
                by_day[t.datum].append((s, t.text))
            if t.datum >= s.date and t.datum <= stand + dt.timedelta(days=config.refresh_hint_days):
                if s not in refresh:
                    refresh.append(s)
    calendar = sorted(by_day.items())[: config.calendar_max_days or None]

    sec: dict[str, list[Snapshot]] = defaultdict(list)
    for s in snaps:
        sec[s.sektor_gruppe or s.sektor].append(s)
    sectors = sorted(sec.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    observations = list(config.observations)
    for name, members in sectors:
        if name not in config.beobachte_sektoren:
            continue
        ampeln = {m.ampel for m in members}
        if ampeln <= {"gelb", "gelb-gruen"}:
            observations.append(f"Bei {name} sind alle {len(members)} Werte Gelb oder Gelb-Grün.")
        elif ampeln == {"rot"}:
            observations.append(f"Bei {name} sind alle {len(members)} Werte Rot.")

    return Report(config, stand, snaps, updated_today,
                  [s for s in snaps if s.date > window_start], new, upgrades, downgrades, unchanged,
                  stale, groups, tendenz_gruen, tendenz_rot, comparisons, beginner, calendar,
                  refresh, sectors, observations)


def _group(items, key, order=()):
    g: "OrderedDict[str, list]" = OrderedDict((k, []) for k in order)
    for s in items:
        g.setdefault(key(s), []).append(s)
    return OrderedDict((k, v) for k, v in g.items() if v)


def column_value(report: Report, s: Snapshot, col: str) -> str:
    from .fmt import fmt_kurs
    match col:
        case "ticker":
            return s.ticker
        case "name":
            return s.name
        case "score":
            return fmt_score(s.score)
        case "ampel":
            return report.ampel_text(s)
        case "stand":
            return fmt_date_short(s.date)
        case "kurs":
            return fmt_kurs(s.kurs)
        case "bewertung":
            return s.bewertung or "s. Analyse"
        case "land" | "sektor" | "kurz" | "quartal" | "kommentar":
            v = getattr(s, col)
            if not v and col == "quartal":
                nxt = next((t for t in s.termine if t.datum >= report.stand), None)
                return ("heute" if nxt and nxt.datum == report.stand else fmt_date_short(nxt.datum)) if nxt else "–"
            return v or "–"
    raise ValueError(f"Unbekannte Spalte {col!r}")


COLUMN_TITLES = {"ticker": "Ticker", "name": "Unternehmen", "score": "Score", "ampel": "Ampel",
                 "stand": "Stand", "kurs": "Kurs (Stand)", "bewertung": "Bewertung (grob)",
                 "land": "Land", "sektor": "Sektor", "kurz": "Kurz-Einschätzung", "quartal": "Quartal",
                 "kommentar": "Kommentar"}
