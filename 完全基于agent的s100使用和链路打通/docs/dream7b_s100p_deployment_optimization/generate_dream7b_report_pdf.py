from __future__ import annotations

import html
import re
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BASE_DIR = Path(__file__).resolve().parent
SOURCE_MD = BASE_DIR / "dream7b_s100p_deployment_report_2026-06-10.md"
OUTPUT_PDF = BASE_DIR / "dream7b_s100p_deployment_report_2026-06-10.pdf"


def register_fonts() -> tuple[str, str]:
    candidates = [
        ("CJK", Path(r"C:\Windows\Fonts\simhei.ttf")),
        ("CJK", Path(r"C:\Windows\Fonts\msyh.ttc")),
        ("CJK", Path(r"C:\Windows\Fonts\simsun.ttc")),
    ]
    bold_candidates = [
        ("CJKBold", Path(r"C:\Windows\Fonts\msyhbd.ttc")),
        ("CJKBold", Path(r"C:\Windows\Fonts\simhei.ttf")),
        ("CJKBold", Path(r"C:\Windows\Fonts\simsunb.ttf")),
    ]

    body = "Helvetica"
    bold = "Helvetica-Bold"
    for name, path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
            body = name
            break
    for name, path in bold_candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
            bold = name
            break
    return body, bold


FONT, FONT_BOLD = register_fonts()


def make_styles():
    sample = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "TitleCJK",
            parent=sample["Title"],
            fontName=FONT_BOLD,
            fontSize=24,
            leading=32,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#102033"),
            spaceAfter=8 * mm,
            wordWrap="CJK",
        ),
        "subtitle": ParagraphStyle(
            "SubtitleCJK",
            parent=sample["BodyText"],
            fontName=FONT,
            fontSize=10.5,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#425466"),
            wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "Heading2CJK",
            parent=sample["Heading2"],
            fontName=FONT_BOLD,
            fontSize=15,
            leading=21,
            textColor=colors.HexColor("#123A5A"),
            spaceBefore=7 * mm,
            spaceAfter=3 * mm,
            wordWrap="CJK",
        ),
        "h3": ParagraphStyle(
            "Heading3CJK",
            parent=sample["Heading3"],
            fontName=FONT_BOLD,
            fontSize=12.5,
            leading=18,
            textColor=colors.HexColor("#2E5E7E"),
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
            wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "BodyCJK",
            parent=sample["BodyText"],
            fontName=FONT,
            fontSize=10,
            leading=16,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#1D2733"),
            spaceAfter=2.5 * mm,
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "SmallCJK",
            parent=sample["BodyText"],
            fontName=FONT,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#425466"),
            wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "TableCJK",
            parent=sample["BodyText"],
            fontName=FONT,
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#1D2733"),
            wordWrap="CJK",
        ),
        "table_head": ParagraphStyle(
            "TableHeadCJK",
            parent=sample["BodyText"],
            fontName=FONT_BOLD,
            fontSize=8.5,
            leading=11.5,
            textColor=colors.white,
            wordWrap="CJK",
        ),
        "code": ParagraphStyle(
            "Code",
            parent=sample["Code"],
            fontName="Courier",
            fontSize=7.2,
            leading=10,
            textColor=colors.HexColor("#203040"),
            backColor=colors.HexColor("#F4F7FA"),
            leftIndent=3 * mm,
            rightIndent=3 * mm,
            spaceBefore=1 * mm,
            spaceAfter=3 * mm,
        ),
        "bullet": ParagraphStyle(
            "BulletCJK",
            parent=sample["BodyText"],
            fontName=FONT,
            fontSize=9.8,
            leading=15,
            leftIndent=7 * mm,
            firstLineIndent=-4 * mm,
            textColor=colors.HexColor("#1D2733"),
            spaceAfter=1.5 * mm,
            wordWrap="CJK",
        ),
    }
    return styles


STYLES = make_styles()


def sanitize_inline(text: str) -> str:
    text = html.escape(text)

    def code_repl(match: re.Match[str]) -> str:
        value = match.group(1)
        font = "Courier" if value.isascii() else FONT
        return f"<font name='{font}'>{value}</font>"

    text = re.sub(r"`([^`]+)`", code_repl, text)
    text = re.sub(
        r"(https://[^\s<]+)",
        r"<link href='\1' color='#0B63B6'>\1</link>",
        text,
    )
    return text


def wrap_code_block(code: str) -> str:
    wrapped: list[str] = []
    for line in code.rstrip("\n").splitlines():
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(
            textwrap.wrap(
                line,
                width=88,
                replace_whitespace=False,
                drop_whitespace=False,
                break_long_words=True,
                break_on_hyphens=False,
            )
        )
    return "\n".join(wrapped)


def parse_table(lines: list[str], start: int) -> tuple[Table, int]:
    rows: list[list[str]] = []
    i = start
    while i < len(lines):
        line = lines[i].strip()
        if not (line.startswith("|") and line.endswith("|")):
            break
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells):
            i += 1
            continue
        rows.append(cells)
        i += 1

    max_cols = max(len(r) for r in rows)
    norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]
    data = []
    for r_idx, row in enumerate(norm_rows):
        style = STYLES["table_head"] if r_idx == 0 else STYLES["table"]
        data.append([Paragraph(sanitize_inline(cell), style) for cell in row])

    width = A4[0] - 40 * mm
    if max_cols == 2:
        col_widths = [width * 0.32, width * 0.68]
    elif max_cols == 3:
        col_widths = [width * 0.24, width * 0.22, width * 0.54]
    else:
        col_widths = [width / max_cols] * max_cols

    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123A5A")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D3DF")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table, i


def markdown_to_flowables(md: str):
    flow = []
    lines = md.splitlines()
    i = 0
    paragraph_buf: list[str] = []

    def flush_para():
        if paragraph_buf:
            text = " ".join(x.strip() for x in paragraph_buf if x.strip())
            if text:
                flow.append(Paragraph(sanitize_inline(text), STYLES["body"]))
            paragraph_buf.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            flow.append(Spacer(1, 1.2 * mm))
            i += 1
            continue

        if stripped.startswith("```"):
            flush_para()
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            flow.append(Preformatted(wrap_code_block("\n".join(code_lines)), STYLES["code"]))
            continue

        if stripped.startswith("|") and stripped.endswith("|") and i + 1 < len(lines):
            flush_para()
            table, i = parse_table(lines, i)
            flow.append(table)
            flow.append(Spacer(1, 4 * mm))
            continue

        if stripped.startswith("# "):
            flush_para()
            title = stripped[2:].strip()
            flow.append(Paragraph(sanitize_inline(title), STYLES["title"]))
            continue_text = [
                "S100P 默认服务部署、性能优化与工具链卡点汇报",
                "状态：default_deployable_ready = True；rollback 已验证；192 请求长稳态无失败",
            ]
            for t in continue_text:
                flow.append(Paragraph(sanitize_inline(t), STYLES["subtitle"]))
            flow.append(Spacer(1, 6 * mm))
            i += 1
            continue

        if stripped.startswith("## "):
            flush_para()
            flow.append(Paragraph(sanitize_inline(stripped[3:].strip()), STYLES["h2"]))
            i += 1
            continue

        if stripped.startswith("### "):
            flush_para()
            flow.append(Paragraph(sanitize_inline(stripped[4:].strip()), STYLES["h3"]))
            i += 1
            continue

        if stripped.startswith("- "):
            flush_para()
            flow.append(Paragraph("- " + sanitize_inline(stripped[2:].strip()), STYLES["bullet"]))
            i += 1
            continue

        if re.match(r"^\d+\.\s+", stripped):
            flush_para()
            flow.append(Paragraph(sanitize_inline(stripped), STYLES["bullet"]))
            i += 1
            continue

        paragraph_buf.append(line)
        i += 1

    flush_para()
    return flow


def draw_footer(canvas, doc):
    canvas.saveState()
    width, _height = A4
    canvas.setFont(FONT, 8)
    canvas.setFillColor(colors.HexColor("#6B7785"))
    canvas.drawString(20 * mm, 12 * mm, "Dream 7B S100P deployment report")
    canvas.drawRightString(width - 20 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf():
    md = SOURCE_MD.read_text(encoding="utf-8")
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=13 * mm,
        title="Dream 7B S100P 部署优化汇报",
        author="OpenClaw S100P project",
    )
    flow = markdown_to_flowables(md)
    doc.build(flow, onFirstPage=draw_footer, onLaterPages=draw_footer)


if __name__ == "__main__":
    build_pdf()
    print(OUTPUT_PDF)
