"""Ablage der Analysen: data/aktien/<TICKER>/<YYYY-MM-DD>.yaml

Jede Datei ist ein Snapshot. Ältere Dateien bleiben als Historie erhalten;
für die aktuelle Einschätzung wird immer die jüngste Datei verwendet.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from .models import Snapshot


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def tickers(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and any(p.glob("*.yaml")))

    def history(self, ticker: str, until: dt.date | None = None) -> list[Snapshot]:
        """Alle Snapshots einer Aktie, älteste zuerst."""
        snaps = []
        for f in sorted((self.root / ticker).glob("*.yaml")):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            snap = Snapshot.from_dict(data)
            if snap.ticker != ticker:
                raise ValueError(f"{f}: Ticker {snap.ticker!r} passt nicht zum Ordner {ticker!r}")
            if until is None or snap.date <= until:
                snaps.append(snap)
        return sorted(snaps, key=lambda s: s.date)

    def latest(self, until: dt.date | None = None) -> dict[str, Snapshot]:
        out = {}
        for t in self.tickers():
            h = self.history(t, until)
            if h:
                out[t] = h[-1]
        return out

    def save(self, snap: Snapshot) -> Path:
        path = self.root / snap.ticker / f"{snap.date.isoformat()}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(snap.to_dict(), allow_unicode=True, sort_keys=False, width=200),
                        encoding="utf-8")
        return path
