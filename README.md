# Crypto Recovery – Aktienanalyse

`aktienreport` erzeugt aus einzelnen Aktienanalysen eine **Zusammenfassung** als PDF, HTML und Markdown,
nach dem Vorbild der Datei *Aktien_ZUSAMMENFASSUNG* vom 29.10.2026:

- Update-Kasten: was aktualisiert wurde, Score-Herauf- und -Herabstufungen mit Begründung, Neuaufnahmen, veraltete Analysen
- Ranking aller Aktien nach Score mit Ampel (Grün / Gelb-Grün / Gelb / Rot) und Tendenz (→ Grün / → Rot)
- Gruppierung nach Ampel
- Quervergleiche (Mag 7, Rüstung, Halbleiter, Pharma, China …), frei konfigurierbar über Tags
- Anfänger-Orientierung (geeignet / Sparplan / ungeeignet nach Risiko-Kategorie)
- Kalender der anstehenden Termine plus Hinweis, welche Aktien nach ihren Zahlen aufgefrischt werden sollten
- Sektor-Verteilung, Beobachtungen, Hinweise und Disclaimer

> Keine Anlageberatung. Score und Ampel sind Analyse-Indikatoren, keine Kaufsignale.

## Installation

```bash
pip install -e ".[dev]"          # optional: ".[markt]" für Kursabfragen über Yahoo Finance
```

## Benutzung

```bash
aktienreport build                         # reports/zusammenfassung-<stand>.{pdf,html,md}
aktienreport build --stand 2026-10-27      # Report zu einem früheren Stichtag
aktienreport build --format md             # nur Markdown
aktienreport list                          # Ranking im Terminal
aktienreport show MSFT                     # Historie einer Aktie
aktienreport check                         # Plausibilitätsprüfung der Daten
```

Neue Analyse eintragen (übernimmt alle Felder vom letzten Snapshot, nur Änderungen angeben):

```bash
aktienreport update AMZN --score 6.5 --kurz "AWS +25 %, Prognose angehoben" --grund "AWS beschleunigt" --kurs "261 USD"
```

Neue Aktie aufnehmen:

```bash
aktienreport update SAP --neu --name SAP --score 6.5 --ampel gelb --sektor "Software (DE)" --sektor-gruppe "Big Tech / Software / Cloud / Security" --land DE --kurz "Cloud +27 %" --anfaenger sparplan --termin "2027-01-28:Q4"
```

Kurse aktualisieren (braucht Internetzugang zu Yahoo Finance):

```bash
aktienreport kurse MSFT NVDA NESN
```

## Daten

Jede Analyse ist ein YAML-Snapshot unter `data/aktien/<TICKER>/<YYYY-MM-DD>.yaml`. Ältere Snapshots bleiben als
Historie erhalten; der Report nimmt pro Aktie immer den jüngsten Snapshot bis zum Stichtag und vergleicht ihn mit
dem vorherigen, um Score-Änderungen zu erkennen.

```yaml
ticker: MSFT
name: Microsoft
date: '2026-10-29'
score: 7.5                # 0–10
ampel: gelb               # gruen | gelb-gruen | gelb | rot
tendenz: gruen            # optional, erscheint als "GELB (→ Grün)"
sektor: Software/Cloud
sektor_gruppe: Big Tech / Software / Cloud / Security
kurz: Azure +48 %, Prognose 49–50 %
kurs: {wert: 531, waehrung: USD, datum: '2026-10-28'}
bewertung: KGV ~30        # für Quervergleiche
quartal: Azure +48 %      # Kennzahl des letzten Quartals
kommentar: OpenAI-Abhängigkeit, FCF −27 %
aenderungsgrund: 'neuer Spitzenreiter: Azure +48 %'
anfaenger: sparplan       # geeignet | sparplan | ungeeignet
risiko: Hoch bewertet     # Kategorie für "eher ungeeignet"
aufgenommen: '2026-10-29' # setzt "Neu aufgenommen"
yahoo: MSFT               # optional abweichendes Yahoo-Symbol
tags: [mag7]              # steuert die Quervergleiche
termine:
  - {datum: '2027-01-28', text: Q2-Zahlen}
```

Die mitgelieferten 86 Aktien stammen aus der Beispiel-Zusammenfassung vom 29.10.2026 (Stand der dortigen Angaben,
Kurse teils nur Spannen). Für die Score-Änderungen dieses Stichtags sind die Vorgänger-Snapshots enthalten.

## Konfiguration

`config/report.yaml` enthält alle Texte und die Struktur: Titel, Disclaimer, Transparenzhinweis, Ereignisse der
Woche, Notizen, Quervergleiche (Tag + Spalten + Text), Sparplan-Gruppen, Reihenfolge der Risiko-Kategorien,
Hinweise sowie Schwellen wie `max_age_days` und `update_window_days`.

## Aufbau

| Modul | Aufgabe |
|---|---|
| `models.py` | Snapshot-Datenmodell mit Validierung |
| `store.py` | Laden/Speichern der Snapshots, Historie |
| `analysis.py` | Ranking, Änderungen, Gruppen, Vergleiche, Kalender, Sektoren |
| `document.py` | formatneutrale Dokumentstruktur |
| `render.py` | Markdown-, HTML- und PDF-Ausgabe (ReportLab) |
| `market.py` | optionale Kursabfrage (yfinance) |
| `cli.py` | Kommandozeile |

Tests: `pytest`
