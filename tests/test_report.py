import datetime as dt

import pytest
import yaml

from aktienreport.analysis import build_report
from aktienreport.cli import main
from aktienreport.config import ComparisonConfig, ReportConfig
from aktienreport.document import build_document
from aktienreport.fmt import fmt_kurs, fmt_num, fmt_score
from aktienreport.models import Kurs, Snapshot
from aktienreport.render import render_html, render_markdown, render_pdf
from aktienreport.store import Store

STAND = dt.date(2026, 10, 29)


def snap(ticker, date, score, ampel="gelb", **kw):
    base = dict(ticker=ticker, name=ticker.title(), date=date, score=score, ampel=ampel,
                sektor="Test", sektor_gruppe=kw.pop("gruppe", "Gruppe A"), kurz=f"{ticker} kurz")
    base.update(kw)
    return Snapshot.from_dict(base)


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "aktien")
    s.save(snap("AAA", "2026-10-20", 6.0))
    s.save(snap("AAA", "2026-10-29", 7.5, tendenz="gruen", aenderungsgrund="starkes Quartal", tags=["vgl"]))
    s.save(snap("BBB", "2026-10-27", 7.0, "gruen", anfaenger="geeignet", tags=["vgl"],
                termine=[{"datum": "2026-10-29", "text": "Q3"}]))
    s.save(snap("CCC", "2026-10-20", 5.0))
    s.save(snap("CCC", "2026-10-29", 4.0, risiko="Spekulativ", anfaenger="ungeeignet",
                aenderungsgrund="Prognose gesenkt"))
    s.save(snap("DDD", "2026-10-29", 2.0, "rot", aufgenommen="2026-10-29", gruppe="Gruppe B",
                kurs={"wert": 1925, "waehrung": "GBp"}))
    s.save(snap("EEE", "2026-10-29", 5.0))
    s.save(snap("EEE", "2026-10-10", 5.0))
    return s


@pytest.fixture
def config():
    return ReportConfig(comparisons=[ComparisonConfig("Vergleich", "vgl", ["ticker", "score", "quartal"])],
                        beobachte_sektoren=["Gruppe B"])


def test_ranking_and_latest_snapshot(store, config):
    r = build_report(store, config)
    assert r.stand == STAND
    assert [s.ticker for s in r.ranking] == ["AAA", "BBB", "EEE", "CCC", "DDD"]
    assert r.ranking[0].score == 7.5


def test_changes_new_and_unchanged(store, config):
    r = build_report(store, config)
    assert [c.text() for c in r.upgrades] == ["AAA 6→7,5 (starkes Quartal)"]
    assert [c.text() for c in r.downgrades] == ["CCC 5→4 (Prognose gesenkt)"]
    assert [s.ticker for s in r.new] == ["DDD"]
    assert [s.ticker for s in r.unchanged] == ["EEE"]


def test_stand_in_the_past_ignores_newer_snapshots(store, config):
    r = build_report(store, config, dt.date(2026, 10, 27))
    assert {s.ticker: s.score for s in r.ranking} == {"AAA": 6.0, "BBB": 7.0, "CCC": 5.0, "EEE": 5.0}


def test_groups_calendar_and_refresh(store, config):
    r = build_report(store, config)
    assert [s.ticker for s in r.groups["gruen"]] == ["BBB"]
    assert [s.ticker for s in r.tendenz_gruen] == ["AAA"]
    assert r.calendar[0][0] == STAND
    assert [s.ticker for s in r.refresh_hint] == ["BBB"]
    assert r.stale == []  # BBB ist genau max_age_days (2) alt
    config.max_age_days = 1
    assert [s.ticker for s in build_report(store, config).stale] == ["BBB"]
    assert r.observations == ["Bei Gruppe B sind alle 1 Werte Rot."]


def test_renderers(store, config, tmp_path):
    title, blocks = build_document(build_report(store, config))
    md = render_markdown(title, blocks)
    assert "Alle 5 Aktien" in md and "| 1 | AAA |" in md and "Heraufgestuft: AAA 6→7,5" in md
    assert "| BBB | 7 | heute |" in md  # Quartal-Spalte fällt auf nächsten Termin zurück
    html = render_html(title, blocks)
    assert html.startswith("<!doctype html>") and "AAA" in html
    pdf = tmp_path / "r.pdf"
    render_pdf(title, blocks, pdf)
    assert pdf.read_bytes().startswith(b"%PDF")


def test_formatting():
    assert fmt_score(7.0) == "7" and fmt_score(6.5) == "6,5"
    assert fmt_num(1925) == "1.925" and fmt_num(436.87) == "436,87"
    assert fmt_kurs(Kurs(1925, "GBp")) == "1.925 p"
    assert fmt_kurs(Kurs(49, "EUR", hinweis="ca.")) == "~49 EUR"


def test_validation():
    with pytest.raises(ValueError):
        snap("X", "2026-10-29", 11)
    with pytest.raises(ValueError):
        snap("X", "2026-10-29", 5, "blau")
    with pytest.raises(ValueError):
        Snapshot.from_dict({"ticker": "X", "name": "X", "date": "2026-10-29", "score": 5, "ampel": "gelb",
                            "sektor": "S", "tippfehler": 1})


def test_cli_update_and_build(store, tmp_path, capsys):
    data = str(store.root)
    assert main(["--data", data, "update", "EEE", "--datum", "2026-10-30", "--score", "5,5",
                 "--grund", "Test", "--kurs", "12,5 USD", "--termin", "2026-11-05:Q3"]) == 0
    saved = yaml.safe_load((store.root / "EEE" / "2026-10-30.yaml").read_text())
    assert saved["score"] == 5.5 and saved["kurs"]["wert"] == 12.5 and saved["aenderungsgrund"] == "Test"
    assert main(["--data", data, "update", "NEW", "--neu", "--name", "Neu AG", "--score", "6",
                 "--ampel", "gelb", "--sektor", "Test", "--datum", "2026-10-30"]) == 0
    out = tmp_path / "out"
    assert main(["--data", data, "--config", str(tmp_path / "fehlt.yaml"), "build", "--out", str(out),
                 "--format", "md,html"]) == 0
    md = (out / "zusammenfassung-2026-10-30.md").read_text()
    assert "Neu aufgenommen (30.10.): NEW Neu AG" in md
    assert "EEE 5→5,5 (Test)" in md


def test_seed_data_is_valid():
    """Die mitgelieferten Daten aus dem Beispiel-PDF müssen sich vollständig laden lassen."""
    from pathlib import Path
    root = Path(__file__).parents[1]
    r = build_report(Store(root / "data" / "aktien"), ReportConfig.load(root / "config" / "report.yaml"),
                     STAND)
    assert r.count == 86
    assert r.ranking[0].ticker == "MSFT"
    assert len(r.groups["rot"]) == 7
