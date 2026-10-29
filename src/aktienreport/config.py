"""Report-Konfiguration (config/report.yaml)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ComparisonConfig:
    title: str
    tag: str
    columns: list[str] = field(default_factory=lambda: ["ticker", "score", "stand", "kommentar"])
    text: str | None = None
    table: bool = True


@dataclass
class ReportConfig:
    title: str = "Zusammenfassung – Alle {n} Aktien"
    footer: str = "Aktienanalysen – Zusammenfassung · Keine Anlageberatung · KI-erstellt, Zahlen selbst prüfen"
    disclaimer: str = "Keine Anlageberatung. Score und Ampel sind nur Analyse-Indikatoren, kein Kaufsignal."
    transparenz: str | None = None
    update_window_days: int = 3
    max_age_days: int = 2
    refresh_hint_days: int = 1
    calendar_max_days: int = 0
    wochen_ereignisse: list[str] = field(default_factory=list)
    notizen: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    beobachte_sektoren: list[str] = field(default_factory=list)
    comparisons: list[ComparisonConfig] = field(default_factory=list)
    sparplan_gruppen: dict[str, list[str]] = field(default_factory=dict)
    risiko_order: list[str] = field(default_factory=list)
    etf_hinweis: str | None = None
    hinweise: list[str] = field(default_factory=list)
    details_pfad: str | None = None

    def sparplan_gruppe(self, sektor_gruppe: str | None) -> str:
        for name, sektoren in self.sparplan_gruppen.items():
            if sektor_gruppe in sektoren:
                return name
        return "Weitere"

    def sparplan_order(self) -> list[str]:
        return [*self.sparplan_gruppen, "Weitere"]

    @classmethod
    def load(cls, path: Path | str | None) -> "ReportConfig":
        if path is None or not Path(path).exists():
            return cls()
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        data["comparisons"] = [ComparisonConfig(**c) for c in data.get("comparisons", [])]
        return cls(**data)
