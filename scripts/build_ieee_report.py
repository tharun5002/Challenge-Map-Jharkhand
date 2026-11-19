"""Build docs/IEEE_REPORT.docx as an IEEE conference-format paper.

Source of truth is docs/IEEE_REPORT.md. The script applies the IEEE conference
layout (US Letter, 0.75/1.0/0.625 in margins, two 3.5 in columns), IEEE
typography (Times New Roman 10 pt body, 24 pt title, 8 pt captions and
references), booktabs-style rules for tables, numbered equations, and two
figures generated from the measured results in docs/RESULTS.md.

Run:  .venv313/Scripts/python.exe scripts/build_ieee_report.py
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "IEEE_REPORT.md"
OUTPUT = ROOT / "docs" / "IEEE_REPORT.docx"

BODY_FONT = "Times New Roman"
BODY_SIZE = 10.0
CAPTION_SIZE = 8.0
REFERENCE_SIZE = 8.0
ABSTRACT_SIZE = 9.0
COLUMN_WIDTH = 3.5
FULL_WIDTH = 7.25

AUTHOR = "Tharun Veeraboina"
AFFILIATION = [
    "Department of Computer Science and Engineering (AIML)",
    "Lovely Professional University",
    "Phagwara, Punjab, India",
    "tharunveeraboina33@gmail.com",
]

# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

THRESHOLD_SWEEP = [
    (0.30, 0.034, 0.999, 0.066),
    (0.35, 0.038, 0.999, 0.073),
    (0.40, 0.045, 0.997, 0.086),
    (0.45, 0.058, 0.993, 0.110),
    (0.50, 0.084, 0.987, 0.156),
    (0.55, 0.128, 0.978, 0.226),
    (0.60, 0.193, 0.965, 0.322),
    (0.65, 0.285, 0.949, 0.438),
    (0.70, 0.384, 0.930, 0.544),
    (0.75, 0.503, 0.897, 0.645),
    (0.80, 0.651, 0.851, 0.738),
    (0.85, 0.742, 0.743, 0.743),
    (0.90, 0.794, 0.571, 0.665),
    (0.95, 0.819, 0.265, 0.400),
    (1.00, 0.911, 0.218, 0.352),
]


def make_architecture_figure(path: Path) -> None:
    """Draw the three-tier runtime architecture as a print-quality PNG."""
    fig, ax = plt.subplots(figsize=(3.45, 3.05), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    boxes = [
        (
            0.80,
            "Browser client",
            "React 19 · Next.js 15 App Router · TypeScript\nTailwind CSS · fetch + Bearer JWT",
        ),
        (
            0.585,
            "Next.js application  (:3000)",
            "server components read public briefs\nclient components call /api/v1",
        ),
        (
            0.37,
            "FastAPI service  (:8000)",
            "routers → services → api/store.py\nOpenAPI at /docs",
        ),
        (
            0.155,
            "SQLite store",
            "challenge_map.db\nusers · complaints · challenges · matches",
        ),
    ]
    height = 0.15
    for index, (center_y, title, subtitle) in enumerate(boxes):
        fill = "#f4f4f4" if index % 2 == 0 else "#e8e8e8"
        ax.add_patch(
            FancyBboxPatch(
                (0.03, center_y - height / 2),
                0.94,
                height,
                boxstyle="round,pad=0.006,rounding_size=0.02",
                linewidth=0.8,
                edgecolor="black",
                facecolor=fill,
            )
        )
        ax.text(
            0.5,
            center_y + 0.028,
            title,
            ha="center",
            va="center",
            fontsize=7.2,
            fontweight="bold",
        )
        ax.text(
            0.5,
            center_y - 0.028,
            subtitle,
            ha="center",
            va="center",
            fontsize=5.7,
            linespacing=1.35,
        )

    labels = ["HTTPS / JSON", "JSON + JWT", "SQL (sqlite3)"]
    for index in range(len(boxes) - 1):
        top = boxes[index][0] - height / 2
        bottom = boxes[index + 1][0] + height / 2
        ax.add_patch(
            FancyArrowPatch(
                (0.5, top),
                (0.5, bottom),
                arrowstyle="-|>",
                mutation_scale=7,
                linewidth=0.8,
                color="black",
            )
        )
        ax.text(
            0.52,
            (top + bottom) / 2,
            labels[index],
            ha="left",
            va="center",
            fontsize=5.4,
            style="italic",
        )

    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


def make_threshold_figure(path: Path) -> None:
    """Plot the measured precision/recall/F1 sweep for duplicate pairs."""
    thresholds = [row[0] for row in THRESHOLD_SWEEP]
    precision = [row[1] for row in THRESHOLD_SWEEP]
    recall = [row[2] for row in THRESHOLD_SWEEP]
    f1 = [row[3] for row in THRESHOLD_SWEEP]

    fig, ax = plt.subplots(figsize=(3.45, 2.35), dpi=300)
    ax.plot(thresholds, precision, color="black", linewidth=0.9, marker="o",
            markersize=2.2, label="Precision")
    ax.plot(thresholds, recall, color="#555555", linewidth=0.9, linestyle="--",
            marker="s", markersize=2.0, label="Recall")
    ax.plot(thresholds, f1, color="black", linewidth=0.9, linestyle="-.",
            marker="^", markersize=2.2, label="F1")
    ax.axvline(0.85, color="#999999", linewidth=0.6, linestyle=(0, (2, 2)))
    ax.set_xlabel("Cosine similarity threshold", fontsize=7)
    ax.set_ylabel("Score", fontsize=7)
    ax.set_xlim(0.28, 1.02)
    ax.set_ylim(0, 1.04)
    ax.tick_params(labelsize=6.2, width=0.5, length=2)
    ax.grid(linewidth=0.35, alpha=0.3)
    ax.legend(fontsize=5.8, loc="lower left", frameon=False, handlelength=1.6)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
    fig.tight_layout(pad=0.2)
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Low-level docx helpers
# ---------------------------------------------------------------------------

TBLPR_ORDER = [
    "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
    "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd",
    "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption",
    "tblDescription",
]
TCPR_BEFORE_BORDERS = {
    "shd", "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign",
    "hideMark",
}


def _insert_tblpr_child(tbl_pr, element) -> None:
    tag = element.tag.split("}")[1]
    position = TBLPR_ORDER.index(tag)
    for child in list(tbl_pr):
        child_tag = child.tag.split("}")[1]
        if child_tag in TBLPR_ORDER and TBLPR_ORDER.index(child_tag) > position:
            child.addprevious(element)
            return
    tbl_pr.append(element)


def _set_run(run, size, bold=False, italic=False, name=BODY_FONT, caps=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.small_caps = caps
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    for attribute in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        r_fonts.set(qn(attribute), name)


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*]+?\*)")


def add_inline(paragraph, text, size=BODY_SIZE, bold=False, italic=False,
               caps=False):
    for part in INLINE.split(text):
        if not part:
            continue
        if len(part) > 4 and part.startswith("**") and part.endswith("**"):
            _set_run(paragraph.add_run(part[2:-2]), size, True, italic,
                     caps=caps)
        elif len(part) > 2 and part.startswith("`") and part.endswith("`"):
            # Small caps would turn code identifiers into shouting capitals.
            _set_run(paragraph.add_run(part[1:-1]), size - 1, bold, italic,
                     name="Courier New")
        elif len(part) > 2 and part.startswith("*") and part.endswith("*"):
            _set_run(paragraph.add_run(part[1:-1]), size, bold, True,
                     caps=caps)
        else:
            _set_run(paragraph.add_run(part), size, bold, italic, caps=caps)


def set_columns(section, count: int) -> None:
    sect_pr = section._sectPr
    cols = sect_pr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        grid = sect_pr.find(qn("w:docGrid"))
        if grid is not None:
            grid.addprevious(cols)
        else:
            sect_pr.append(cols)
    cols.set(qn("w:num"), str(count))
    cols.set(qn("w:space"), "360" if count == 2 else "0")
    cols.set(qn("w:equalWidth"), "1")


def apply_page(section) -> None:
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(0.625)
    section.right_margin = Inches(0.625)
    section.header_distance = Inches(0.5)
    section.footer_distance = Inches(0.5)


def table_borders_none(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "none")
        element.set(qn("w:sz"), "0")
        element.set(qn("w:space"), "0")
        borders.append(element)
    _insert_tblpr_child(tbl_pr, borders)

    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    _insert_tblpr_child(tbl_pr, layout)

    margins = OxmlElement("w:tblCellMar")
    for side, width in (("top", 20), ("left", 50), ("bottom", 20),
                        ("right", 50)):
        element = OxmlElement(f"w:{side}")
        element.set(qn("w:w"), str(width))
        element.set(qn("w:type"), "dxa")
        margins.append(element)
    _insert_tblpr_child(tbl_pr, margins)


def cell_borders(cell):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn("w:tcBorders"))
    if borders is not None:
        return borders
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        borders.append(element)
    for child in list(tc_pr):
        if child.tag.split("}")[1] in TCPR_BEFORE_BORDERS:
            child.addprevious(borders)
            return borders
    tc_pr.append(borders)
    return borders


def set_rule(cell, edge: str, size: int) -> None:
    element = cell_borders(cell).find(qn(f"w:{edge}"))
    element.set(qn("w:val"), "single")
    element.set(qn("w:sz"), str(size))
    element.set(qn("w:space"), "0")
    element.set(qn("w:color"), "000000")


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

BULLET = re.compile(r"^[-*]\s+")
NUMBERED = re.compile(r"^(\d+)\.\s+")
TABLE_CAPTION = re.compile(r"^\*\*TABLE\s+([IVX]+)\.\*\*\s*(.*)$")


def parse_blocks(lines: list[str]):
    blocks = []
    index = 0
    while index < len(lines):
        raw = lines[index]
        line = raw.strip()
        if not line or line == "---":
            index += 1
            continue
        if line.startswith("```"):
            index += 1
            code = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index].rstrip())
                index += 1
            index += 1
            blocks.append(("code", "\n".join(code).strip("\n")))
            continue
        if line.startswith("### "):
            blocks.append(("h3", line[4:].strip()))
            index += 1
            continue
        if line.startswith("## "):
            blocks.append(("h2", line[3:].strip()))
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                row = lines[index].strip().strip("|")
                cells = [cell.strip() for cell in row.split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
                    rows.append(cells)
                index += 1
            blocks.append(("table", rows))
            continue
        if BULLET.match(line):
            items = []
            while index < len(lines) and BULLET.match(lines[index].strip()):
                item = BULLET.sub("", lines[index].strip())
                index += 1
                while (index < len(lines) and lines[index].strip()
                       and not BULLET.match(lines[index].strip())
                       and not NUMBERED.match(lines[index].strip())
                       and not lines[index].strip().startswith(("#", "|", "```"))):
                    item += " " + lines[index].strip()
                    index += 1
                items.append(item)
            blocks.append(("ul", items))
            continue
        if NUMBERED.match(line):
            items = []
            while index < len(lines) and NUMBERED.match(lines[index].strip()):
                item = NUMBERED.sub("", lines[index].strip())
                index += 1
                while (index < len(lines) and lines[index].strip()
                       and not NUMBERED.match(lines[index].strip())
                       and not BULLET.match(lines[index].strip())
                       and not lines[index].strip().startswith(("#", "|", "```"))):
                    item += " " + lines[index].strip()
                    index += 1
                items.append(item)
            blocks.append(("ol", items))
            continue

        paragraph = line
        index += 1
        while (index < len(lines) and lines[index].strip()
               and not lines[index].strip().startswith(("#", "|", "```"))
               and not BULLET.match(lines[index].strip())
               and not NUMBERED.match(lines[index].strip())):
            paragraph += " " + lines[index].strip()
            index += 1
        match = TABLE_CAPTION.match(paragraph)
        if match:
            blocks.append(("caption", paragraph))
        else:
            blocks.append(("p", paragraph))
    return attach_captions(blocks)


def attach_captions(blocks):
    """Move each TABLE caption to its table, whichever side it was written on."""
    for index, (kind, payload) in enumerate(blocks):
        if kind != "caption":
            continue
        if index + 1 < len(blocks) and blocks[index + 1][0] == "table":
            table_rows = blocks[index + 1][1]
            blocks[index + 1] = ("table", (table_rows, payload))
            blocks[index] = ("skip", None)
        elif index > 0 and blocks[index - 1][0] == "table":
            table_rows = blocks[index - 1][1]
            blocks[index - 1] = ("table", (table_rows, payload))
            blocks[index] = ("skip", None)
    return [block for block in blocks if block[0] != "skip"]


# ---------------------------------------------------------------------------
# Document construction
# ---------------------------------------------------------------------------

class Paper:
    def __init__(self, figure_dir: Path):
        self.figure_dir = figure_dir
        self.doc = Document()
        self.equation_number = 0
        self.expect_abstract = False
        self.in_references = False
        self.pending_wide = False
        self._setup_styles()

    # -- setup ---------------------------------------------------------
    def _setup_styles(self) -> None:
        style = self.doc.styles["Normal"]
        style.font.name = BODY_FONT
        style.font.size = Pt(BODY_SIZE)
        r_pr = style.element.get_or_add_rPr()
        r_fonts = r_pr.find(qn("w:rFonts"))
        if r_fonts is None:
            r_fonts = OxmlElement("w:rFonts")
            r_pr.insert(0, r_fonts)
        for attribute in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            r_fonts.set(qn(attribute), BODY_FONT)
        paragraph = style.paragraph_format
        paragraph.space_before = Pt(0)
        paragraph.space_after = Pt(0)
        paragraph.line_spacing = 1.0

        first = self.doc.sections[0]
        apply_page(first)
        set_columns(first, 1)

    def start_body_columns(self) -> None:
        section = self.doc.add_section(WD_SECTION.CONTINUOUS)
        apply_page(section)
        set_columns(section, 2)
        self._shrink_break()

    def begin_wide(self) -> None:
        section = self.doc.add_section(WD_SECTION.CONTINUOUS)
        apply_page(section)
        set_columns(section, 1)
        self._shrink_break()

    def end_wide(self) -> None:
        section = self.doc.add_section(WD_SECTION.CONTINUOUS)
        apply_page(section)
        set_columns(section, 2)
        self._shrink_break()

    def _shrink_break(self) -> None:
        paragraph = self.doc.paragraphs[-1]
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = Pt(1)

    # -- blocks --------------------------------------------------------
    def title_block(self, title: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(14)
        _set_run(paragraph.add_run(title), 24)

        name = self.doc.add_paragraph()
        name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        name.paragraph_format.space_after = Pt(4)
        _set_run(name.add_run(AUTHOR), 11)

        for index, line in enumerate(AFFILIATION):
            paragraph = self.doc.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = (
                Pt(14) if index == len(AFFILIATION) - 1 else Pt(0)
            )
            _set_run(paragraph.add_run(line), 10)

    def section_heading(self, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(12)
        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.paragraph_format.keep_with_next = True
        _set_run(paragraph.add_run(text), 10, caps=True)

    def subsection_heading(self, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(9)
        paragraph.paragraph_format.space_after = Pt(3)
        paragraph.paragraph_format.keep_with_next = True
        _set_run(paragraph.add_run(text), 10, italic=True)

    def body(self, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.first_line_indent = Inches(0.2)
        add_inline(paragraph, text, BODY_SIZE)

    def abstract(self, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.space_after = Pt(6)
        _set_run(paragraph.add_run("Abstract\u2014"), ABSTRACT_SIZE,
                 bold=True, italic=True)
        add_inline(paragraph, text, ABSTRACT_SIZE, bold=True)

    def index_terms(self, text: str) -> None:
        body = re.sub(r"^\*\*Index Terms\*\*\s*\u2014\s*", "", text)
        body = body.replace("**Index Terms** \u2014 ", "")
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.space_after = Pt(10)
        _set_run(paragraph.add_run("Index Terms\u2014"), ABSTRACT_SIZE,
                 bold=True, italic=True)
        add_inline(paragraph, body, ABSTRACT_SIZE, bold=True)

    def bullet(self, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.left_indent = Inches(0.24)
        paragraph.paragraph_format.first_line_indent = Inches(-0.16)
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.paragraph_format.tab_stops.add_tab_stop(Inches(0.24))
        _set_run(paragraph.add_run("\u2022\t"), BODY_SIZE)
        add_inline(paragraph, text, BODY_SIZE)

    def numbered(self, number: int, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.left_indent = Inches(0.28)
        paragraph.paragraph_format.first_line_indent = Inches(-0.2)
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.paragraph_format.tab_stops.add_tab_stop(Inches(0.28))
        _set_run(paragraph.add_run(f"{number})\t"), BODY_SIZE)
        add_inline(paragraph, text, BODY_SIZE)

    def reference(self, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        # Left-aligned: justified references stretch around long URLs.
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.left_indent = Inches(0.25)
        paragraph.paragraph_format.first_line_indent = Inches(-0.25)
        paragraph.paragraph_format.space_after = Pt(2.5)
        add_inline(paragraph, text, REFERENCE_SIZE)

    def equation(self, lines: list[str]) -> None:
        self.equation_number += 1
        paragraph = self.doc.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(5)
        paragraph.paragraph_format.space_after = Pt(5)
        paragraph.paragraph_format.keep_together = True
        paragraph.paragraph_format.tab_stops.add_tab_stop(
            Inches(1.75), WD_TAB_ALIGNMENT.CENTER
        )
        paragraph.paragraph_format.tab_stops.add_tab_stop(
            Inches(3.45), WD_TAB_ALIGNMENT.RIGHT
        )
        for position, line in enumerate(lines):
            if position:
                paragraph.add_run().add_break()
            _set_run(paragraph.add_run("\t"), 9)
            for token in re.split(r"([A-Za-z_][A-Za-z_0-9]*)", line):
                if not token:
                    continue
                run = paragraph.add_run(token)
                _set_run(run, 9)
                if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", token):
                    run.italic = True
            if position == len(lines) - 1:
                _set_run(paragraph.add_run(f"\t({self.equation_number})"), 9)

    def code_block(self, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.paragraph_format.left_indent = Inches(0.12)
        paragraph.paragraph_format.space_before = Pt(3)
        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.paragraph_format.keep_together = True
        for position, line in enumerate(text.splitlines()):
            if position:
                paragraph.add_run().add_break()
            _set_run(paragraph.add_run(line), 7.5, name="Courier New")

    def figure(self, filename: str, caption: str, width=COLUMN_WIDTH) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(6)
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.paragraph_format.keep_with_next = True
        paragraph.add_run().add_picture(str(self.figure_dir / filename),
                                        width=Inches(width))

        caption_paragraph = self.doc.add_paragraph()
        caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption_paragraph.paragraph_format.space_after = Pt(9)
        add_inline(caption_paragraph, caption, CAPTION_SIZE)

    def table_caption(self, caption: str) -> tuple[str, str]:
        match = TABLE_CAPTION.match(caption)
        if not match:
            return "", caption
        roman, text = match.group(1), match.group(2)
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(8)
        paragraph.paragraph_format.space_after = Pt(3)
        paragraph.paragraph_format.keep_with_next = True
        _set_run(paragraph.add_run(f"TABLE {roman}"), CAPTION_SIZE, caps=True)
        paragraph.add_run().add_break()
        add_inline(paragraph, text, CAPTION_SIZE, caps=True)
        return roman, text

    def table(self, rows: list[list[str]], caption: str) -> None:
        roman, _ = self.table_caption(caption)
        wide = roman in {"III", "IV"}
        if wide:
            self.begin_wide()
        self._emit_table(rows, roman, FULL_WIDTH if wide else COLUMN_WIDTH)
        if wide:
            self.end_wide()

    def _emit_table(self, rows: list[list[str]], roman: str,
                    total_width: float) -> None:
        columns = max(len(row) for row in rows)
        widths = self._column_widths(roman, columns, total_width)
        table = self.doc.add_table(rows=len(rows), cols=columns)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        table_borders_none(table)

        tbl_pr = table._tbl.tblPr
        tbl_w = tbl_pr.find(qn("w:tblW"))
        if tbl_w is None:
            tbl_w = OxmlElement("w:tblW")
            _insert_tblpr_child(tbl_pr, tbl_w)
        tbl_w.set(qn("w:type"), "dxa")
        tbl_w.set(qn("w:w"), str(int(total_width * 1440)))

        for column, width in zip(table.columns, widths):
            column.width = Inches(width)
        for row in table.rows:
            row.height = None
            tr_pr = row._tr.get_or_add_trPr()
            cant_split = OxmlElement("w:cantSplit")
            tr_pr.append(cant_split)

        header = table.rows[0]
        header_pr = header._tr.get_or_add_trPr()
        repeat = OxmlElement("w:tblHeader")
        repeat.set(qn("w:val"), "true")
        header_pr.append(repeat)

        for row_index, row in enumerate(rows):
            for column_index in range(columns):
                cell = table.cell(row_index, column_index)
                cell.width = Inches(widths[column_index])
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                text = row[column_index] if column_index < len(row) else ""
                paragraph = cell.paragraphs[0]
                paragraph.paragraph_format.space_before = Pt(0)
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.0
                paragraph.alignment = self._cell_alignment(
                    roman, column_index, len(row)
                )
                add_inline(
                    paragraph, text, 7.6,
                    bold=(row_index == 0),
                )

        for cell in table.rows[0].cells:
            set_rule(cell, "top", 8)
            set_rule(cell, "bottom", 4)
        for cell in table.rows[-1].cells:
            set_rule(cell, "bottom", 8)

    @staticmethod
    def _cell_alignment(roman: str, column: int, count: int):
        if roman == "II" and column == 1:
            return WD_ALIGN_PARAGRAPH.LEFT
        if column == 0:
            return WD_ALIGN_PARAGRAPH.LEFT
        return WD_ALIGN_PARAGRAPH.CENTER

    @staticmethod
    def _column_widths(roman: str, count: int, total: float) -> list[float]:
        known = {
            ("I", 2): [1.5, 2.0],
            ("II", 2): [0.85, 2.65],
            ("III", 7): [1.25, 1.2, 1.3, 0.82, 0.82, 0.88, 0.98],
            ("IV", 8): [1.15, 1.05, 0.8, 0.8, 0.8, 0.95, 0.85, 0.85],
        }
        widths = known.get((roman, count))
        if widths is None:
            widths = [total / count] * count
        scale = total / sum(widths)
        return [width * scale for width in widths]

    # -- document ------------------------------------------------------
    def build(self, blocks, title: str) -> None:
        self.title_block(title)
        self.start_body_columns()

        for kind, payload in blocks:
            if kind == "h2":
                heading = payload
                if heading.lower() == "abstract":
                    self.expect_abstract = True
                    continue
                if heading.lower() == "references":
                    self.in_references = True
                    self.section_heading(heading)
                    continue
                self.section_heading(heading)
            elif kind == "h3":
                self.subsection_heading(payload)
            elif kind == "p":
                if self.expect_abstract:
                    self.abstract(payload)
                    self.expect_abstract = False
                elif payload.startswith("**Index Terms**"):
                    self.index_terms(payload)
                elif payload.startswith("**Fig."):
                    continue
                elif self.in_references:
                    self.reference(payload)
                else:
                    self.body(payload)
            elif kind == "ul":
                for item in payload:
                    self.bullet(item)
            elif kind == "ol":
                for number, item in enumerate(payload, start=1):
                    self.numbered(number, item)
            elif kind == "code":
                if "Browser" in payload and "FastAPI" in payload:
                    self.figure(
                        "architecture.png",
                        "**Fig. 1.** Runtime architecture of the implemented "
                        "prototype.",
                    )
                elif payload.lstrip().startswith("priority ="):
                    self.equation([
                        "priority = 100 \u00d7 (0.30\u00b7severity + "
                        "0.25\u00b7affected + 0.20\u00b7volume",
                        "+ 0.15\u00b7district_spread + "
                        "0.10\u00b7recurrence)",
                    ])
                elif payload.lstrip().startswith("match ="):
                    self.equation([
                        "match = 0.40\u00b7tag_overlap + "
                        "0.25\u00b7district_proximity",
                        "+ 0.20\u00b7severity + 0.15\u00b7capacity",
                    ])
                else:
                    self.code_block(payload)
            elif kind == "table":
                rows, caption = payload
                self.table(rows, caption)
                if caption.startswith("**TABLE IV"):
                    self.figure(
                        "threshold_sweep.png",
                        "**Fig. 2.** Duplicate-pair precision, recall and F1 "
                        "versus the cosine threshold on the 1,500 injected "
                        "pairs (district-blocked top-5 candidates). Best F1 = "
                        "0.743 at 0.85; the deployed default is 0.86.",
                    )

        # A trailing continuous break makes Word balance the last page's
        # columns, the way an IEEE paper ends rather than filling one column.
        final = self.doc.add_section(WD_SECTION.CONTINUOUS)
        apply_page(final)
        set_columns(final, 1)
        self._shrink_break()

    def save(self, path: Path) -> None:
        properties = self.doc.core_properties
        properties.title = (
            "ChallengeMap: An Evidence-Grounded Pipeline for Turning Citizen "
            "Complaints into Ranked Challenge Briefs"
        )
        properties.author = AUTHOR
        properties.subject = "IEEE conference paper"
        properties.keywords = (
            "civic technology; complaint analytics; duplicate detection; "
            "topic discovery; multilingual NLP; explainable ranking"
        )
        properties.comments = "Generated in IEEE conference paper format."
        self.doc.save(path)


def main() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    title_line = next(line for line in lines if line.startswith("# "))
    title = title_line[2:].strip()

    abstract_index = next(
        index for index, line in enumerate(lines)
        if line.strip().lower() == "## abstract"
    )
    body_blocks = parse_blocks(lines[abstract_index:])

    with tempfile.TemporaryDirectory() as temp:
        figure_dir = Path(temp)
        make_architecture_figure(figure_dir / "architecture.png")
        make_threshold_figure(figure_dir / "threshold_sweep.png")

        paper = Paper(figure_dir)
        paper.build(body_blocks, title)
        paper.save(OUTPUT)

    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
