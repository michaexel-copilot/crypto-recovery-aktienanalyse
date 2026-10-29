"""Renderer für Markdown, HTML und PDF."""
from __future__ import annotations

import html
from pathlib import Path

from .document import Block, Bullets, Callout, Heading, Para, Table

AMPEL_COLORS = {"gruen": "#2e9e4f", "gelb-gruen": "#9bbf2e", "gelb": "#e0b000", "rot": "#d23c3c"}


# ---------------------------------------------------------------- Markdown
def render_markdown(title: str, blocks: list[Block], footer: str = "") -> str:
    out = [f"# {title}", ""]
    for b in blocks:
        match b:
            case Heading():
                out += ["#" * b.level + " " + b.text, ""]
            case Para():
                out += [f"`{b.text}`" if b.style == "mono" else (f"*{b.text}*" if b.style != "normal" else b.text), ""]
            case Callout():
                out += [f"> {line}  " for line in b.lines]
                out += [f"> - {x}" for x in b.bullets]
                out.append("")
            case Bullets():
                if b.title:
                    out += [f"**{b.title}**", ""]
                out += [(f"{i}. " if b.ordered else "- ") + x for i, x in enumerate(b.items, 1)]
                out.append("")
            case Table():
                esc = lambda v: v.replace("|", "\\|")
                out.append("| " + " | ".join(b.header) + " |")
                out.append("|" + "---|" * len(b.header))
                out += ["| " + " | ".join(esc(v) for v in row) + " |" for row in b.rows]
                out.append("")
    if footer:
        out += ["---", f"*{footer}*", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- HTML
HTML_CSS = """
:root{--bg:#fff;--fg:#1d1f23;--muted:#666;--line:#e3e5e8;--box:#f4f6f9;--warn:#fff6e0;--head:#25344d}
@media (prefers-color-scheme:dark){:root{--bg:#16181c;--fg:#e6e8eb;--muted:#9aa0a6;--line:#2c3036;--box:#1f2329;--warn:#2d2717;--head:#c9d6ea}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;padding:24px 16px}
main{max-width:1150px;margin:0 auto}
h1{margin:0 0 4px;font-size:26px}h2{color:var(--head);border-bottom:2px solid var(--line);padding-bottom:4px;margin-top:32px}
h3{margin:20px 0 6px}.muted{color:var(--muted)}.small{font-size:13px;color:var(--muted)}
.mono{font-family:ui-monospace,monospace;font-size:13px}
.callout{background:var(--box);border-left:4px solid #5b7db8;padding:10px 14px;margin:12px 0;border-radius:4px}
.callout.warn{background:var(--warn);border-color:#d99a00}.callout p{margin:4px 0}
.tbl{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--box);position:sticky;top:0}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle}
footer{margin-top:40px;font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:8px}
"""


def render_html(title: str, blocks: list[Block], footer: str = "") -> str:
    e = html.escape
    body = [f"<h1>{e(title)}</h1>"]
    for b in blocks:
        match b:
            case Heading():
                body.append(f"<h{b.level}>{e(b.text)}</h{b.level}>")
            case Para():
                body.append(f'<p class="{b.style}">{e(b.text)}</p>')
            case Callout():
                inner = "".join(f"<p>{e(x)}</p>" for x in b.lines)
                if b.bullets:
                    inner += "<ul>" + "".join(f"<li>{e(x)}</li>" for x in b.bullets) + "</ul>"
                body.append(f'<div class="callout {b.tone}">{inner}</div>')
            case Bullets():
                tag = "ol" if b.ordered else "ul"
                if b.title:
                    body.append(f"<p><strong>{_dotted(b.title)}</strong></p>")
                body.append(f"<{tag}>" + "".join(f"<li>{e(x)}</li>" for x in b.items) + f"</{tag}>")
            case Table():
                head = "".join(f"<th>{e(h)}</th>" for h in b.header)
                rows = []
                for i, row in enumerate(b.rows):
                    a = b.ampel[i] if i < len(b.ampel) else None
                    cells = []
                    for j, v in enumerate(row):
                        dot = (f'<span class="dot" style="background:{AMPEL_COLORS[a]}"></span>'
                               if a and (j == b.ampel_col or (b.ampel_col is None and j == 0)) else "")
                        cells.append(f"<td>{dot}{e(v)}</td>")
                    rows.append("<tr>" + "".join(cells) + "</tr>")
                body.append(f'<div class="tbl"><table><thead><tr>{head}</tr></thead>'
                            f'<tbody>{"".join(rows)}</tbody></table></div>')
    if footer:
        body.append(f"<footer>{e(footer)}</footer>")
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{e(title)}</title><style>{HTML_CSS}</style></head>"
            f"<body><main>{''.join(body)}</main></body></html>")


def _dotted(title: str) -> str:
    """Färbt das führende ● in Ampel-Überschriften."""
    e = html.escape
    for key, word in (("gruen", "GRÜN"), ("gelb", "GELB"), ("rot", "ROT")):
        if title.startswith(f"● {word}"):
            return f'<span class="dot" style="background:{AMPEL_COLORS[key]}"></span>{e(title[2:])}'
    return e(title)


# ---------------------------------------------------------------- PDF
FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
]


def _register_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for regular, bold in FONT_CANDIDATES:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("ReportSans", regular))
            pdfmetrics.registerFont(TTFont("ReportSans-Bold", bold))
            return "ReportSans", "ReportSans-Bold"
    return "Helvetica", "Helvetica-Bold"  # Fallback ohne Unicode-Sonderzeichen wie ● oder →


def render_pdf(title: str, blocks: list[Block], path: Path, footer: str = "", stand_text: str = "") -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate,
                                    Spacer, Table as RLTable, TableStyle)

    font, bold = _register_fonts()
    st = {
        "h1": ParagraphStyle("h1", fontName=bold, fontSize=17, leading=21, spaceAfter=4),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=12.5, leading=16, spaceBefore=10, spaceAfter=5,
                             textColor=colors.HexColor("#25344d")),
        "h3": ParagraphStyle("h3", fontName=bold, fontSize=10.5, leading=13, spaceBefore=6, spaceAfter=3),
        "normal": ParagraphStyle("n", fontName=font, fontSize=8.5, leading=11, alignment=TA_LEFT),
        "small": ParagraphStyle("s", fontName=font, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#555")),
        "muted": ParagraphStyle("m", fontName=font, fontSize=9, leading=11.5, textColor=colors.HexColor("#444")),
        "mono": ParagraphStyle("mo", fontName="Courier", fontSize=8, leading=10),
        "cell": ParagraphStyle("c", fontName=font, fontSize=7.3, leading=9),
        "cellb": ParagraphStyle("cb", fontName=bold, fontSize=7.3, leading=9),
    }
    e = html.escape
    pagesize = landscape(A4)
    width = pagesize[0] - 24 * mm
    story = [Paragraph(e(title), st["h1"])]

    for b in blocks:
        match b:
            case Heading():
                story.append(Paragraph(e(b.text), st[f"h{min(b.level, 3)}"]))
            case Para():
                story.append(Paragraph(e(b.text), st.get(b.style, st["normal"])))
            case Callout():
                inner = [Paragraph(e(x), st["normal"]) for x in b.lines]
                inner += [Paragraph("• " + e(x), st["normal"]) for x in b.bullets]
                bg = "#fff6e0" if b.tone == "warn" else "#eef2f8"
                box = RLTable([[inner]], colWidths=[width])
                box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
                                         ("LINEBEFORE", (0, 0), (0, -1), 2.5, colors.HexColor("#5b7db8")),
                                         ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5),
                                         ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
                story += [Spacer(1, 4), box, Spacer(1, 4)]
            case Bullets():
                items = [ListItem(Paragraph(e(x), st["normal"]), leftIndent=10) for x in b.items]
                lst = ListFlowable(items, bulletType="1" if b.ordered else "bullet", start=1 if b.ordered else "•",
                                   bulletFontName=font, bulletFontSize=8, leftIndent=12)
                parts = [lst]
                if b.title:
                    parts.insert(0, Paragraph(_pdf_dotted(b.title, bold), st["h3"]))
                story.append(KeepTogether(parts))
            case Table():
                data = [[Paragraph(e(h), st["cellb"]) for h in b.header]]
                data += [[Paragraph(e(v), st["cell"]) for v in row] for row in b.rows]
                widths = b.widths or [1] * len(b.header)
                total = sum(widths)
                t = RLTable(data, colWidths=[width * w / total for w in widths], repeatRows=1)
                style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6ebf2")),
                         ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d0d4da")),
                         ("VALIGN", (0, 0), (-1, -1), "TOP"),
                         ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
                col = b.ampel_col if b.ampel_col is not None else 0
                for i, a in enumerate(b.ampel, 1):
                    if a:
                        style.append(("LINEBEFORE", (col, i), (col, i), 3, colors.HexColor(AMPEL_COLORS[a])))
                t.setStyle(TableStyle(style))
                story += [t, Spacer(1, 6)]

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor("#777"))
        canvas.drawString(12 * mm, 8 * mm, footer)
        canvas.drawRightString(pagesize[0] - 12 * mm, 8 * mm, f"Seite {doc.page} · {stand_text}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=pagesize, leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=15 * mm, title=title,
                            author="aktienreport", subject="Aktienanalysen – Zusammenfassung")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def _pdf_dotted(title: str, bold: str) -> str:
    e = html.escape
    for key, word in (("gruen", "GRÜN"), ("gelb", "GELB"), ("rot", "ROT")):
        if title.startswith(f"● {word}"):
            return f'<font color="{AMPEL_COLORS[key]}">●</font>{e(title[1:])}'
    return e(title)
