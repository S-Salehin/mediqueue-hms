"""Build the final FYDP report from the supplied university template.

The source template is never modified. The script reuses its document package and
styles, clears the sample subject matter, and writes the implemented project report.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "FYDP Tamplate.docx"
OUT_DIR = ROOT / "deliverables"
OUT_FILE = OUT_DIR / "Hospital Management System Final Report Revised.docx"
DIAGRAM_DIR = ROOT / "report_assets" / "diagrams"
SCREENSHOT_DIR = ROOT / "report_assets" / "screenshots"

TITLE = "Hospital Management System: A Web Application"
SUBTITLE = "Web Based Hospital Operations, Appointment and Queue Management System"
STUDENTS = [
    ("Md. Sobuj Mia", "0242220005101064"),
    ("Md. Ismail Hossain", "0242220005101051"),
]
SUPERVISOR = "Md. Ferdouse Ahmed Foysal"
CO_SUPERVISOR = "Shah Md. Tanvir Siddiquee"
SUBMISSION_DATE = "September 04, 2026"

NAVY = "13324A"
TEAL = "087F73"
PALE = "DDF4EF"
BLUE = "DDECF7"
GRAY = "E9EEF1"
WHITE = "FFFFFF"
INK = "17232D"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, start=90, bottom=80, end=90) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def keep_with_next(paragraph) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    node = p_pr.find(qn("w:keepNext"))
    if node is None:
        node = OxmlElement("w:keepNext")
        p_pr.append(node)


def keep_together(paragraph) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    node = p_pr.find(qn("w:keepLines"))
    if node is None:
        node = OxmlElement("w:keepLines")
        p_pr.append(node)


def add_heading_rule(paragraph) -> None:
    """Add the thin horizontal rule used by the supplied report's front matter."""
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        p_pr.append(borders)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "3")
    bottom.set(qn("w:color"), "000000")
    borders.append(bottom)


def prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    node = OxmlElement("w:cantSplit")
    tr_pr.append(node)


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    node = OxmlElement("w:tblHeader")
    node.set(qn("w:val"), "true")
    tr_pr.append(node)


def set_repeat_table_header(row) -> None:
    repeat_header(row)
    prevent_row_split(row)


def add_field(paragraph, instruction: str, placeholder: str = "Update field in Microsoft Word") -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend((begin, instr, separate, text, end))


def set_page_number(section, fmt: str, start: int | None = None) -> None:
    sect_pr = section._sectPr
    pg_num = sect_pr.find(qn("w:pgNumType"))
    if pg_num is None:
        pg_num = OxmlElement("w:pgNumType")
        sect_pr.append(pg_num)
    pg_num.set(qn("w:fmt"), fmt)
    if start is not None:
        pg_num.set(qn("w:start"), str(start))


def clear_document(document: Document) -> None:
    body = document._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)
    # The template contains floating footer artwork from its sample report. Keep the
    # page geometry but detach those legacy parts before new page numbers are added.
    sect_pr = body.sectPr
    for reference_name in ("w:headerReference", "w:footerReference"):
        for reference in list(sect_pr.findall(qn(reference_name))):
            sect_pr.remove(reference)
    for rel_id, relationship in list(document.part.rels.items()):
        if relationship.reltype in (RT.HEADER, RT.FOOTER):
            document.part.drop_rel(rel_id)


def style_document(document: Document) -> None:
    normal = document.styles["Normal"]
    normal.font.name = "Century"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Century")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Century")
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Century")
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    normal.paragraph_format.line_spacing = 1.12
    normal.paragraph_format.space_after = Pt(5)

    heading_settings = {
        "Heading 1": (20, "000000", 12, 12),
        "Heading 2": (12, "000000", 10, 5),
        "Heading 3": (10.5, "000000", 7, 4),
        "Heading 4": (10.5, "000000", 6, 3),
    }
    for name, (size, color, before, after) in heading_settings.items():
        style = document.styles[name]
        style.font.name = "Century"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style._element.rPr.rFonts.set(qn("w:ascii"), "Century")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Century")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Century")
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    for name in ("Figure Caption", "Table Caption", "Source Note", "Code Block", "Preliminary Heading", "Front Matter Heading"):
        if name not in document.styles:
            document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    for name in ("Preliminary Heading", "Front Matter Heading"):
        style = document.styles[name]
        style.font.name = "Century"
        style.font.size = Pt(14)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        style.paragraph_format.space_before = Pt(8)
        style.paragraph_format.space_after = Pt(12)
        style.paragraph_format.keep_with_next = True
    for name in ("Figure Caption", "Table Caption"):
        style = document.styles[name]
        style.font.name = "Century"
        style.font.size = Pt(8)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        style.paragraph_format.space_before = Pt(4)
        style.paragraph_format.space_after = Pt(8)
        style.paragraph_format.keep_with_next = name == "Table Caption"
    source = document.styles["Source Note"]
    source.font.name = "Century"
    source.font.size = Pt(8)
    source.font.italic = True
    source.font.color.rgb = RGBColor(82, 100, 113)
    source.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    source.paragraph_format.space_after = Pt(8)
    code = document.styles["Code Block"]
    code.font.name = "Consolas"
    code.font.size = Pt(9)
    code.paragraph_format.left_indent = Cm(0.6)
    code.paragraph_format.right_indent = Cm(0.6)
    code.paragraph_format.space_before = Pt(4)
    code.paragraph_format.space_after = Pt(6)
    code.paragraph_format.line_spacing = 1.0

    for section in document.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.3)
        section.left_margin = Cm(2.54)
        section.right_margin = Cm(2.54)
        section.header_distance = Cm(1.2)
        section.footer_distance = Cm(1.2)


def add_text(document: Document, text: str, *, bold_prefix: str | None = None,
             align=None, style=None, keep=False):
    paragraph = document.add_paragraph(style=style)
    if bold_prefix and text.startswith(bold_prefix):
        paragraph.add_run(bold_prefix).bold = True
        paragraph.add_run(text[len(bold_prefix):])
    else:
        paragraph.add_run(text)
    if align is not None:
        paragraph.alignment = align
    if keep:
        keep_together(paragraph)
    return paragraph


def add_numbering_definition(document: Document, *, bullet: bool) -> int:
    """Create one real single-level Word numbering definition and return its numId."""
    numbering = document.part.numbering_part.element
    abstract_ids = [int(node.get(qn("w:abstractNumId"))) for node in numbering.findall(qn("w:abstractNum"))]
    num_ids = [int(node.get(qn("w:numId"))) for node in numbering.findall(qn("w:num"))]
    abstract_id = max(abstract_ids, default=0) + 1
    num_id = max(num_ids, default=0) + 1

    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    multi = OxmlElement("w:multiLevelType")
    multi.set(qn("w:val"), "singleLevel")
    abstract.append(multi)
    level = OxmlElement("w:lvl")
    level.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    level.append(start)
    number_format = OxmlElement("w:numFmt")
    number_format.set(qn("w:val"), "bullet" if bullet else "decimal")
    level.append(number_format)
    level_text = OxmlElement("w:lvlText")
    level_text.set(qn("w:val"), "•" if bullet else "%1.")
    level.append(level_text)
    justification = OxmlElement("w:lvlJc")
    justification.set(qn("w:val"), "left")
    level.append(justification)
    paragraph_properties = OxmlElement("w:pPr")
    indentation = OxmlElement("w:ind")
    indentation.set(qn("w:left"), "540")
    indentation.set(qn("w:hanging"), "300")
    paragraph_properties.append(indentation)
    level.append(paragraph_properties)
    abstract.append(level)
    numbering.insert(0, abstract)

    concrete = OxmlElement("w:num")
    concrete.set(qn("w:numId"), str(num_id))
    reference = OxmlElement("w:abstractNumId")
    reference.set(qn("w:val"), str(abstract_id))
    concrete.append(reference)
    numbering.append(concrete)
    return num_id


def apply_numbering(paragraph, num_id: int) -> None:
    paragraph_properties = paragraph._p.get_or_add_pPr()
    num_properties = OxmlElement("w:numPr")
    level = OxmlElement("w:ilvl")
    level.set(qn("w:val"), "0")
    number = OxmlElement("w:numId")
    number.set(qn("w:val"), str(num_id))
    num_properties.extend((level, number))
    paragraph_properties.append(num_properties)


def add_numbered(document: Document, items: list[str]) -> None:
    num_id = add_numbering_definition(document, bullet=False)
    for item in items:
        paragraph = document.add_paragraph(item)
        apply_numbering(paragraph, num_id)


def add_bullets(document: Document, items: list[str]) -> None:
    num_id = add_numbering_definition(document, bullet=True)
    for item in items:
        paragraph = document.add_paragraph(item)
        apply_numbering(paragraph, num_id)


def add_heading(document: Document, text: str, level: int = 1, *, page_break_before: bool = False) -> None:
    paragraph = document.add_heading(text, level=level)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.page_break_before = page_break_before
    keep_with_next(paragraph)


def add_table(document: Document, number: str, title: str, headers: list[str], rows: list[list[str]],
              widths: list[float] | None = None, font_size=9) -> None:
    caption = document.add_paragraph(style="Table Caption")
    caption.add_run(f"Table {number}: {title}")
    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = False
    header = table.rows[0]
    set_repeat_table_header(header)
    for index, value in enumerate(headers):
        cell = header.cells[index]
        cell.text = value
        set_cell_shading(cell, "E6E6E6")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_margins(cell)
        if widths:
            cell.width = Inches(widths[index])
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.0
            for run in paragraph.runs:
                run.font.name = "Century"
                run.font.size = Pt(font_size)
                run.font.bold = True
                run.font.color.rgb = RGBColor(0, 0, 0)
    for row_index, values in enumerate(rows):
        row = table.add_row()
        prevent_row_split(row)
        if row_index % 2:
            for cell in row.cells:
                set_cell_shading(cell, "F4F4F4")
        for index, value in enumerate(values):
            cell = row.cells[index]
            cell.text = str(value)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            if widths:
                cell.width = Inches(widths[index])
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.0
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in paragraph.runs:
                    run.font.name = "Century"
                    run.font.size = Pt(font_size)
    if widths:
        width_twips = [round(value * 1440) for value in widths]
        total_twips = sum(width_twips)
        table_pr = table._tbl.tblPr
        table_width = table_pr.find(qn("w:tblW"))
        if table_width is None:
            table_width = OxmlElement("w:tblW")
            table_pr.insert(0, table_width)
        table_width.set(qn("w:w"), str(total_twips))
        table_width.set(qn("w:type"), "dxa")
        table_indent = table_pr.find(qn("w:tblInd"))
        if table_indent is None:
            table_indent = OxmlElement("w:tblInd")
            table_pr.append(table_indent)
        table_indent.set(qn("w:w"), "0")
        table_indent.set(qn("w:type"), "dxa")
        grid = table._tbl.tblGrid
        for child in list(grid):
            grid.remove(child)
        for twips in width_twips:
            column = OxmlElement("w:gridCol")
            column.set(qn("w:w"), str(twips))
            grid.append(column)
        for row in table.rows:
            for index, cell in enumerate(row.cells):
                tc_width = cell._tc.get_or_add_tcPr().find(qn("w:tcW"))
                if tc_width is None:
                    tc_width = OxmlElement("w:tcW")
                    cell._tc.get_or_add_tcPr().append(tc_width)
                tc_width.set(qn("w:w"), str(width_twips[index]))
                tc_width.set(qn("w:type"), "dxa")
    document.add_paragraph()


def add_task_allocation_timeline(document: Document, number: str) -> None:
    """Add the editable two-row planned/actual timeline required by the FYDP template."""
    caption = document.add_paragraph(style="Table Caption")
    caption.add_run(f"Table {number}: Task allocation and project timeline.")

    weeks = list(range(12, 50, 2))
    task_width = 1.84
    week_width = (6.20 - task_width) / len(weeks)
    widths = [task_width] + [week_width] * len(weeks)
    table = document.add_table(rows=2, cols=20)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    task_header = table.cell(0, 0).merge(table.cell(1, 0))
    task_header.text = "Tasks"
    weeks_header = table.cell(0, 1).merge(table.cell(0, 19))
    weeks_header.text = "Weeks"
    for index, value in enumerate(weeks, start=1):
        table.cell(1, index).text = str(value)

    schedule = [
        ("Project analysis and requirements", (12, 20), (12, 18)),
        ("Architecture and data design", (16, 24), (18, 26)),
        ("Identity, roles and hospital directory", (20, 30), (22, 32)),
        ("Scheduling and appointment workflow", (24, 34), (26, 36)),
        ("Reception and queue operations", (30, 38), (32, 40)),
        ("Assistant, audit and notifications", (34, 42), (36, 44)),
        ("Security, testing and recovery", (38, 46), (40, 48)),
        ("Report, UAT and deployment readiness", (42, 48), (44, 48)),
    ]
    planned_fill = "4D4BFF"
    actual_fill = "4CF45B"
    for task, planned, actual in schedule:
        planned_row = table.add_row()
        actual_row = table.add_row()
        prevent_row_split(planned_row)
        prevent_row_split(actual_row)
        merged_task = planned_row.cells[0].merge(actual_row.cells[0])
        merged_task.text = task
        for column, week in enumerate(weeks, start=1):
            if planned[0] <= week <= planned[1]:
                set_cell_shading(planned_row.cells[column], planned_fill)
            if actual[0] <= week <= actual[1]:
                set_cell_shading(actual_row.cells[column], actual_fill)

    target_width_twips = round(6.20 * 1440)
    width_twips = [round(value * 1440) for value in widths]
    width_twips[-1] += target_width_twips - sum(width_twips)
    table_width = table._tbl.tblPr.find(qn("w:tblW"))
    if table_width is None:
        table_width = OxmlElement("w:tblW")
        table._tbl.tblPr.insert(0, table_width)
    table_width.set(qn("w:w"), str(sum(width_twips)))
    table_width.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for value in width_twips:
        grid_column = OxmlElement("w:gridCol")
        grid_column.set(qn("w:w"), str(value))
        grid.append(grid_column)

    for row_index, row in enumerate(table.rows):
        raw_cells = list(row._tr.tc_lst)
        expected_widths = [width_twips[0], sum(width_twips[1:])] if row_index == 0 else width_twips
        if len(raw_cells) != len(expected_widths):
            raise ValueError(f"Unexpected task timeline geometry in row {row_index + 1}")
        for raw_cell, value in zip(raw_cells, expected_widths):
            tc_width = raw_cell.get_or_add_tcPr().find(qn("w:tcW"))
            if tc_width is None:
                tc_width = OxmlElement("w:tcW")
                raw_cell.get_or_add_tcPr().append(tc_width)
            tc_width.set(qn("w:w"), str(value))
            tc_width.set(qn("w:type"), "dxa")

    for row_index, row in enumerate(table.rows):
        if row_index < 2:
            repeat_header(row)
        prevent_row_split(row)
        for cell_index, cell in enumerate(row.cells):
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell, top=20, start=18, bottom=20, end=18)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_before = Pt(0)
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.0
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT if cell_index == 0 else WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    run.font.name = "Century"
                    run.font.size = Pt(7.2)
                    run.font.color.rgb = RGBColor(0, 0, 0)
                    if row_index == 0 or (row_index == 1 and cell_index == 0):
                        run.font.bold = True

    spacer = document.add_paragraph()
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(0)
    spacer.paragraph_format.line_spacing = 0.3
    legend = document.add_table(rows=1, cols=4)
    legend.style = "Table Grid"
    legend.alignment = WD_TABLE_ALIGNMENT.CENTER
    legend.autofit = False
    repeat_header(legend.rows[0])
    legend_labels = ["Estimated Work Period", "", "Actual Work Period", ""]
    legend_widths = [1.82, 0.36, 1.66, 0.36]
    legend_twips = [round(value * 1440) for value in legend_widths]
    legend_table_width = legend._tbl.tblPr.find(qn("w:tblW"))
    if legend_table_width is None:
        legend_table_width = OxmlElement("w:tblW")
        legend._tbl.tblPr.insert(0, legend_table_width)
    legend_table_width.set(qn("w:w"), str(sum(legend_twips)))
    legend_table_width.set(qn("w:type"), "dxa")
    legend_grid = legend._tbl.tblGrid
    for child in list(legend_grid):
        legend_grid.remove(child)
    for value in legend_twips:
        grid_column = OxmlElement("w:gridCol")
        grid_column.set(qn("w:w"), str(value))
        legend_grid.append(grid_column)
    for index, label in enumerate(legend_labels):
        cell = legend.cell(0, index)
        cell.text = label
        cell.width = Inches(legend_widths[index])
        tc_width = cell._tc.get_or_add_tcPr().find(qn("w:tcW"))
        if tc_width is None:
            tc_width = OxmlElement("w:tcW")
            cell._tc.get_or_add_tcPr().append(tc_width)
        tc_width.set(qn("w:w"), str(legend_twips[index]))
        tc_width.set(qn("w:type"), "dxa")
        set_cell_margins(cell, top=20, start=30, bottom=20, end=30)
        if index == 1:
            set_cell_shading(cell, planned_fill)
        elif index == 3:
            set_cell_shading(cell, actual_fill)
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(0)
            for run in paragraph.runs:
                run.font.name = "Century"
                run.font.size = Pt(8)
                run.font.bold = True
    document.add_paragraph()


def add_figure(document: Document, number: str, title: str, path: Path, *, width=6.3,
               source: str | None = None) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.keep_with_next = True
    shape = paragraph.add_run().add_picture(str(path), width=Inches(width))
    shape._inline.docPr.set("descr", title)
    shape._inline.docPr.set("title", f"Figure {number}")
    caption = document.add_paragraph(style="Figure Caption")
    caption.add_run(f"Figure {number}: {title}")
    if source:
        caption.paragraph_format.keep_with_next = True
        add_text(document, source, style="Source Note")


def page_break(document: Document) -> None:
    document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def new_section(document: Document, *, numbering: str, start: int) -> None:
    section = document.add_section(WD_SECTION.NEW_PAGE)
    section.different_first_page_header_footer = False
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.3)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)
    section.header_distance = Cm(1.2)
    section.footer_distance = Cm(1.2)
    section.footer.is_linked_to_previous = False
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.LEFT
    footer.paragraph_format.tab_stops.add_tab_stop(Inches(6.05), WD_TAB_ALIGNMENT.RIGHT)
    mark = footer.add_run("©Daffodil International University")
    mark.italic = True
    footer.add_run("\t")
    add_field(footer, "PAGE")
    for run in footer.runs:
        run.font.name = "Century"
        run.font.size = Pt(8)
    set_page_number(section, numbering, start)


def chapter(document: Document, number: int, title: str, overview: str, *, start_on_new_page: bool = True) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.page_break_before = start_on_new_page
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_before = Pt(20)
    run = paragraph.add_run(f"Chapter {number}")
    run.bold = True
    run.font.name = "Century"
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(0, 0, 0)
    heading = document.add_heading(title, level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
    heading.paragraph_format.space_before = Pt(20)
    heading.paragraph_format.space_after = Pt(28)
    add_text(document, overview)


def cover(document: Document, logo: Path) -> None:
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(26)
    r = p.add_run(TITLE)
    r.bold = True
    r.font.name = "Century"
    r.font.size = Pt(20)
    add_text(document, "By", align=WD_ALIGN_PARAGRAPH.CENTER)
    for name, student_id in STUDENTS:
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(name)
        r.bold = True
        r.font.size = Pt(11)
        p.add_run(f"\n{student_id}")
    p = add_text(document, "FINAL YEAR DESIGN PROJECT REPORT", align=WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.space_before = Pt(22)
    for run in p.runs:
        run.bold = True
        run.font.size = Pt(14)
    add_text(
        document,
        "This Report Presented in Partial Fulfillment of the Requirements for the Degree of Bachelor of Science in Computer Science and Engineering",
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(15)
    p.add_run("Supervised by\n").bold = True
    p.add_run(f"{SUPERVISOR}\nLecturer\nDepartment of Computer Science and Engineering")
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(7)
    p.add_run("Co-Supervised by\n").bold = True
    p.add_run(f"{CO_SUPERVISOR}\nLecturer\nDepartment of Computer Science and Engineering")
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(8)
    shape = paragraph.add_run().add_picture(str(logo), width=Inches(1.22))
    shape._inline.docPr.set("descr", "Daffodil International University logo")
    shape._inline.docPr.set("title", "University logo")
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    r = p.add_run("DAFFODIL INTERNATIONAL UNIVERSITY")
    r.bold = True
    r.font.size = Pt(12)
    p.add_run(f"\nDhaka, Bangladesh\n{SUBMISSION_DATE}")
    for cover_paragraph in document.paragraphs:
        cover_paragraph.paragraph_format.line_spacing = 1.0
        cover_paragraph.paragraph_format.space_after = Pt(1)


def preliminary_pages(document: Document) -> None:
    document.add_paragraph("APPROVAL", style="Preliminary Heading")
    add_text(
        document,
        f"This project titled “{TITLE}”, submitted by {STUDENTS[0][0]} and {STUDENTS[1][0]} to the Department of Computer Science and Engineering, Daffodil International University, has been prepared in partial fulfillment of the requirements for the degree of Bachelor of Science in Computer Science and Engineering. The work, report, demonstration, and supporting evidence are presented for academic evaluation and approval as to their style and contents.",
    )
    board_heading = document.add_paragraph(style="Preliminary Heading")
    board_run = board_heading.add_run("BOARD OF EXAMINERS")
    board_run.underline = True
    examiners = [
        "Board Chairman",
        "Internal Examiner 1",
        "Internal Examiner 2",
        "External Examiner",
    ]
    for role in examiners:
        add_text(document, "Name and signature: ______________________________________")
        add_text(document, f"{role}\nDepartment of Computer Science and Engineering\nDaffodil International University")
        document.add_paragraph()
    page_break(document)

    declaration_start = len(document.paragraphs)
    declaration_heading = document.add_paragraph("DECLARATION", style="Preliminary Heading")
    add_heading_rule(declaration_heading)
    add_text(
        document,
        f"We hereby declare that the project described in this report was completed by us under the supervision of {SUPERVISOR}, Lecturer, Department of Computer Science and Engineering, Daffodil International University, and the co-supervision of {CO_SUPERVISOR}, Lecturer, Department of Computer Science and Engineering, Daffodil International University. We further declare that this project, or any substantial part of it, has not been submitted elsewhere for the award of another degree or diploma. Sources used in the analysis and design are acknowledged in the references.",
    )
    add_text(document, f"Supervised by:\n\nSignature: ____________________\n{SUPERVISOR}\nLecturer, Department of Computer Science and Engineering\nDaffodil International University")
    add_text(document, f"Co-supervised by:\n\nSignature: ____________________\n{CO_SUPERVISOR}\nLecturer, Department of Computer Science and Engineering\nDaffodil International University")
    for name, student_id in STUDENTS:
        add_text(document, f"Submitted by:\n\nSignature: ____________________\n{name}\nID: {student_id}\nDepartment of Computer Science and Engineering\nDaffodil International University")
    for paragraph in document.paragraphs[declaration_start:]:
        paragraph.paragraph_format.line_spacing = 1.0
        paragraph.paragraph_format.space_after = Pt(4)
    page_break(document)

    acknowledgements_heading = document.add_paragraph("ACKNOWLEDGEMENTS", style="Preliminary Heading")
    add_heading_rule(acknowledgements_heading)
    add_text(
        document,
        "First, we are grateful to Almighty Allah for giving us the patience and ability to complete this final year project. The work began as a small appointment system and grew into a carefully bounded hospital operations pilot. That change required us to revisit assumptions, correct earlier documentation, and test the system as a working service rather than only as a classroom demonstration.",
    )
    add_text(
        document,
        f"We express our sincere gratitude to our supervisor, {SUPERVISOR}, and our co-supervisor, {CO_SUPERVISOR}, both from the Department of Computer Science and Engineering at Daffodil International University. Their guidance helped us connect software design decisions with the responsibility involved in handling patient identity, schedules, queues, and operational records.",
    )
    add_text(
        document,
        "We also thank the faculty members, classmates, and family members who supported the work. The interface review, repeated role walkthroughs, and discussion of real reception and doctor workflows were especially useful. Finally, we acknowledge the maintainers of the open standards, research literature, frameworks, and tools cited in this report. Their public technical material allowed the system to be developed with verifiable rather than invented assumptions.",
    )
    page_break(document)

    abstract_heading = document.add_paragraph("ABSTRACT", style="Front Matter Heading")
    add_heading_rule(abstract_heading)
    add_text(
        document,
        "Hospitals lose time and create avoidable uncertainty when appointment booking, reception check in, queue progress, onsite payment recording, and communication are kept in separate manual processes. This project develops a web based hospital operations pilot for one small hospital with up to 30 doctors, 500 appointments in a day, and 50 concurrent users. The system provides separate workspaces for patients, doctors, receptionists, and administrators. It covers doctor directories, schedules and closures, patient registration with generated medical record numbers, appointment booking and rescheduling, walk ins, check in, live privacy safe queue tokens, onsite BDT payment status, notifications, consent, and immutable audit evidence. The implementation uses React 19, Django 5.2 LTS, Django REST Framework, PostgreSQL 18, Caddy, and Docker. Transactional domain services combine row locks, uniqueness constraints, idempotency records, state validation, and business histories to protect competing operations. The main design contribution is an Adaptive Arrival Window that combines the configured visit duration with recent valid service durations and reports a bounded wait range without performing clinical triage or changing first in first out order. A read only role aware assistant explains workflows and uses only allowlisted live facts. It retains a deterministic local answer path when the optional external language provider is unavailable. The completed local candidate passed 129 Django tests with 87 percent line coverage, 57 frontend tests with 88.88 percent line coverage, six Chromium workflow scenarios, security and dependency checks, a 50 user quick read test, and an encrypted backup restoration exercise. Real patient use remains intentionally blocked until the hospital approves its identity, privacy and retention rules, legal review, staff access, external infrastructure, restoration evidence, and signed user acceptance. The result is therefore a tested production candidate and academic implementation, not a claim of unrestricted clinical deployment.",
    )
    keyword = document.add_paragraph()
    keyword.add_run("Keywords: ").bold = True
    keyword.add_run("Hospital Management System, Appointment Scheduling, Patient Queue, Adaptive Arrival Window, Role Based Access Control, Django, React, PostgreSQL, Software Quality Assurance.")
    page_break(document)

    document.add_paragraph("Table of Contents", style="Preliminary Heading")
    p = document.add_paragraph()
    add_field(p, 'TOC \\o "1-3" \\h \\z \\t "Front Matter Heading,1"', "Right click and update the table of contents")
    page_break(document)
    document.add_paragraph("List of Figures", style="Front Matter Heading")
    p = document.add_paragraph()
    add_field(p, 'TOC \\h \\z \\t "Figure Caption,1"', "Right click and update the list of figures")
    page_break(document)
    document.add_paragraph("List of Tables", style="Front Matter Heading")
    p = document.add_paragraph()
    add_field(p, 'TOC \\h \\z \\t "Table Caption,1"', "Right click and update the list of tables")


def chapter_one(document: Document) -> None:
    chapter(
        document,
        1,
        "Introduction",
        "This chapter introduces the operational problem addressed by the Hospital Management System. It explains the motivation, problem statement, objectives, research questions, project scope, expected outcome, contribution, and organization of this report.",
        start_on_new_page=False,
    )
    add_heading(document, "1.1 Introduction", 2)
    add_text(
        document,
        "An outpatient visit begins before a patient enters a consultation room. The patient has to find an appropriate doctor, understand where and when that doctor works, obtain a valid appointment, arrive at the correct location, report to reception, wait for a fair turn, and receive confirmation when the visit ends. Reception staff must identify the patient correctly, avoid duplicate records, protect the final available capacity, accommodate walk ins, and explain delays. Doctors need a current view of their own queue without gaining unrelated access. Administrators have to configure services and retain enough evidence to understand who changed what. A weak system may display a polished dashboard while still allowing double booking, exposure of another patient, or an unexplained queue override.",
    )
    add_text(
        document,
        "The initial university proposal described a basic appointment application. During system analysis, the project was expanded into a bounded hospital operations platform while retaining the approved educational objective. The design now connects doctor information, schedules, appointment capacity, patient registration, reception work, queue progress, onsite payment status, notifications, and administrative oversight. These functions share one controlled data model instead of depending on separate lists or informal communication.",
    )
    add_text(
        document,
        "The implemented project is deliberately nonclinical. It does not store diagnoses, prescriptions, clinical notes, laboratory results, card details, or automated triage decisions. This boundary keeps the work technically coherent and prevents an appointment and patient flow system from being represented as a complete electronic medical record. Within that boundary, the system still treats patient identity, appointment history, queue position, consent, and staff activity as sensitive information.",
    )

    add_heading(document, "1.2 Motivation", 2)
    add_text(
        document,
        "A fixed appointment time does not tell a patient how the real queue is moving. Arriving too early increases crowding and wasted time, while arriving too late can disrupt service. A receptionist who answers the same availability and queue questions repeatedly has less time for identity checking and patient assistance. The project is motivated by the opportunity to connect scheduling, check in, queue progress, and communication in one consistent record. Research on outpatient scheduling shows that access, variability, no shows, capacity, and patient preferences interact, so a useful design must handle more than a calendar screen [1], [2], [3].",
    )
    add_text(
        document,
        "The second motivation is responsibility. Patient identity, contact details, appointment patterns, and queue position are sensitive operational data even when no clinical notes are present. Security cannot be added after the screens are finished. The design therefore starts with default denial, server side sessions, staff MFA, minimal disclosure, immutable histories, and recovery controls. NIST secure development guidance similarly treats security requirements and verification as work throughout the life cycle, not only as a final scan [18].",
    )

    add_heading(document, "1.3 Problem Statement", 2)
    add_text(
        document,
        "The main problem is the lack of one dependable workflow joining appointment capacity with actual outpatient arrival and service order. A simple calendar can accept a booking but may still allow two requests to compete for the last position. A reception list can record arrival but may not preserve the relationship with the appointment. A queue screen can display progress but may expose patient identity or give an exact waiting time that cannot be justified. Separate manual records also make correction, audit, notification, and recovery difficult.",
    )
    add_text(
        document,
        "The engineering problem is therefore to build a web based system that coordinates these operations for one small hospital, preserves legal state transitions during repeated or concurrent requests, limits information according to role and ownership, and remains understandable on ordinary desktop and mobile browsers. The solution must be useful during a real reception workflow while remaining small enough to deploy, test, maintain, back up, and restore with limited infrastructure.",
    )

    add_heading(document, "1.4 Objectives", 2)
    add_numbered(
        document,
        [
            "Create a responsive web system for patient, doctor, receptionist, and administrator roles with clear ownership and object level access rules.",
            "Provide a configurable hospital directory containing departments, locations, chambers, doctor profiles, schedules, exceptions, capacity, and consultation fees.",
            "Register patients with unique medical record numbers, explicit privacy notice consent, duplicate warnings, safe corrections, and an assisted account claim path.",
            "Implement transactional appointment booking, rescheduling, cancellation, check in, walk in handling, queue transitions, and onsite payment recording.",
            "Show privacy safe queue tokens, current service progress, a bounded wait range, an arrival recommendation, confidence, and freshness without revealing another patient.",
            "Provide a read only role aware assistant that explains the system and answers live operational questions from allowlisted data without giving medical advice.",
            "Record business history, staff authentication events, consent, administrative changes, notification attempts, and operational overrides for review.",
            "Meet stated quality gates for automated tests, authorization, concurrency, accessibility, dependency security, container assembly, recovery, and documentation.",
            "Produce a maintainable deployment design with separate runtime and migration database privileges, encrypted backups, monitoring, rollback, and explicit real data approval gates.",
        ],
    )

    add_heading(document, "1.5 Methodology", 2)
    add_text(
        document,
        "The project followed an iterative design and implementation method. Requirements from the supplied university material were traced to actors, permissions, records, state transitions, risks, interfaces, and test conditions. The system was then built as complete vertical workflows across React, the Django API, and PostgreSQL. Each workflow passed code review, automated checks, role based browser verification, and defect correction before the next workflow was accepted. Deployment, recovery, privacy, and real data approval were evaluated as part of the same method rather than as work left outside the software life cycle.",
    )

    add_heading(document, "1.6 Research Questions", 2)
    research_questions = [
        "RQ1. How can appointment capacity be protected when patients or staff submit repeated or competing booking requests?",
        "RQ2. How can scheduled patients and walk in patients enter one fair operational queue without revealing another patient's identity?",
        "RQ3. Can recent valid service durations support a useful waiting range and recommended arrival window without performing medical triage or changing first in first out order?",
        "RQ4. How can one assistant answer role specific workflow and live operational questions without obtaining broad database access or changing hospital records?",
        "RQ5. Which authentication, authorization, audit, backup, testing, and deployment controls are necessary before a small hospital pilot may handle real patient data?",
    ]
    for question in research_questions:
        add_text(document, question, bold_prefix=question.split(".")[0] + ".")

    add_heading(document, "1.7 Scope of the Project", 2)
    add_text(
        document,
        "The first release is designed for one small hospital with up to 30 doctors, about 500 appointments in a day, and 50 concurrent users. It supports patient, doctor, receptionist, and administrator roles. Included functions are patient registration and account claiming, medical record number generation, departments, locations, chambers, doctor profiles, recurring schedules, closures, availability, appointment booking, rescheduling, cancellation, check in, walk ins, queue control, privacy safe patient tokens, adaptive waiting information, onsite payment recording in BDT, notifications, consent, administrative settings, operational reports, and audit evidence.",
    )
    add_text(
        document,
        "The release excludes electronic medical record notes, diagnoses, prescriptions, laboratory, pharmacy, radiology, inpatient care, bed management, insurance, inventory, payroll, online payments, SMS, video consultation, automated diagnosis, automated triage, and multi hospital tenancy. The development name MediQueue is configurable and must be replaced by the hospital's approved identity before public use. All demonstrations use synthetic records until the legal, organizational, and infrastructure gates are approved.",
    )

    add_heading(document, "1.8 Project Outcome", 2)
    add_text(
        document,
        "The expected outcome is a complete web application that can demonstrate the outpatient journey from doctor discovery to appointment completion. A patient should be able to create an account, find a doctor, select real computed availability, book or change an appointment, and follow a private queue token. Reception should be able to identify patients, create walk ins, check patients in, and record onsite payment status. A doctor should be able to manage only the assigned queue. An administrator should be able to configure the service and review audit records.",
    )
    add_text(
        document,
        "The expected technical result is a same origin React and Django application backed by PostgreSQL, deployed through containers and a reverse proxy. The database must protect capacity and state under concurrency. Automated tests must cover roles, ownership, workflow transitions, idempotency, queue privacy, provider failure, accessibility, builds, container assembly, and restoration. External hospital acceptance and real patient launch approval remain separate from completion of the academic prototype.",
    )

    add_heading(document, "1.9 Contribution of the Project", 2)
    add_text(
        document,
        "The first contribution is an integrated operational model that joins schedule capacity, appointments, reception check in, queue tickets, payments, notifications, consent, and audit history without mixing their states. The second contribution is the Adaptive Arrival Window. It combines the configured consultation duration with the median of recent valid service durations, reports a range and confidence rather than an exact promise, and records manual overrides while preserving first in first out order.",
    )
    add_text(
        document,
        "The third contribution is a role aware, read only help assistant. It answers workflow questions and carefully selected live facts for the signed in role while refusing medical advice and write operations. A deterministic local answer path remains available when the optional language provider fails. The fourth contribution is the engineering evidence around the application: transactional services, stable API errors, immutable histories, staff MFA, security checks, reproducible containers, encrypted restoration, role walkthroughs, and explicit go live conditions.",
    )

    add_heading(document, "1.10 Organization of the Report", 2)
    add_text(
        document,
        "Chapter 2 presents the hospital operations background, related research, comparable systems, feature comparison, and gap analysis. Chapter 3 explains the research methodology, requirements, system architecture, data design, workflow method, adaptive mechanism, assistant method, tools, and project allocation. Chapter 4 describes the implementation environment, implemented modules, interface evidence, software quality assurance, and measured results. Chapter 5 discusses engineering standards, design constraints, ethical and social responsibilities, sustainability, financial analysis, complex engineering problems, knowledge profiles, engineering activities, and risk. Chapter 6 summarises the work, reports the major findings, traces the objectives, explains limitations, identifies future work, and gives the final conclusion.",
    )


def chapter_two(document: Document) -> None:
    chapter(
        document,
        2,
        "Background and Gap Analysis",
        "This chapter explains the background of hospital information systems, outpatient appointment scheduling, reception queues, privacy, and operational assistance. It reviews verifiable research and comparable products, then identifies the gap addressed by the proposed system.",
    )
    add_heading(document, "2.1 Introduction", 2)
    add_text(
        document,
        "Appointment scheduling allocates limited provider time among patients whose arrival and service duration are uncertain. A slot is therefore both a promise to a patient and a capacity reservation for a hospital. Queue management begins when the patient reaches the service location. The appointment order, actual arrival, late attendance, walk ins, temporary deferral, doctor availability, and variable service time can all change the observed wait. These two problems are related but should not be represented by one overloaded status field.",
    )
    add_text(
        document,
        "The implemented model separates appointment state from queue state. An appointment may be confirmed while its patient has not checked in. Check in creates one queue ticket with a public token. The appointment later becomes completed or no show when the service path reaches a terminal result. This separation makes reports and permissions more precise. It also lets a patient leave the queue without silently deleting the original appointment history.",
    )
    add_text(
        document,
        "A hospital information service also has to manage identity, accountability, and recovery. The WHO global digital health strategy emphasises coordinated and sustainable digital health rather than technology in isolation [17]. For this project, sustainability means a small number of understandable services, a supported database, reproducible images, documented recovery, and controls that a small operational team can actually maintain.",
    )

    add_heading(document, "2.2 Hospital Information Systems", 2)
    add_text(
        document,
        "A hospital information system brings separate administrative activities into a shared and controlled information flow. In the scope of this project, the important records are hospital identity, departments, service locations, doctors, schedules, patients, appointments, queue sessions, queue tickets, payments, notifications, consent, and audit events. Each record has a different purpose and life cycle. Combining all of them in one generic table or status field would make validation and access control difficult.",
    )
    add_text(
        document,
        "The proposed system follows a modular structure. Directory information is public only where disclosure is appropriate. Patient identity is private. Appointment and queue records are projected differently for patients, doctors, receptionists, and administrators. Administrative configuration is separated from daily operational actions. This structure supports accountability while keeping the first release smaller than a full clinical information system.",
    )

    add_heading(document, "2.3 Outpatient Appointment Scheduling", 2)
    add_text(
        document,
        "Outpatient appointment scheduling assigns limited doctor capacity to patient demand. Capacity is influenced by the schedule date, working interval, consultation duration, parallel capacity, closure rules, and existing confirmed appointments. The application must compute availability from those inputs instead of storing a list of disconnected time labels. Booking and rescheduling must run inside database transactions so that two requests cannot both reserve the final position.",
    )
    add_text(
        document,
        "Research shows that appointment rules interact with service variability, patient preferences, access, and nonattendance [1], [2], [3], [4]. This project does not claim one universal schedule rule. It provides explicit capacity, exceptions, cancellation, rescheduling, reminders, and no show outcomes so that the hospital can operate and later evaluate its own service pattern.",
    )

    add_heading(document, "2.4 Reception and Queue Management", 2)
    add_text(
        document,
        "Queue management begins after physical arrival. A confirmed appointment does not itself prove that the patient is present. Reception check in creates one queue ticket and one public token for the relevant doctor, date, and chamber. Walk in registration creates an appointment and queue entry through one controlled action. The doctor then calls, starts, defers, restores, completes, or marks a patient as no show through defined state transitions.",
    )
    add_text(
        document,
        "The live queue remains first in first out according to effective waiting time. A defer action temporarily removes a patient from the active order, while restore records a new effective waiting time and reason. The patient sees only the patient's own token, the token being served, an estimated range, confidence, and freshness. Another patient's name, contact information, or appointment reason is never part of the patient queue response.",
    )

    add_heading(document, "2.5 Privacy, Security, and Accountability", 2)
    add_text(
        document,
        "Operational hospital data can still reveal identity, attendance, specialist choice, and visit patterns even when no diagnosis is stored. The project therefore uses server managed sessions, CSRF protection, verified patient email, invitation only staff accounts, TOTP multi factor authentication for staff, default deny permissions, queryset filtering, object checks, rate limits, and security focused response headers. Sensitive write actions record the actor, request, time, previous state, new state, and reason where applicable.",
    )
    add_text(
        document,
        "Security is treated as a development activity rather than a final feature. The test plan applies relevant OWASP ASVS Level 2 controls [20], while the repository workflow follows secure development principles from NIST SP 800-218 [18]. These sources guide verification; they do not replace legal and operational approval by the hospital.",
    )

    add_heading(document, "2.6 Role Aware Digital Assistance", 2)
    add_text(
        document,
        "Patients and staff often need help with navigation, availability, queue progress, and operational rules. A generic chatbot connected directly to the database would create unnecessary disclosure and action risk. The proposed assistant instead receives an allowlisted context prepared by server side role rules. It is read only, refuses medical advice and triage, does not claim that an action has been completed, and returns a deterministic local answer when the optional external language provider is unavailable.",
    )

    add_heading(document, "2.7 Adaptive Arrival Information", 2)
    add_text(
        document,
        "A fixed appointment time and an exact predicted wait can both be misleading when consultation duration varies. The proposed Adaptive Arrival Window communicates a bounded range. Before sufficient observations exist, the configured consultation duration is used. After five valid completed visits for a doctor, the estimate combines 70 percent of the median of the latest 20 valid service durations with 30 percent of the configured duration. Dispersion broadens the interval, and the patient sees the confidence and last update time. This remains an operational estimate, not a clinical priority score.",
    )

    add_heading(document, "2.8 Related Works", 2)
    add_text(
        document,
        "The review concentrated on outpatient scheduling, wait reduction, nonattendance, reminders, and self scheduling because these topics directly influence the project. No paper was used to justify clinical prioritisation. The Adaptive Arrival Window is an engineering design for operational communication and requires evaluation against real pilot data before effectiveness can be claimed.",
    )
    literature = [
        ["Cayirli and Veral [1]", "2003", "Review of outpatient scheduling literature", "Classified appointment system decisions and sources of variability; established that scheduling performance depends on interacting design choices."],
        ["Cayirli, Veral and Rosen [2]", "2006", "Simulation study of ambulatory scheduling", "Compared appointment rules and showed the importance of matching schedule design to the operating environment."],
        ["Gupta and Denton [3]", "2008", "Review and research agenda", "Connected access, patient preferences, provider constraints and uncertainty; identified practical modelling challenges."],
        ["Ahmadi-Javid et al. [4]", "2017", "Systematic review of optimisation studies", "Organised outpatient appointment optimisation research and highlighted assumptions that can limit practical transfer."],
        ["Dantas et al. [5]", "2018", "Systematic review of no shows", "Reviewed causes and methods around nonattendance, supporting explicit cancellation, reminder and no show handling."],
        ["Rivas [6]", "2020", "Synthesis of advanced access evidence", "Reported that access interventions can improve some operational outcomes while results depend on context."],
        ["Ansell et al. [7]", "2017", "Systematic review of wait reduction", "Found multiple patient centred interventions, including open access, but did not establish one universal design."],
        ["McLean et al. [8]", "2016", "Reminder evidence synthesis", "Showed reminders are useful but operate through context, information quality and patient ability to respond."],
        ["Zhao et al. [9]", "2017", "Meta analysis of digital notifications", "Evaluated electronic notifications for appointment attendance and informed the minimal notification design."],
        ["Ahmadi et al. [10]", "2020", "Systematic review of no show prediction", "Mapped prediction methods and limitations; reinforced the decision not to automate patient priority in this pilot."],
        ["Woodcock et al. [11]", "2022", "Review of automated self scheduling", "Identified organisational, workflow, usability and integration factors beyond simply placing a calendar online."],
    ]
    add_table(document, "2.1", "Summary of literature reviewed", ["Author", "Year", "Focus", "Relevance to this project"], literature, widths=[1.35, 0.55, 1.65, 2.65], font_size=8)
    add_text(
        document,
        "Three conclusions shaped the design. First, no appointment rule is universally best because demand, service variation, capacity, and patient behaviour differ. Second, reminders and self service access help only when the underlying records and workflow are reliable. Third, predictive work must be evaluated carefully and should not be confused with clinical judgment. The proposed estimator therefore uses a transparent median based calculation, shows uncertainty and confidence, preserves first in first out order, and allows an auditable staff override rather than a hidden ranking.",
    )

    add_heading(document, "2.9 Feature-Based Comparison", 2)
    add_text(
        document,
        "Five established product families were reviewed from their official public descriptions. Their inclusion does not imply access to proprietary architecture, security controls, or measured outcomes. The comparison records visible or documented capabilities only.",
    )
    comparison = [
        ["Doctor discovery and appointment request", "Yes", "Limited", "Yes", "No", "No", "Yes"],
        ["Patient self service portal", "Yes", "No", "Yes", "Limited", "Limited", "Yes"],
        ["Reception or kiosk queue", "No", "Yes", "No", "Yes", "Yes", "Yes"],
        ["Privacy safe patient queue token", "Not established", "Yes", "Not established", "Yes", "Yes", "Yes"],
        ["Live operational wait information", "Limited", "Yes", "Limited", "Yes", "Yes", "Yes"],
        ["Role aware live help assistant", "Not established", "Not established", "Not established", "Not established", "Not established", "Yes"],
        ["Transparent adaptive arrival range", "Not established", "Not established", "Not established", "Not established", "Not established", "Yes"],
        ["Deployment and recovery evidence in project scope", "Not public", "Not public", "Not public", "Not public", "Not public", "Yes"],
    ]
    add_table(document, "2.2", "Public capability comparison", ["Capability", "Practo [12]", "Qminder [13]", "Doctolib [14]", "Qmatic [15]", "Epic MyChart [16]", "Proposed"], comparison, widths=[1.55, 0.7, 0.7, 0.7, 0.7, 0.75, 0.75], font_size=7)
    add_text(
        document,
        "Practo and Doctolib demonstrate doctor discovery and online booking. Qminder and Qmatic focus more directly on arrival and patient flow. MyChart represents a broad patient portal around a larger clinical platform. The proposed system does not try to reproduce those product ecosystems. Its value is the coherent implementation of a small hospital workflow, visible integrity controls, auditable queue decisions, and a deployment package that can be examined academically.",
    )

    add_heading(document, "2.10 Gap Analysis", 2)
    gaps = [
        ["Gap", "Consequence", "Project response"],
        ["Appointment calendar separated from reception queue", "Patients receive a booking time but cannot understand actual progress", "Join booking and check in through a separate queue ticket and privacy safe snapshot"],
        ["Public screens expose names or identifiable queue details", "Waiting patients can learn another person's visit pattern", "Show tokens only and filter every response by role and ownership"],
        ["Repeated clicks and competing staff actions are treated as interface issues", "Double booking, double check in, duplicate payment or two active patients", "Enforce idempotency, row locks, constraints and legal state transitions in the API"],
        ["Wait estimates appear as unexplained exact numbers", "False certainty and difficult operational review", "Return a bounded range, confidence, sample count, calculation version and freshness"],
        ["Generic chatbot receives broad database access", "Cross role disclosure, unsafe advice and actions without accountability", "Build allowlisted role context, read only tools, clinical refusal and deterministic fallback"],
        ["A classroom deployment ends at docker compose up", "No recovery, rollback, monitoring or authority for real data", "Define launch gates, role separation, backups, restore tests, alerts and incident procedures"],
    ]
    add_table(document, "2.3", "Observed gaps and design response", gaps[0], gaps[1:], widths=[1.7, 2.1, 2.4], font_size=8)

    gap_details = [
        ("2.10.1 Gap 1: Fragmented Appointment and Queue State", "Many systems treat booking time and physical queue position as one status. The proposed model separates them and joins them through an explicit check in event. This preserves the meaning of both records and permits accurate cancellation, no show, and completion history."),
        ("2.10.2 Gap 2: Privacy Exposure in Live Queue Displays", "A public queue display can disclose who is receiving a service. The proposed patient projection uses tokens and ownership filtering. Staff interfaces show the minimum identity required for their assigned task, while administrative access remains separately controlled and audited."),
        ("2.10.3 Gap 3: Weak Protection Against Repeated and Concurrent Actions", "A disabled button cannot protect the database when two browsers or staff members act together. The project combines idempotency keys, unique constraints, row locks, transactions, and legal state services so correctness does not depend on the frontend alone."),
        ("2.10.4 Gap 4: Unexplained Waiting Time Claims", "An exact waiting time hides uncertainty. The Adaptive Arrival Window returns a bounded interval, sample count, confidence, calculation version, and freshness. Operational overrides are possible but require a reason and remain visible in history."),
        ("2.10.5 Gap 5: Broad and Unsafe Assistant Access", "A general language model should not decide which records it may read. The server first selects a narrow role specific context, rejects unsafe categories, and keeps the endpoint read only. Provider failure returns local guidance instead of interrupting hospital work."),
        ("2.10.6 Gap 6: Incomplete Production Evidence", "A classroom deployment can stop after the interface runs. This project includes container hardening, health checks, database privilege separation, automated security review, backup and restore procedures, rollback rules, incident escalation, and real data launch gates."),
    ]
    for heading, explanation in gap_details:
        add_heading(document, heading, 3)
        add_text(document, explanation)

    add_heading(document, "2.10.7 Novelty Boundary", 3)
    add_text(
        document,
        "The project does not claim that queues, median service estimates, reminders, language models, or role based access were invented here. Its novel contribution is the implementation combination: a first in first out hospital queue, a transparent adaptive arrival range, freshness and confidence indicators, recorded fairness overrides, a role aware read only assistant, and transactional audit evidence in one small hospital production candidate. The contribution is described as original project engineering, not as a worldwide first. A real pilot must collect error, interval coverage, override, and user acceptance evidence before any stronger effectiveness claim is made.",
    )

    add_heading(document, "2.11 Summary of Research Gap", 2)
    add_text(
        document,
        "The background review shows that scheduling and attendance are context dependent operational problems. Comparable products validate demand for digital booking and queue communication but do not remove the need for a careful local design. The identified gap leads directly to the requirements and architecture in Chapter 3.",
    )


def chapter_three(document: Document) -> None:
    chapter(
        document,
        3,
        "Research Methodology",
        "This chapter presents the method used to analyse, design, implement, and verify the proposed Hospital Management System. The work followed an iterative design and engineering method in which requirements, access rules, database invariants, API behaviour, interface states, and tests were developed together.",
    )
    add_heading(document, "3.1 Requirement Analysis and Design Specification", 2)
    add_heading(document, "3.1.1 Overview", 3)
    add_text(
        document,
        "The research uses a design and implementation methodology. First, the supplied university documents and interface references were examined to identify the intended actors and workflow. Second, the scope was limited to nonclinical outpatient operations. Third, each requirement was mapped to a role, data record, permission, state transition, failure condition, and verification method. The system was then implemented in short vertical increments and evaluated with automated and manual evidence.",
    )
    add_heading(document, "3.1.2 Proposed System Design", 3)
    add_text(
        document,
        "The overall architecture has four functional layers. The presentation layer contains the public pages and the four role workspaces. The application layer contains the versioned Django REST API, authentication, authorization, validation, and domain services. The data layer contains PostgreSQL records, constraints, histories, audit events, idempotency results, and the notification outbox. The operations layer contains Caddy, containers, health checks, monitoring rules, backup, restoration, and release controls.",
    )
    add_figure(document, "3.1", "Overall architecture of the proposed Hospital Management System", DIAGRAM_DIR / "02_system_architecture.png")

    add_heading(document, "3.2 Requirement Collection and Analysis", 2)
    add_heading(document, "3.2.1 Stakeholders and Operating Assumptions", 3)
    stakeholders = [
        ["Patient", "Find a doctor, book, reschedule or cancel, understand queue progress, receive notices, control own profile"],
        ["Doctor", "See assigned schedule and minimum patient identity, operate own queue, understand workload"],
        ["Receptionist", "Register and find patients, prevent duplicates, manage appointments, check in, handle walk ins, queue and onsite payment"],
        ["Administrator", "Manage staff, hospital directory, schedules, settings, reports, notifications and audit evidence"],
        ["Hospital operations owner", "Approve workflow, data policy, support, downtime, incident and launch decisions"],
        ["Deployment operator", "Maintain environment, secrets, images, migrations, monitoring, backup and recovery without reading patient records unnecessarily"],
        ["Academic examiner", "Evaluate requirements, design choices, implementation evidence, limitations and professional responsibility"],
    ]
    add_table(document, "3.1", "Stakeholders and principal needs", ["Stakeholder", "Principal need"], stakeholders, widths=[1.45, 4.75], font_size=9)
    add_text(
        document,
        "The operating assumptions are one active hospital, Asia/Dhaka display time, BDT currency, email availability for self registering patients, invitation controlled staff identities, and onsite payments only. The service must remain useful when email is delayed and when the optional language provider is absent. The browser is untrusted. Interface visibility never replaces server authorization.",
    )

    add_heading(document, "3.2.2 Role and System Context", 3)
    add_figure(document, "3.2", "Role and access context", DIAGRAM_DIR / "03_role_access_context.png")
    add_text(
        document,
        "Patients can see only their own claimed profile, appointments, queue ticket, payment summary, notifications, and consent. Doctors can see only their linked schedule and the minimum patient identity associated with their appointments and queue. Receptionists receive operational access needed for registration and flow, but cannot create privileged staff. Administrators configure the service and review audit records. Staff actions require completed TOTP MFA. Querysets are filtered before object lookup so changing a UUID cannot turn a forbidden object into a disclosed object.",
    )

    add_heading(document, "3.2.3 Functional Requirements", 3)
    functional = [
        ["FR01", "Public directory", "Anyone can view active hospital details, departments, doctors and safe future availability."],
        ["FR02", "Patient registration", "A patient accepts the active privacy notice, verifies email and receives one unique MRN."],
        ["FR03", "Assisted registration", "Reception can create an unclaimed profile and send a single use claim invitation without inventing an email."],
        ["FR04", "Duplicate warning", "Reception receives a review warning for matching identity fields; the system never merges automatically."],
        ["FR05", "Staff invitation", "An administrator invites a named staff member to one approved role with an expiring single use token."],
        ["FR06", "Staff MFA", "A staff session remains pending until a valid, nonreplayed TOTP is confirmed."],
        ["FR07", "Directory management", "Administration creates, edits, orders and deactivates departments, locations, chambers and doctors."],
        ["FR08", "Schedule management", "Administration creates effective schedules and dated exceptions while rejecting unsafe overlaps."],
        ["FR09", "Availability", "The API computes slots from schedule, exception, local time and confirmed capacity."],
        ["FR10", "Booking", "A verified patient or reception user reserves eligible capacity within one transaction."],
        ["FR11", "Rescheduling", "An eligible confirmed appointment moves old and new capacity atomically and records both values."],
        ["FR12", "Cancellation", "An eligible actor supplies the required reason and releases future capacity exactly once."],
        ["FR13", "Check in", "Reception creates one queue ticket and final token for an eligible appointment on its service date."],
        ["FR14", "Walk in", "Reception registers or selects a patient, creates a same day appointment, and checks in through one controlled workflow."],
        ["FR15", "Queue operation", "Authorised staff call next, start, defer, restore, complete, no show or cancel through legal transitions."],
        ["FR16", "Patient queue", "A patient sees own token, served token, wait range, arrival guidance, confidence and update time without names."],
        ["FR17", "Payment", "Reception records unpaid, paid onsite, waived or refunded state in integer BDT minor units with history."],
        ["FR18", "Notification", "A committed event can create in application and minimal email notifications through an outbox."],
        ["FR19", "Audit", "Security and business events retain actor, action, subject, reason, request identifier and safe changes."],
        ["FR20", "Assistant", "An authenticated role asks system questions and receives guidance plus only allowlisted live facts."],
        ["FR21", "Failure recovery", "Email and provider failure do not roll back business records; retries and fallback remain bounded."],
        ["FR22", "Hospital settings", "Administration configures development branding, contact values, timezone display and current privacy notice."],
    ]
    add_table(document, "3.2", "Functional requirements", ["ID", "Function", "Verifiable requirement"], functional, widths=[0.55, 1.3, 4.35], font_size=8)

    add_heading(document, "3.2.4 Nonfunctional Requirements", 3)
    nonfunctional = [
        ["NFR01", "Security", "Apply OWASP ASVS Level 2 controls where applicable; no unresolved critical or high finding at launch."],
        ["NFR02", "Privacy", "Minimise data by role, channel, URL and log; never show another patient name in queue progress."],
        ["NFR03", "Integrity", "No slot over capacity, duplicate ticket, duplicate MRN, duplicate active service or illegal terminal transition."],
        ["NFR04", "Availability", "Initial service target is 99.5 percent monthly availability after production monitoring begins."],
        ["NFR05", "Performance", "Production sized staging target is read p95 below 500 ms, write p95 below 800 ms and queue freshness within 15 seconds."],
        ["NFR06", "Capacity", "Support the agreed pilot of 30 doctors, 500 daily appointments and 50 concurrent users."],
        ["NFR07", "Accessibility", "Target WCAG 2.2 AA with keyboard, focus, labels, reflow, contrast, status announcements and no color only meaning."],
        ["NFR08", "Recovery", "Encrypted separate backup copies target a one hour RPO and four hour RTO; clean restore is rehearsed."],
        ["NFR09", "Auditability", "Material state change and override evidence is append only through the application and correlated by request ID."],
        ["NFR10", "Maintainability", "Exact dependencies, small modules, explicit contracts, migrations, tests, human readable commits and operational documentation."],
        ["NFR11", "Compatibility", "Use current Chromium for automated release evidence and complete the documented wider browser checks before real data."],
        ["NFR12", "Safety", "No diagnosis, medical advice, automatic triage, hidden queue priority, card processing or unsupported interoperability claim."],
    ]
    add_table(document, "3.3", "Nonfunctional requirements", ["ID", "Quality", "Acceptance statement"], nonfunctional, widths=[0.6, 1.15, 4.45], font_size=8)

    add_heading(document, "3.3 System Design and Development", 2)
    add_heading(document, "3.3.1 Application Architecture", 3)
    add_text(
        document,
        "The browser and API share one origin. Caddy serves the immutable React build and proxies only the versioned API path to Django. This removes a separate cross origin token architecture and allows Django sessions and CSRF protection to operate normally. The React application performs presentation and interaction; it does not enforce final authority. Django serializers validate shape, permission classes establish the role boundary, views locate role filtered records, and domain services execute state changes inside transactions.",
    )
    add_text(
        document,
        "PostgreSQL is the single source of operational truth. It stores business entities, state history, queue estimates, audit events, idempotency outcomes, notification jobs, and login audit. The notification worker claims committed outbox rows and contacts SMTP independently. An email failure therefore changes the delivery record but cannot erase a successful appointment. Conditional queue reads use ETag and If-None-Match so unchanged snapshots can return without a repeated response body.",
    )
    add_text(
        document,
        "The architecture intentionally omits Redis and WebSockets. Ten second polling on an active queue page and 30 second polling in the background meet the pilot freshness design with fewer moving parts. A snapshot becomes visibly stale after 30 seconds without success. This is an explicit scale tradeoff, not a claim that polling is always superior.",
    )

    add_heading(document, "3.3.2 Data Model and Integrity", 3)
    add_figure(document, "3.3", "Core data model", DIAGRAM_DIR / "08_core_data_model.png")
    data_dictionary = [
        ["User, RoleAssignment", "Authentication identity and one or more explicit application roles", "Unique normalised email; protected role grant"],
        ["StaffInvitation, StaffMFADevice, LoginAudit", "Staff onboarding, encrypted TOTP material and authentication evidence", "Single use invitation; no raw recovery code in storage"],
        ["Hospital, Department, Location, Chamber", "Configurable organisation and service locations", "One active hospital for pilot; unique local codes"],
        ["DoctorProfile, PatientProfile", "Role specific directory and patient identity", "UUID public IDs; unique doctor code and generated MRN"],
        ["PrivacyNoticeVersion, ConsentRecord", "Exact notice text and patient decision history", "Append only consent tied to immutable notice version"],
        ["Schedule, ScheduleException", "Recurring hours, capacity and dated closure or replacement", "Overlap validation; referenced structural schedule fields immutable"],
        ["Appointment, AppointmentHistory", "Current booking and every material appointment change", "Capacity transaction; four exact appointment states"],
        ["QueueSession, QueueTicket, QueueEvent", "Daily service order, current token and transition evidence", "One active ticket per appointment and one active service position"],
        ["QueueEstimateRecord", "Calculation inputs and output used for one patient snapshot", "Append only version, sample and uncertainty evidence"],
        ["PaymentRecord, PaymentHistory", "Onsite BDT status and corrections", "Integer minor units; no card or bank credential fields"],
        ["Notification, NotificationOutbox, NotificationAttempt", "In app messages and reliable email delivery", "Business commit separated from delivery retry"],
        ["AuditEvent, IdempotencyRecord, RateLimitBucket", "Traceability, repeated write result and shared abuse control", "Safe structured data and bounded retention"],
    ]
    add_table(document, "3.4", "Core data dictionary", ["Record group", "Purpose", "Important invariant"], data_dictionary, widths=[1.7, 2.35, 2.15], font_size=8)
    add_text(
        document,
        "Every externally addressable business record uses a UUID. Sequential database keys, where present internally, do not become object authority. Timestamps are stored in UTC and displayed in Asia/Dhaka. Money is stored as integer BDT minor units. Patients, doctors, schedules, and referenced configuration are deactivated or superseded rather than silently deleted. Restrictive foreign keys keep historical records from becoming detached.",
    )

    add_heading(document, "3.3.3 Data Flow Diagram and Appointment Queue State Design", 3)
    add_figure(document, "3.4", "Appointment and queue workflow", DIAGRAM_DIR / "04_appointment_queue_workflow.png")
    add_text(
        document,
        "Appointment states are confirmed, cancelled, completed, and no_show. Queue states are waiting, called, in_service, deferred, completed, no_show, and cancelled. Cancelled, completed, and no show appointments are terminal. Queue defer and restore are explicit because temporarily passing a patient should not be disguised as cancellation. Every override requires a reason and records the previous state, new state, actor, time, and request identifier.",
    )
    add_text(
        document,
        "A write request carries an Idempotency-Key. The server associates its digest with the authenticated actor, route scope, and request digest. An exact retry receives the stored outcome. Reusing the key with a different body is rejected. For competing actions, PostgreSQL row locks serialize the schedule, appointment, queue session, or ticket that owns the invariant. Database constraints remain the final protection if application checks race. PostgreSQL documentation distinguishes row level locking and constraint enforcement, which are both used here [23], [24].",
    )

    add_heading(document, "3.3.4 API Contract", 3)
    api_groups = [
        ["Authentication", "/api/v1/auth/", "CSRF, session, login, MFA, registration, verification, reset, invitation and claim"],
        ["Public directory", "/api/v1/public/", "Hospital, departments, doctors and doctor availability"],
        ["Patient self service", "/api/v1/me/ and /appointments/", "Own profile, consent, appointments, queue and notifications"],
        ["Reception", "/api/v1/reception/", "Patient search, duplicate check, assisted registration, check in and walk in"],
        ["Queue", "/api/v1/queues/ and /queue-tickets/", "Conditional snapshot and controlled state actions"],
        ["Payments", "/api/v1/appointments/{id}/payment/", "Onsite state, corrections and history"],
        ["Administration", "/api/v1/admin/", "Staff, settings, privacy notices, directory, schedules, outbox and audit"],
        ["Assistant", "/api/v1/assistant/chat/", "Authenticated role guidance and read only live context"],
        ["Health", "/api/v1/health/", "Liveness and configuration plus database readiness"],
    ]
    add_table(document, "3.5", "Versioned API groups", ["Area", "Path", "Responsibility"], api_groups, widths=[1.25, 2.05, 2.9], font_size=8)
    add_text(
        document,
        "Successful resources use stable JSON representations. Errors use status, code, title, detail, field_errors, and request_id. Input serializers reject unknown fields on sensitive workflows so a client cannot mass assign role, ownership, state, amount, or audit values. Protected responses use private no store caching where appropriate. Queue snapshots alone expose an ETag suitable for conditional refresh.",
    )

    add_heading(document, "3.4 Adaptive Arrival Window Methodology", 2)
    add_figure(document, "3.5", "Adaptive Arrival Window calculation", DIAGRAM_DIR / "05_adaptive_arrival_window.png")
    add_text(
        document,
        "The live queue remains first in first out by valid check in order. The mechanism never interprets symptoms, diagnoses urgency, or changes priority. Before a doctor has five valid completed visits, the configured schedule duration is used. From five observations onward, the service estimate is 70 percent of the median of the latest 20 valid completed durations plus 30 percent of the configured duration. The result is clamped between five and 60 minutes. Median absolute deviation describes observed variability when enough data exists; otherwise the response uses a deliberately wider fallback interval.",
    )
    p = document.add_paragraph(style="Code Block")
    p.add_run("estimated_service = clamp(0.70 × median(recent_valid_durations) + 0.30 × configured_duration, 5, 60)\n")
    p.add_run("estimated_wait = people_ahead × estimated_service\n")
    p.add_run("arrival_window = bounded range derived from wait and observed or fallback uncertainty")
    add_text(
        document,
        "The response contains token, currently served token, people ahead, lower and upper wait bounds, recommended return or arrival window, confidence label, sample count, calculation version, and last update time. A stored QueueEstimateRecord makes the shown result explainable later. Accuracy is measured as absolute and median absolute error, interval coverage, override rate, stale snapshot rate, and sample count by doctor. Those metrics cannot be reported honestly until a real controlled pilot produces representative durations.",
    )

    add_heading(document, "3.5 Role Aware Assistant Methodology", 2)
    add_figure(document, "3.6", "Role aware help assistant", DIAGRAM_DIR / "06_role_aware_assistant.png")
    add_text(
        document,
        "The assistant is an authenticated, read only help layer. It answers navigation and workflow questions for every role. A patient can ask how to book, whether a selected doctor has future capacity, or what the patient's own queue status means. A doctor can ask which scheduled working day has lower current appointment pressure. Reception and administration can request aggregate operational totals. The server derives role from the session rather than from a client supplied role name.",
    )
    add_text(
        document,
        "Live facts are built by allowlisted query functions. A patient context contains only that patient's records. A doctor context starts from the linked DoctorProfile. Reception and administrator context provides approved counts without patient names or identifiers. The client never sends raw database context to the provider. Questions that request clinical advice, medical urgency, hidden instructions, credentials, another person's data, or unsupported actions are refused or answered through the safe local path.",
    )
    add_text(
        document,
        "The deterministic path covers essential system guidance and remains the default reliability layer. If a replacement Groq key is configured by the authorised operator, the optional provider receives only the system guide, safe role context, the question, and a bounded recent user history through a fixed HTTPS endpoint. Timeouts and provider errors return to local guidance. Output is normalised to plain text because the panel does not render arbitrary Markdown. The assistant cannot book, cancel, change a queue, edit a patient, or record a payment. Groq's API documentation is used only for the optional integration contract [27].",
    )

    add_heading(document, "3.6 System Requirements and Safety Design", 2)
    add_heading(document, "3.6.1 Security and Privacy Design", 3)
    security = [
        ["Authentication", "Django password hashing, email ownership for patients, invitation only staff, TOTP MFA, replay control, lockout and bounded sessions"],
        ["Browser session", "Secure HttpOnly cookie in production, SameSite policy, CSRF token, trusted origin checks and no bearer token in local storage"],
        ["Authorization", "Default deny, role permission, filtered queryset, object ownership and service level invariant checks"],
        ["Data minimisation", "Queue tokens instead of names, minimal emails, no clinical data, no card fields, safe logs and generic public responses"],
        ["Integrity", "Transactions, row locks, unique and check constraints, idempotency and append only state history"],
        ["Secrets", "External environment files, independent values, stable MFA encryption key, no repository key and no secret in screenshots"],
        ["Runtime", "Nonroot containers, read only filesystems, dropped capabilities, private database network and narrow public ports"],
        ["Supply chain", "Exact lockfiles, immutable container references, dependency review, source scanning and secret scanning"],
        ["Recovery", "Encrypted backup, separate copy approval, restoration rehearsal, RPO, RTO, migration and rollback procedure"],
        ["Accountability", "Login audit, business audit, consent versions, history records, notification attempts and request correlation"],
    ]
    add_table(document, "3.6", "Security and privacy controls", ["Area", "Implemented design"], security, widths=[1.35, 4.85], font_size=8)
    add_text(
        document,
        "The control baseline uses applicable OWASP ASVS 5.0 Level 2 verification items [20], Django security guidance [22], and secure development practices from NIST SP 800-218 [18]. This is a mapped engineering baseline, not a certification. Bangladesh legal applicability, retention, data location, controller responsibilities, and hospital policy still require qualified review against the current official instruments before real data [25].",
    )

    add_heading(document, "3.6.2 User Interface and Accessibility Design", 3)
    add_text(
        document,
        "The interface uses a quiet hospital palette, clear page titles, familiar form labels, status text in addition to colour, visible keyboard focus, responsive navigation, and action placement close to the relevant record. Patient pages emphasise the next decision. Reception pages place search, appointment action, and queue action in operational order. Doctor pages minimise navigation around the current queue. Administrator pages separate configuration resources instead of presenting one crowded dashboard.",
    )
    add_text(
        document,
        "Loading, empty, success, validation error, server failure, offline queue, reconnecting, stale data, destructive confirmation, and permission denial are designed states. Queue changes use screen reader announcements without repeating another patient identity. The target is WCAG 2.2 AA [19]. Automated checks support, but do not replace, keyboard and screen reader review with hospital users.",
    )

    add_heading(document, "3.6.3 Design Alternatives Considered", 3)
    alternatives = [
        ["Database", "MySQL or SQLite", "PostgreSQL 18", "One supported database across environments, strong constraints, transactional row locking and operational consistency"],
        ["Authentication", "Browser stored JWT", "Django session and CSRF", "Same origin deployment reduces token exposure and simplifies invalidation"],
        ["Queue updates", "WebSockets with Redis", "Conditional HTTP polling", "Meets 50 user pilot freshness with fewer services and easier recovery"],
        ["Background work", "General message broker", "Database outbox worker", "Keeps appointment commit and notification intent atomic without another datastore"],
        ["Wait estimate", "Mean or opaque prediction model", "Median blend plus uncertainty", "Robust to outliers, explainable, bounded and testable with little initial data"],
        ["Assistant", "Provider only chatbot with broad tools", "Local guidance plus optional provider", "Essential help survives provider failure and live data access stays allowlisted"],
        ["Frontend", "Server rendered templates", "React application", "Supports distinct workspaces, polling state and responsive interaction while retaining one origin"],
    ]
    add_table(document, "3.7", "Design alternatives", ["Decision", "Alternative", "Selected", "Reason"], alternatives, widths=[1.1, 1.4, 1.45, 2.25], font_size=8)

    add_heading(document, "3.7 Tools and Technologies", 2)
    tools = [
        ["Frontend", "React, JavaScript, React Router, Vite, Tailwind CSS", "Role workspaces, responsive interaction, forms, queue polling, and assistant panel"],
        ["Backend", "Python, Django 5.2 LTS, Django REST Framework", "Authentication, authorization, API validation, domain services, audit, and administration"],
        ["Database", "PostgreSQL 18", "Transactions, row locks, constraints, histories, indexes, and operational storage"],
        ["Gateway", "Caddy", "Same origin static delivery, API proxying, HTTPS, and security headers"],
        ["Runtime", "Docker and Docker Compose", "Repeatable local, test, staging, and production service definitions"],
        ["Verification", "Django TestCase, Coverage.py, Vitest, Testing Library, Playwright, axe, k6", "Unit, API, permission, component, browser, accessibility, and load evidence"],
        ["Security", "Bandit, Semgrep, dependency review, Trivy, secret scanning", "Source, dependency, image, configuration, and credential checks"],
        ["Repository", "Git and private GitHub", "Reviewed changes, protected checks, version history, and release evidence"],
    ]
    add_table(document, "3.8", "Tools and technologies used in the project", ["Area", "Tool or technology", "Purpose"], tools, widths=[1.05, 2.15, 3.0], font_size=8)
    add_heading(document, "3.8 Project Plan", 2)
    add_figure(document, "3.7", "Incremental implementation and verification workflow", DIAGRAM_DIR / "01_incremental_methodology.png")
    plan = [
        ["Planning and audit", "Requirements, scope, risks, documents and repository controls", "Requirement traceability and approved implementation boundary"],
        ["Foundation", "React, Django, PostgreSQL, containers, identity, roles and shared UI", "Healthy same origin application with protected sessions"],
        ["Directory and scheduling", "Hospital configuration, doctors, locations, schedules and capacity", "Public discovery and administrable availability"],
        ["Appointment operations", "Patient identity, booking, rescheduling, cancellation, walk ins and check in", "Transactional appointment workflow"],
        ["Queue and communication", "Queue states, estimator, payment, notifications, audit and assistant", "Complete outpatient operational path"],
        ["Verification", "Unit, API, browser, concurrency, load, security, dependency and recovery checks", "Recorded evidence and defect correction"],
        ["Delivery", "Screenshots, report, staging instructions, release and launch gate review", "Submission package and production candidate"],
    ]
    add_table(document, "3.9", "Project activity plan", ["Work package", "Main work", "Output"], plan, widths=[1.45, 2.65, 2.1], font_size=8)
    add_heading(document, "3.9 Task Allocation", 2, page_break_before=True)
    add_task_allocation_timeline(document, "3.10")
    add_table(
        document,
        "3.11",
        "Task allocation between project members",
        ["Project member", "Principal responsibility", "Shared responsibility"],
        [
            [STUDENTS[0][0], "Requirement consolidation, backend services, database integrity, deployment evidence, and report traceability", "Security review, integration, role walkthroughs, defect correction, presentation, and final submission"],
            [STUDENTS[1][0], "Frontend interfaces, role journeys, synthetic demonstration data, browser verification, and evidence capture", "Security review, integration, role walkthroughs, defect correction, presentation, and final submission"],
        ],
        widths=[1.25, 2.55, 2.4],
        font_size=8,
    )
    add_text(
        document,
        f"{STUDENTS[0][0]} concentrated on requirement consolidation, backend domain design, database integrity, deployment evidence, and report traceability. {STUDENTS[1][0]} concentrated on interface implementation, role journeys, synthetic data, browser verification, and evidence capture. Both members reviewed security boundaries, executed manual role walkthroughs, corrected integration defects, and prepared the final presentation. Git history and automated checks remain the technical evidence; this allocation describes responsibility rather than claiming that either member worked in isolation.",
    )

    add_heading(document, "3.10 Summary", 2)
    add_text(
        document,
        "The design treats authorization, state, concurrency, privacy, and recovery as core functions. The selected architecture remains small enough for the stated pilot but includes the controls needed to test it seriously. Chapter 4 shows how these decisions were implemented and verified.",
    )


def add_interface_evidence(document: Document) -> None:
    figures = [
        ("4.2", "Public and patient interfaces of the implemented system", "09_public_patient_interfaces.png", "The public pages present hospital services and approved doctor information. The patient workspace connects booking, upcoming appointments, notifications, profile and privacy choices through one role specific navigation structure."),
        ("4.3", "Patient assistant and privacy safe live queue", "10_patient_assistant_queue.png", "The assistant reports controlled live availability without booking on behalf of the patient. The queue page shows only the patient's token, the token being served, people ahead, a waiting range, confidence, location, and freshness."),
        ("4.4", "Reception dashboard and completed check in result", "11_reception_interfaces.png", "Reception can move from daily workload to patient identification and check in. The completed action returns one public queue token and leaves the appointment available for subsequent queue operation."),
        ("4.5", "Doctor dashboard, workload assistance, and queue operation", "12_doctor_interfaces.png", "The doctor sees only the linked schedule and queue. The assistant summarises that doctor's booked pressure, while queue actions operate the assigned patients through controlled transitions."),
        ("4.6", "Administrator configuration, audit, and operational assistance", "13_administrator_interfaces.png", "The administrator configures schedules, reviews immutable audit events, and obtains approved aggregate information. The assistant does not expose patient names or modify configuration."),
    ]
    for number, title, filename, explanation in figures:
        add_figure(document, number, title, DIAGRAM_DIR / filename, width=6.2, source="Source: Synthetic demonstration data captured from the implemented local release candidate.")
        add_text(document, explanation)


def chapter_four(document: Document) -> None:
    chapter(
        document,
        4,
        "Implementation and Results",
        "This chapter describes the implemented environment and modules, shows the working interfaces, and reports the verified software quality evidence with clear limits on what local testing can prove.",
    )
    add_heading(document, "4.1 Environment Setup", 2)
    environment = [
        ["Frontend", "React 19.2.8, React Router 7.18.2, Vite 8.2.1, Tailwind CSS 4.3.3, JavaScript"],
        ["Backend", "Python 3.14.7, Django 5.2 LTS, Django REST Framework, Gunicorn"],
        ["Database", "PostgreSQL 18.6 in local, test, staging and production definitions"],
        ["Gateway", "Caddy serving built assets and proxying /api/v1 on the same origin"],
        ["Containers", "Docker Compose with nonroot runtime, read only filesystems and private networks where applicable"],
        ["Testing", "Django TestCase and transaction tests, Coverage.py, Vitest, Testing Library, Playwright Chromium, axe and k6"],
        ["Security checks", "Django deployment check, Bandit, Semgrep, dependency audit, container configuration and secret scan"],
        ["Repository", "Private GitHub repository with short lived branches, pull requests and required automated checks"],
    ]
    add_table(document, "4.1", "Implementation environment", ["Layer", "Implemented technology"], environment, widths=[1.25, 4.95], font_size=9)
    add_text(
        document,
        "Exact direct and transitive dependencies are committed in lockfiles. The development service supports live frontend work, while test and production definitions build immutable assets. The API and worker share the same backend image so they cannot silently drift. Migrations use a database owner account; the long running API uses a separate restricted runtime account in controlled environments.",
    )

    add_heading(document, "4.2 Backend and Database Implementation", 2)
    add_text(
        document,
        "The backend is organised into accounts, directory, operations, communications, help_assistant, and shared core modules. Accounts implements custom users, role assignment, invitations, patient and staff onboarding, MFA, account tokens, login audit, and session controls. Directory implements hospital configuration, departments, locations, chambers, doctor profiles, patient profiles, privacy notice versions, consent, duplicate warnings, and correction history. Operations contains schedules, appointments, queue sessions and tickets, estimates, payments, histories, dashboards, and service functions. Communications contains in application notifications and the email outbox. Core contains stable exceptions, permissions, middleware, throttling, audit, idempotency, logging, and health checks.",
    )
    add_text(
        document,
        "Views remain thin around serializer validation, role filtered lookup, and service invocation. Competing writes run in atomic blocks and acquire rows in a consistent order. For example, rescheduling locks the appointment and both schedule allocations before changing capacity. Call next locks the queue session before selecting an eligible waiting ticket. Append only database triggers protect histories and audit style records from ordinary update or delete operations even if future application code makes a mistake.",
    )

    add_heading(document, "4.3 Frontend and Role Interface Implementation", 2)
    add_text(
        document,
        "The frontend uses route guards for usability, but relies on the API for authority. AuthContext retrieves the current server session, BrandContext retrieves safe hospital presentation values, and the API client obtains a CSRF token before state changing requests. Shared components implement panels, forms, status pills, dialogs, loading placeholders, feedback, pagination, and accessible focus behaviour. Each role has a separate layout and navigation set. Polling logic stops unnecessary foreground frequency when the page is in the background and marks stale data after failed refreshes.",
    )
    add_text(
        document,
        "The assistant is a global authenticated widget. It opens from every role workspace, uses role specific suggestions, labels whether an answer used live information, provides safe internal links returned by the server, and never renders arbitrary HTML. Conversation history is kept short in component state rather than written to browser storage.",
    )

    add_heading(document, "4.4 Deployment and Recovery Implementation", 2)
    add_figure(document, "4.1", "Pilot deployment and recovery topology", DIAGRAM_DIR / "07_deployment_topology.png")
    add_text(
        document,
        "The planned pilot host has 4 vCPU, 8 GiB RAM, 160 GiB NVMe storage, Ubuntu 24.04 LTS, a Bangladesh location, key based SSH, and a firewall exposing only approved management access and HTTPS. PostgreSQL has no public port. Caddy applies HTTPS and response headers. Production secrets live outside Git in a protected environment file. Images are released by immutable digest through an approved environment.",
    )
    add_text(
        document,
        "Backup design uses pgBackRest with encrypted daily full backups and hourly recovery points on separately approved storage, retained for 30 days. Timers, backup age checks, clean restore instructions, and database reconciliation are included. A rollback distinguishes application rollback from incompatible schema reversal. When a safe reverse migration is unavailable, the documented decision is forward correction or restoration to a verified recovery point.",
    )

    add_heading(document, "4.5 Hospital Management System Interface Results", 2)
    add_text(
        document,
        "The following figures were captured from the running application with synthetic Bengali names. They demonstrate the implemented navigation and representative actions. No production identity, patient record, MFA secret, password, API key, or real email address appears in the evidence.",
    )
    add_interface_evidence(document)

    add_heading(document, "4.6 Testing and Evaluation", 2)
    add_text(
        document,
        "The final working tree was checked at multiple layers. Backend tests ran against PostgreSQL rather than an easier substitute. Frontend tests covered API contracts, authentication context, queue polling, shared components, formatting and the assistant. Browser tests exercised the assembled same origin system. Failure cases were asserted deliberately, so warning and error log entries produced by a test do not indicate a failed suite when the expected response and rollback are verified.",
    )
    results = [
        ["Backend suite", "129 Django tests", "Passed", "87 percent line coverage; PostgreSQL 18; migrations and system check clean"],
        ["Frontend suite", "57 Vitest tests in 8 files", "Passed", "86.87 percent statements; 88.88 percent lines; production build passed"],
        ["Browser workflow", "6 Chromium role scenarios", "Passed", "Public service, availability, staff MFA, reception check in, patient queue and doctor queue"],
        ["Quick local load", "50 virtual users, 3,638 requests", "Passed", "4.23 ms read p95 and no failed checked response in recorded local run"],
        ["Backup recovery", "Encrypted backup and clean isolated restore", "Passed", "Synthetic business records reconciled after restore"],
        ["Security and supply chain", "Source, dependency, image, filesystem and secret checks", "Passed", "Latest required GitHub checks reported no unresolved high or critical finding"],
        ["Compose and image", "Local, test and production rendering and build checks", "Passed", "Caddy validation, nonroot/read only rules and health paths checked"],
        ["Hospital UAT", "Named doctor, reception and administrator sign off", "Pending", "Must be completed on external staging before real patient approval"],
        ["Full staging load", "30 minute mixed read and write workload", "Pending", "Requires production sized external staging and monitoring"],
    ]
    add_table(document, "4.2", "Verification result summary", ["Evidence", "Scope", "Result", "Interpretation"], results, widths=[1.3, 1.65, 0.65, 2.6], font_size=8)

    add_heading(document, "4.7 Functional, Permission, and Concurrency Results", 2)
    scenarios = [
        ["T01", "Two patients compete for the final slot", "Exactly one booking commits; the other receives a conflict; capacity remains valid"],
        ["T02", "The same booking, check in, queue or payment request repeats", "The stored idempotent outcome returns and no duplicate business record appears"],
        ["T03", "Two staff users call next at the same time", "One ticket becomes called and the queue retains one active service position"],
        ["T04", "A patient changes an appointment UUID", "No other patient's record, existence detail or side effect is disclosed"],
        ["T05", "A doctor requests a different doctor's queue", "Role filtered lookup denies access"],
        ["T06", "A patient views the live queue", "Only own token and public served token are present; no other patient name is returned"],
        ["T07", "Cancellation, late arrival, defer, restore, no show and completion", "Only documented transitions succeed and required reasons enter history"],
        ["T08", "SMTP delivery fails", "Business transaction remains committed and outbox retry state advances safely"],
        ["T09", "Queue polling loses connectivity", "The page shows stale or reconnecting state and resumes without duplicating actions"],
        ["T10", "Staff login, lockout, reset, CSRF and session expiry", "Unauthorised paths fail with the stable response contract and audit evidence"],
        ["T11", "Assistant question attempts prompt injection or asks for medical advice", "Provider is not called; the answer refuses or returns bounded local guidance"],
        ["T12", "Assistant asks for live data as each role", "Patient and doctor facts remain owned; staff summaries contain approved aggregate values"],
    ]
    add_table(document, "4.3", "Representative critical test cases", ["ID", "Scenario", "Pass condition"], scenarios, widths=[0.5, 2.25, 3.45], font_size=8)

    add_heading(document, "4.8 Performance Evaluation", 2)
    add_text(
        document,
        "The recorded quick local load test ramped to 50 virtual users, held for 60 seconds, and sent 3,638 checked requests through the assembled reverse proxy to public read paths. Its 4.23 millisecond p95 was well below the 500 millisecond quick gate. This proves that the tested local read path remained responsive under that narrow run. It does not prove production network latency, authenticated write capacity, long duration database behaviour, queue freshness under mixed work, or SMTP recovery.",
    )
    add_text(
        document,
        "The release workload remains a five minute ramp to 50 concurrent users, 30 minutes at that level, and five minute ramp down on production sized staging. It mixes directory and availability reads, dashboards, conditional queue snapshots, booking, reception search and check in, doctor transitions, administration reads, and notification recovery. Read p95 must remain below 500 milliseconds, write p95 below 800 milliseconds, unexpected errors below one percent, and queue freshness within 15 seconds. Business reconciliation must then prove that no capacity, token, state, payment, or outbox invariant was lost.",
    )

    add_heading(document, "4.9 Security and Recovery Results", 2)
    add_text(
        document,
        "The final repository revision passed the configured source, dependency, filesystem, container, configuration, and secret reviews. The private GitHub workflows completed backend, frontend, image, Python dependency, JavaScript dependency, and filesystem security jobs before the report revision was merged. The local secret scan found no Groq key pattern, and the supplied academic material, local environment files, report QA files, and temporary report build files remain ignored by Git.",
    )
    add_text(
        document,
        "The recovery exercise used an isolated project and synthetic marker. It created an encrypted full backup, verified the backup repository, removed only the named recovery database volume, restored into a clean volume, and reconciled the expected record. This verifies the local container and encryption procedure. It does not prove off site credentials, the one hour recovery point objective, or the four hour recovery time objective on the hospital's future infrastructure.",
    )

    add_heading(document, "4.10 Results and Discussion", 2)
    add_text(
        document,
        "The implementation satisfies the defined academic and local software goals. A patient can complete the discovery and appointment path, reception can bridge scheduled and walk in patients into one queue, a doctor can operate the assigned queue, and an administrator can configure and audit the service. Queue information is more useful than a simple token because it includes a wait range, confidence and freshness. The role aware assistant reduces navigation uncertainty while remaining read only and useful without a paid provider.",
    )
    add_text(
        document,
        "The strongest technical result is not the number of pages or endpoints. It is the consistent treatment of repeated and competing actions. Idempotency controls a repeated client request, row locks control concurrent service execution, constraints protect the database, histories explain the result, and frontend feedback reports it. These layers address different failure modes and cannot replace one another.",
    )
    add_text(
        document,
        "The evidence also reveals clear limits. Automated coverage above the threshold does not prove that every hospital user understands the wording. A fast local read test does not establish production capacity. A successful isolated restore does not prove that off host credentials and incident responders are ready. The report therefore marks external UAT, full staging load, legal approval, live SMTP, final branding, and controlled pilot acceptance as pending rather than converting plans into false results.",
    )

    add_heading(document, "4.11 Overall Result Summary", 2)
    overall_results = [
        ["Role based access", "Four authenticated workspaces plus public pages", "Implemented and covered by API and browser tests"],
        ["Directory and schedules", "Departments, locations, chambers, doctor profiles, schedules, closures, and computed slots", "Implemented with administrative and public projections"],
        ["Appointment workflow", "Registration, booking, rescheduling, cancellation, check in, and walk ins", "Implemented with idempotency, capacity locking, and history"],
        ["Queue workflow", "Token allocation, call, start, defer, restore, complete, no show, cancel, and leave", "Implemented with transactional state rules and privacy safe patient view"],
        ["Adaptive arrival", "Median blend, uncertainty range, confidence, freshness, and audit record", "Implemented; real operational accuracy evaluation remains pending"],
        ["Role aware assistant", "System guidance and allowlisted live facts with local fallback", "Implemented as read only; external provider remains optional"],
        ["Quality evidence", "129 backend tests, 57 frontend tests, 6 browser workflows, security checks, load gate, and restore", "All recorded local and repository checks passed"],
        ["Real patient launch", "External staging, legal review, hospital UAT, production SMTP, off site restore, and pilot approval", "Pending and intentionally release blocking"],
    ]
    add_table(document, "4.4", "Overall implementation and result summary", ["Component", "Main outcome", "Result"], overall_results, widths=[1.25, 3.0, 1.95], font_size=8)

    add_heading(document, "4.12 Comparative Analysis", 2)
    analytical = [
        ["Cayirli and Veral [1]", "Appointment system design and variability", "Shows that scheduling decisions interact with uncertainty", "The project combines capacity protected booking with a separate observed queue rather than assuming the booked time equals actual service order"],
        ["Gupta and Denton [3]", "Access, preferences, capacity, and uncertainty", "Describes practical complexity in appointment scheduling", "The implementation represents schedules, exceptions, capacity, cancellation, and rescheduling as explicit records and transactions"],
        ["Dantas et al. [5]", "Appointment nonattendance", "Reviews no show causes and approaches", "The workflow includes reminders, cancellation, explicit no show state, and history without using a hidden risk score"],
        ["Ansell et al. [7]", "Interventions to reduce waiting", "Reports several patient centred approaches with context dependent effects", "The Adaptive Arrival Window communicates current progress and uncertainty but makes no unsupported claim of universal wait reduction"],
        ["McLean et al. [8] and Zhao et al. [9]", "Reminder and digital notification evidence", "Supports reminders while recognising delivery and context limitations", "The system commits business actions first and delivers minimal notifications through a retryable outbox"],
        ["Woodcock et al. [11]", "Automated patient self scheduling", "Identifies workflow, integration, and usability factors beyond a calendar", "The patient path is joined to reception, queue, notifications, consent, payment status, and staff operations"],
    ]
    add_table(document, "4.5", "Analytical comparison between related studies and the proposed system", ["Study", "Main focus", "Reported direction", "Relation to proposed work"], analytical, widths=[1.25, 1.45, 1.65, 1.85], font_size=7)

    add_heading(document, "4.13 Summary", 2)
    add_text(
        document,
        "The implemented candidate covers the intended outpatient operations, adaptive queue and role aware assistance. Automated evidence is strong for the local revision and the interface screenshots demonstrate real workflows with synthetic data. Organisational and external infrastructure gates remain before live use.",
    )


def chapter_five(document: Document) -> None:
    chapter(
        document,
        5,
        "Engineering Standards and Design Challenges",
        "This chapter relates the project to relevant engineering standards, evaluates its social and professional responsibilities, explains management and financial assumptions, and maps the work to complex engineering problem and activity categories.",
    )
    add_heading(document, "5.1 Compliance with the Standards", 2)
    add_heading(document, "5.1.1 Software Standards", 3)
    standards = [
        ["WCAG 2.2 AA [19]", "Accessible web content", "Semantic structure, keyboard operation, focus, labels, contrast, reflow, target size, errors and status messages"],
        ["OWASP ASVS 5.0 Level 2 [20]", "Application security verification", "Authentication, session, access control, validation, data protection, API and configuration test catalogue"],
        ["NIST SP 800-218 [18]", "Secure software development", "Tracked security requirements, protected environments, automated checks, component provenance and response to defects"],
        ["NIST SP 800-63B [21]", "Authentication guidance", "Password, authenticator, rate limit, session and recovery design considerations"],
        ["Django security guidance [22]", "Framework specific protection", "CSRF, host validation, HTTPS, cookies, SQL parameterisation, output handling and deployment checks"],
        ["PostgreSQL 18 documentation [23], [24]", "Transactional integrity", "Row locking, uniqueness, check constraints and referential integrity"],
        ["Bangladesh Core FHIR guide [26]", "Future interoperability", "Stable identifiers retained for later mapping; no conformance claim in this release"],
        ["Bangladesh Government Gazette [25]", "Current legal source", "Qualified applicability, retention, data location and organisational review required before real data"],
    ]
    add_table(document, "5.1", "Standards and guidance mapping", ["Source", "Area", "Project application"], standards, widths=[1.65, 1.45, 3.1], font_size=8)

    add_heading(document, "5.1.2 Hardware Standards", 3)
    add_text(
        document,
        "The pilot assumes standards compliant patient and staff browsers rather than proprietary terminals. Reception work is suited to a desktop or laptop with a reliable local network, while patient pages support ordinary mobile displays. The production baseline is a 4 vCPU, 8 GiB RAM, 160 GiB NVMe server with separate approved backup storage. Capacity, disk growth, memory, database connections, certificate expiry, and backup age must be monitored before the hospital increases its workload.",
    )

    add_heading(document, "5.1.3 Communication Standards", 3)
    add_text(
        document,
        "Browser communication uses HTTPS and JSON over a versioned REST interface. The same origin arrangement makes cookie and CSRF boundaries easier to reason about. Email leaves the system only through an approved SMTP service and contains minimal operational text plus a secure link. No SMS or online payment gateway is connected. The database is not public. Future interoperability may map stable identifiers to Bangladesh Core FHIR resources, but the current release has not passed FHIR profile validation and is not presented as conformant.",
    )

    add_heading(document, "5.2 Impact on Society, Environment and Sustainability", 2)
    add_heading(document, "5.2.1 Impact on Life", 3)
    add_text(
        document,
        "A clearer appointment and queue experience can reduce unnecessary waiting and repeated enquiries. Privacy safe tokens reduce disclosure in a crowded waiting area. Bengali synthetic names and Bangladesh time and currency make the demonstration relevant to the intended environment. However, digital access can exclude people without email, confidence, literacy, vision, motor ability, or reliable connectivity. Reception assisted registration, account claiming, plain language, responsive layout, keyboard support, and a downtime paper reconciliation procedure are therefore part of the design rather than optional decoration.",
    )
    add_text(
        document,
        "Safety is protected by the nonclinical boundary. A queue estimate may help a patient plan arrival, but it must never tell a person whether symptoms are urgent. The assistant refuses medical advice and directs emergencies to the hospital's approved emergency channel. Staff retain responsibility for operational overrides, and each override leaves a reason. The system should never be used to deny care merely because a patient is not digitally connected.",
    )

    add_heading(document, "5.2.2 Impact on Society and Environment", 3)
    add_text(
        document,
        "The system supports society by making doctor availability, appointment status, and queue progress easier to understand without requiring patients to disclose their information in a public waiting area. Environmentally, the selected architecture avoids dedicated kiosks, a permanent WebSocket cluster, and an additional cache or message broker at pilot scale. Static assets are built once, unchanged queue snapshots use conditional requests, and bounded polling reduces unnecessary network and compute use. These choices reduce avoidable resource use but do not constitute a formal carbon assessment.",
    )

    add_heading(document, "5.2.3 Ethical Aspects", 3)
    add_text(
        document,
        "Purpose limitation is the main ethical rule. Data collected to book and operate a visit should not silently become advertising, model training, or unrelated profiling data. The system stores no diagnosis, symptom, prescription, or card data. Consent points to the exact published privacy notice version. Staff access is role limited and reviewable. Demonstrations use synthetic identities. Logs and emails use minimal content. The optional assistant receives only allowlisted facts and cannot write to business records.",
    )
    add_text(
        document,
        "Transparency also applies to estimation. The patient receives a range and confidence rather than a false promise. Staff can see why an estimate was produced and must explain overrides. The hospital must approve the language used for consent, retention, incident communication, and patient correction. Legal review cannot be replaced by a software statement saying that the service is compliant.",
    )

    add_heading(document, "5.2.4 Sustainability Plan", 3)
    add_text(
        document,
        "The design favours a small operational footprint, supported software, container reuse, conditional responses, bounded polling and one database. Fewer services reduce idle compute, backup complexity and operator training. Sustainable operation also includes routine patching, image rebuilds, storage monitoring, deletion according to an approved retention schedule, and deactivation instead of unnecessary duplication. Accessibility and assisted workflows support social sustainability by keeping the service usable for more patients.",
    )
    add_text(
        document,
        "Operational sustainability requires a named service owner, routine access review, tested backup restoration, monitored certificate and storage health, funded support, and documented staff training. The controlled department pilot must be evaluated before the hospital expands the service. These responsibilities remain necessary even though the selected software dependencies have low direct licence cost.",
    )

    add_heading(document, "5.3 Project Management and Financial Analysis", 2)
    add_text(
        document,
        "The emergency delivery window required strict priority. Identity, authorization, booking integrity, queue integrity, recovery and evidence were Priority 0. Visual polish and secondary reports followed only when those controls were stable. The task register used one owner and one verifiable completion condition per item. Defects were classified by consequence; a privacy exposure, privilege error, corrupted booking, unsafe queue or failed recovery path blocked release.",
    )
    finance = [
        ["VPS and storage", "Recurring", "4 vCPU, 8 GiB RAM, NVMe host and separately approved backup storage"],
        ["Domain, DNS and TLS operations", "Recurring", "Approved domain and monitored certificate; automated TLS certificate itself may have no licence fee"],
        ["Transactional email", "Recurring", "Volume based approved SMTP service with bounce and delivery monitoring"],
        ["Operations and support", "Recurring", "Named staff time for patching, access review, monitoring, backup and incident response"],
        ["Security and legal review", "Initial and periodic", "Independent application review and Bangladesh legal or policy mapping"],
        ["Training and UAT", "Initial and per release", "Doctor, reception, administrator and support rehearsal with synthetic records"],
        ["Software licences", "Low direct cost", "Selected application dependencies are open source; organisational support cost remains"],
    ]
    add_table(document, "5.2", "Cost categories for procurement", ["Category", "Timing", "Procurement note"], finance, widths=[1.55, 1.1, 3.55], font_size=8)
    add_text(
        document,
        "No vendor price is presented as a current quotation. The hospital should request local quotations for infrastructure, off host backup, SMTP, monitoring, assessment, and support, then approve a twelve month operating budget. The main financial risk is not framework licence cost; it is underfunding the people and recovery processes that keep patient operations trustworthy.",
    )

    add_heading(document, "5.4 Complex Engineering Problem", 2)
    add_heading(document, "5.4.1 Complex Problem Solving", 3)
    add_text(
        document,
        "The project qualifies as a complex engineering problem because it combines conflicting stakeholder needs, security and privacy consequences, concurrent state changes, uncertain service duration, recovery requirements, accessibility, and a constrained deployment environment. A correct answer could not be obtained by producing forms and database tables alone. The solution required analysis of boundaries, failure modes, competing actions, information disclosure, operational responsibility, and evidence after correction.",
    )
    ep_rows = [
        ["EP1", "Depth of knowledge", "Requires web engineering, transactions, security, accessibility, queue operations, recovery and healthcare data responsibility together."],
        ["EP2", "Conflicting requirements", "Fast access conflicts with privacy; flexible reception conflicts with strict integrity; freshness conflicts with simple infrastructure."],
        ["EP3", "Depth of analysis", "State machines, contention, failure recovery, object authorization and estimation uncertainty require analysis beyond a CRUD application."],
        ["EP4", "Familiarity of issues", "Booking pages are familiar, but fair queue overrides, cross role data minimisation and real data launch authority are less routine."],
        ["EP5", "Applicable codes", "Multiple guidance sources apply and require interpretation; none alone defines the complete local design."],
        ["EP6", "Stakeholder involvement", "Patients, doctors, reception, administrators, operators, institutional reviewers and legal advisers have different authority and needs."],
        ["EP7", "Interdependence", "A schedule change affects capacity, appointments, queues, notifications, audit, reports, tests and recovery."],
    ]
    add_table(document, "5.3", "Mapping with complex engineering problem characteristics", ["Code", "Characteristic", "Project rationale"], ep_rows, widths=[0.6, 1.55, 4.05], font_size=8)

    add_heading(document, "5.4.2 Mapping with Knowledge Profile for EP1", 3)
    kp_rows = [
        ["K1", "Natural sciences", "Understanding that clinical service duration varies, without modelling clinical decisions."],
        ["K2", "Mathematics", "Median, median absolute deviation, bounded ranges, percentiles, rate and capacity calculations."],
        ["K3", "Engineering fundamentals", "Modularity, interfaces, state, concurrency, testing, observability and failure handling."],
        ["K4", "Specialist knowledge", "Django, React, PostgreSQL locking, web security, MFA, containers and accessible interaction."],
        ["K5", "Engineering design", "Balancing role workflow, privacy, scale, maintainability, availability and recovery."],
        ["K6", "Engineering practice", "Git review, continuous integration, migrations, infrastructure definition, backup, restore and incident runbooks."],
        ["K7", "Comprehension", "Explaining constraints and evidence to both technical and hospital stakeholders."],
        ["K8", "Research literature", "Using peer reviewed scheduling and attendance literature plus primary technical standards."],
    ]
    add_table(document, "5.4", "Mapping with knowledge profile", ["Code", "Knowledge area", "Application in the project"], kp_rows, widths=[0.6, 1.55, 4.05], font_size=8)

    add_heading(document, "5.4.3 Engineering Activities", 3)
    ea_rows = [
        ["EA1", "Range of resources", "Source documents, application code, database, containers, cloud repository, standards, research, test tools and operational procedures."],
        ["EA2", "Level of interaction", "Continuous coordination across four user roles, academic supervision, development, operations and approval owners."],
        ["EA3", "Innovation", "Transparent adaptive arrival range and role aware live assistant integrated with transactional queue evidence."],
        ["EA4", "Consequences", "A defect can expose patient identity, waste capacity, alter service order or prevent recovery, so release gates reflect consequence."],
        ["EA5", "Familiarity", "Common web technologies are applied to less routine hospital workflow, privacy and concurrent state problems."],
    ]
    add_table(document, "5.5", "Mapping with complex engineering activities", ["Code", "Activity", "Project rationale"], ea_rows, widths=[0.6, 1.45, 4.15], font_size=8)

    add_heading(document, "5.5 Design Challenges and Constraints", 2)
    add_text(
        document,
        "The limited infrastructure influenced the use of conditional polling and a database outbox instead of permanent socket infrastructure and a separate message broker. The main software challenge was maintaining one valid business result when requests repeat or compete. Booking, rescheduling, check in, queue advancement, and payment correction affect several records, so transactions, row locks, idempotency, constraints, and append only histories work together rather than relying on the visible button state.",
    )
    add_text(
        document,
        "The second challenge was communicating useful queue progress without disclosing another patient or presenting uncertain timing as a promise. The solution uses public tokens, a bounded waiting range, confidence, freshness, a nonclinical boundary, and recorded staff overrides. The third challenge was providing role aware assistance without broad database access. The assistant therefore uses server prepared allowlisted context, read only handlers, safe refusal rules, and a deterministic local fallback.",
    )

    add_heading(document, "5.6 Risk Analysis", 2)
    risks = [
        ["Unauthorized access to patient records", "High", "Default deny roles, filtered querysets, object checks, MFA for staff, audit, and permission tests", "Hospital access review and incident response rehearsal"],
        ["Double booking or invalid capacity", "High", "Atomic services, schedule locks, unique constraints, idempotency, and last capacity concurrency test", "Full mixed write workload on production sized staging"],
        ["Duplicate or unfair queue action", "High", "Queue session lock, one active service constraint, legal transitions, recorded defer and restore reasons", "Doctor and reception UAT during a controlled department pilot"],
        ["Queue privacy disclosure", "High", "Token only patient projection, no other patient name, narrow staff view, API and browser privacy tests", "Waiting area observation and hospital privacy approval"],
        ["Assistant discloses or invents information", "Medium", "Allowlisted role context, read only endpoint, injection and medical refusal rules, local fallback", "Processor approval and sampled response review before provider use"],
        ["Notification provider failure", "Medium", "Database outbox, bounded retry, attempt history, and business transaction separation", "Production SMTP bounce, delay, and alert testing"],
        ["Database or host failure", "High", "Encrypted backup procedure, clean local restore, health checks, and documented rollback", "Approved off site storage and timed external restoration exercise"],
        ["Legal or retention decision incomplete", "High", "Synthetic data only and explicit real data gate", "Qualified Bangladesh legal review and hospital policy approval"],
    ]
    add_table(document, "5.6", "Major project risks and mitigation strategies", ["Risk", "Impact", "Implemented mitigation", "Remaining control"], risks, widths=[1.25, 0.65, 2.65, 1.65], font_size=7)

    add_heading(document, "5.7 Summary", 2)
    add_text(
        document,
        "The project required choices across standards, software, operations, ethics, accessibility, cost and recovery. Its complexity comes from interdependent consequences rather than from an excessive number of technologies. The mappings show how theoretical knowledge and engineering practice meet in the implemented candidate.",
    )


def chapter_six(document: Document) -> None:
    chapter(
        document,
        6,
        "Conclusion",
        "This chapter summarises the completed work and major findings, traces the achieved objectives, states the limitations, and identifies a controlled path for future development after the hospital reviews the production candidate.",
    )
    add_heading(document, "6.1 Summary", 2)
    add_text(
        document,
        "The project transformed a basic university appointment idea into a complete nonclinical hospital operations candidate. It supports patient registration and account claiming, doctor and location configuration, scheduling and closures, capacity based booking, rescheduling, cancellation, check in, walk ins, queue control, onsite payment status, notifications, consent, audit, and role dashboards. React, Django REST Framework, PostgreSQL, Caddy and Docker are combined through one versioned same origin application.",
    )
    add_text(
        document,
        "The Adaptive Arrival Window improves the information available around a first in first out queue without pretending to perform medical triage. The role aware assistant explains the system and can answer controlled live questions while remaining read only, role scoped, and functional through its local guide when the provider is unavailable. The design protects material writes with idempotency, row locks, constraints, histories and audit evidence.",
    )
    add_text(
        document,
        "The final local revision has repeatable backend, frontend, browser, security, dependency, container, load and recovery evidence. Documentation covers planning, implementation, workflows, production, tests, defects, auditing, the advanced mechanism and the assistant. This supports academic evaluation and staging preparation. It does not remove the hospital's responsibility to approve people, policy, infrastructure and real data use.",
    )

    add_heading(document, "6.2 Major Findings", 2)
    add_text(
        document,
        "The first finding is that appointment and queue correctness depends on the database transaction, not on the visible button state. Idempotency protects exact client retries, row locks serialize competing business actions, database constraints protect the final invariant, and history records explain the committed result. These controls solve different problems and were most effective when used together.",
    )
    add_text(
        document,
        "The second finding is that useful queue communication does not require disclosure of patient identity or automatic priority. A public token, people ahead, bounded wait range, confidence, location, and freshness provide a practical patient view. The third finding is that operational assistance can remain useful without unrestricted artificial intelligence access. The local guide and allowlisted role facts answer core questions even when the external provider is disabled.",
    )
    add_text(
        document,
        "The fourth finding is that a tested local application and an approved live hospital service are different outcomes. The software checks establish strong evidence for the implemented revision, but legal review, external infrastructure, hospital policies, named users, monitored restoration, and signed acceptance still require organizational authority.",
    )

    add_heading(document, "6.3 Achievement of Objectives", 2)
    objective_results = [
        ["O1", "Provide four role based workspaces", "Patient, doctor, receptionist, and administrator interfaces and API permissions are implemented", "Achieved"],
        ["O2", "Manage hospital directory and schedules", "Departments, locations, chambers, doctors, schedules, closures, fees, and capacity are implemented", "Achieved"],
        ["O3", "Protect patient registration and consent", "Unique MRN, duplicate warnings, account claim, privacy notice version, and consent history are implemented", "Achieved"],
        ["O4", "Implement complete appointment operations", "Booking, rescheduling, cancellation, walk in, check in, and payment status are transactional", "Achieved"],
        ["O5", "Provide a private and fair queue", "Token only patient view and controlled call, start, defer, restore, complete, and no show states are implemented", "Achieved"],
        ["O6", "Implement Adaptive Arrival Window", "Bounded estimate, confidence, freshness, sample evidence, and override history are implemented", "Achieved; pilot accuracy pending"],
        ["O7", "Provide role aware assistance", "Read only local guidance and allowlisted live facts are implemented with optional provider fallback", "Achieved"],
        ["O8", "Produce quality and deployment evidence", "Automated suites, browser workflows, security checks, load gate, containers, and clean restore passed", "Achieved locally"],
        ["O9", "Prepare real patient deployment", "Procedures and gates are documented, but external staging, legal review, UAT, and hospital approval remain", "Partially achieved"],
    ]
    add_table(document, "6.1", "Compact objective traceability summary", ["ID", "Objective area", "Completed evidence", "Status"], objective_results, widths=[0.45, 1.45, 3.55, 0.75], font_size=7)

    add_heading(document, "6.4 Limitation", 2)
    limitations = [
        ["Single hospital and outpatient scope", "The system is not an electronic medical record or complete hospital information suite", "Evaluate wider modules only through separately governed projects"],
        ["No representative service history", "Adaptive waiting accuracy and patient benefit are not yet measured", "Collect controlled pilot data and compare interval error and coverage"],
        ["Limited browser acceptance evidence", "Automated release evidence uses pinned Chromium", "Complete Firefox, WebKit, Edge, mobile, keyboard, and screen reader UAT"],
        ["Narrow local load evidence", "The 50 user quick read gate does not prove mixed production writes", "Run the 30 minute authenticated mixed workload on production sized staging"],
        ["External services not provisioned", "Domain, SMTP, monitoring, off site backup, and incident rota are not active", "Procure, configure, monitor, and rehearse the approved environment"],
        ["Hospital policy not approved", "Privacy, consent, retention, correction, downtime, and legal mapping remain organizational decisions", "Obtain qualified legal review and signed hospital approval"],
        ["External assistant provider optional", "Provider availability and processor terms may change", "Keep local fallback and enable a protected replacement key only after approval"],
        ["Interoperability and wider modules excluded", "No FHIR conformance, SMS, online payments, clinical, insurance, or inpatient function", "Treat each future integration as a separately reviewed extension"],
    ]
    add_table(document, "6.2", "Current limitations and possible improvement directions", ["Limitation", "Current effect", "Possible improvement"], limitations, widths=[1.55, 2.25, 2.4], font_size=7)

    add_heading(document, "6.5 Future Work", 2)
    add_text(
        document,
        "The immediate next work is operational rather than feature expansion. The hospital should approve branding and policies, procure staging, configure named staff and MFA, run signed role UAT, complete the mixed load test, exercise alert delivery, restore from separate storage, rehearse rollback, review the assistant's processor boundary, and operate one department with synthetic records before the real data decision.",
    )
    add_text(
        document,
        "After enough valid service history is collected, the estimate can be evaluated by doctor, day and service pattern. Any modification should remain explainable, compare against the current median baseline, report interval coverage, and undergo fairness review. A prediction model should not be introduced merely because data exists. Patient comprehension and arrival behaviour are as important as numerical error.",
    )
    add_text(
        document,
        "Later product work may include approved bilingual content, SMS through a reviewed provider, a progressive web application, richer operational reporting, integration with an existing clinical record through validated Bangladesh Core FHIR profiles, and multi location capacity. Clinical notes, prescriptions, diagnosis, triage, payment processing, or insurance would require separate governance, threat modelling, domain expertise, consent, tests and deployment approval rather than an unreviewed extension of this database.",
    )

    add_heading(document, "6.6 Final Conclusion", 2)
    add_text(
        document,
        "A hospital system should be judged by the records it protects and the failures it handles, not only by the screens it displays. This project establishes a practical foundation for appointment and queue operations with visible limits, repeatable evidence, and a clear route from academic demonstration to a controlled hospital pilot.",
    )


def references(document: Document) -> None:
    page_break(document)
    heading = document.add_heading("References", level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
    heading.paragraph_format.space_after = Pt(18)
    refs = [
        "[1] T. Cayirli and E. Veral, “Outpatient scheduling in health care: A review of literature,” Production and Operations Management, vol. 12, no. 4, pp. 519–549, 2003, doi: 10.1111/j.1937-5956.2003.tb00218.x.",
        "[2] T. Cayirli, E. Veral, and H. Rosen, “Designing appointment scheduling systems for ambulatory care services,” Health Care Management Science, vol. 9, no. 1, pp. 47–58, 2006, doi: 10.1007/s10729-006-6279-5.",
        "[3] D. Gupta and B. Denton, “Appointment scheduling in health care: Challenges and opportunities,” IIE Transactions, vol. 40, no. 9, pp. 800–819, 2008, doi: 10.1080/07408170802165880.",
        "[4] A. Ahmadi-Javid, Z. Jalali, and K. J. Klassen, “Outpatient appointment systems in healthcare: A review of optimization studies,” European Journal of Operational Research, vol. 258, no. 1, pp. 3–34, 2017, doi: 10.1016/j.ejor.2016.06.064.",
        "[5] L. F. Dantas, J. L. Fleck, F. L. Cyrino Oliveira, and S. Hamacher, “No-shows in appointment scheduling: A systematic literature review,” Health Policy, vol. 122, no. 4, pp. 412–421, 2018, doi: 10.1016/j.healthpol.2018.02.002.",
        "[6] J. Rivas, “Advanced access scheduling in primary care: A synthesis of evidence,” Journal of Healthcare Management, vol. 65, no. 3, pp. 171–184, 2020, doi: 10.1097/JHM-D-19-00047.",
        "[7] D. Ansell, J. A. G. Crispo, B. Simard, and L. Bjerre, “Interventions to reduce wait times for primary care appointments: A systematic review,” BMC Health Services Research, vol. 17, art. 295, 2017, doi: 10.1186/s12913-017-2219-y.",
        "[8] S. McLean et al., “Appointment reminder systems are effective but not optimal: Results of a systematic review and evidence synthesis employing realist principles,” Patient Preference and Adherence, vol. 10, pp. 479–499, 2016, doi: 10.2147/PPA.S93046.",
        "[9] Y. Zhao et al., “Using digital notifications to improve attendance in clinic: Systematic review and meta-analysis,” BMJ Open, vol. 7, e012116, 2017, doi: 10.1136/bmjopen-2016-012116.",
        "[10] D. Carreras-García, D. Delgado-Gómez, F. Llorente-Fernández, and A. Arribas-Gil, “Patient no-show prediction: A systematic literature review,” Entropy, vol. 22, no. 6, art. 675, 2020, doi: 10.3390/e22060675.",
        "[11] E. W. Woodcock, “Barriers to and facilitators of automated patient self-scheduling for health care organizations: Scoping review,” Journal of Medical Internet Research, vol. 24, no. 1, e28323, 2022, doi: 10.2196/28323.",
        "[12] Practo, “Practo Instant appointment booking,” Practo Help. [Online]. Available: https://help.practo.com/practo-search/what-is-practo-instant/. [Accessed: Sep. 4, 2026].",
        "[13] Qminder, “Queue management system for healthcare,” Qminder. [Online]. Available: https://www.qminder.com/industries/healthcare/. [Accessed: Sep. 4, 2026].",
        "[14] Doctolib, “Solutions for healthcare professionals,” Doctolib. [Online]. Available: https://about.doctolib.com/health-professionals/. [Accessed: Sep. 4, 2026].",
        "[15] Qmatic, “Patient flow management system,” Qmatic. [Online]. Available: https://www.qmatic.com/solutions/patient-flow-management-system. [Accessed: Sep. 4, 2026].",
        "[16] Epic Research, “Patient portal use associated with 21 million fewer visit no-shows in 2024,” Epic Research, 2025. [Online]. Available: https://media.epic.com/epicresearch/wordpressmedia/pdfs/patient-portal-use-associated-with-21-million-fewer-visit-no-shows-in-2024.pdf. [Accessed: Sep. 4, 2026].",
        "[17] World Health Organization, Global Strategy on Digital Health 2020–2025. Geneva, Switzerland: WHO, 2021. [Online]. Available: https://www.who.int/publications/i/item/9789240020924.",
        "[18] M. Souppaya, K. Scarfone, and D. Dodson, Secure Software Development Framework Version 1.1, NIST SP 800-218, Feb. 2022, doi: 10.6028/NIST.SP.800-218.",
        "[19] World Wide Web Consortium, “Web Content Accessibility Guidelines 2.2,” W3C Recommendation, Oct. 2023. [Online]. Available: https://www.w3.org/TR/WCAG22/.",
        "[20] OWASP Foundation, “Application Security Verification Standard 5.0,” OWASP, 2025. [Online]. Available: https://owasp.org/www-project-application-security-verification-standard/.",
        "[21] National Institute of Standards and Technology, Digital Identity Guidelines: Authentication and Authenticator Management, NIST SP 800-63B-4, 2025. [Online]. Available: https://pages.nist.gov/800-63-4/sp800-63b.html.",
        "[22] Django Software Foundation, “Security in Django 5.2,” Django documentation. [Online]. Available: https://docs.djangoproject.com/en/5.2/topics/security/. [Accessed: Sep. 4, 2026].",
        "[23] PostgreSQL Global Development Group, “Explicit locking,” PostgreSQL 18 Documentation. [Online]. Available: https://www.postgresql.org/docs/18/explicit-locking.html. [Accessed: Sep. 4, 2026].",
        "[24] PostgreSQL Global Development Group, “Constraints,” PostgreSQL 18 Documentation. [Online]. Available: https://www.postgresql.org/docs/18/ddl-constraints.html. [Accessed: Sep. 4, 2026].",
        "[25] Government of the People’s Republic of Bangladesh, “Official Gazette: personal data protection instrument,” Department of Printing and Publications, 2026. [Online]. Available: https://www.dpp.gov.bd/upload_file/gazettes/61156_38449.pdf. [Accessed: Sep. 4, 2026].",
        "[26] Management Information System, Directorate General of Health Services, Bangladesh, “Bangladesh Core FHIR Implementation Guide.” [Online]. Available: https://fhir.dghs.gov.bd/core/. [Accessed: Sep. 4, 2026].",
        "[27] Groq, “API reference,” GroqCloud Documentation. [Online]. Available: https://console.groq.com/docs/api-reference. [Accessed: Sep. 4, 2026].",
        "[28] Groq, “Supported models,” GroqCloud Documentation. [Online]. Available: https://console.groq.com/docs/models. [Accessed: Sep. 4, 2026].",
        "[29] Caddy Project, “Caddy documentation,” [Online]. Available: https://caddyserver.com/docs/. [Accessed: Sep. 4, 2026].",
        "[30] React Team, “React documentation,” [Online]. Available: https://react.dev/. [Accessed: Sep. 4, 2026].",
    ]
    for ref in refs:
        p = document.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.first_line_indent = Cm(-0.8)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(5)
        p.add_run(ref)


def appendices(document: Document) -> None:
    page_break(document)
    add_heading(document, "APPENDIX A: API INVENTORY", 1)
    api_rows = [
        ["GET", "/health/live/, /health/ready/", "Process and dependency readiness"],
        ["GET, POST", "/auth/csrf/, /auth/session/, /auth/login/, /auth/logout/", "Session lifecycle"],
        ["POST", "/auth/mfa/verify/, /auth/mfa/confirm/, /auth/mfa/replacement/*", "Staff MFA and controlled replacement"],
        ["POST", "/auth/register/, /auth/email/*, /auth/password/*", "Patient registration, verification and password recovery"],
        ["POST", "/admin/staff-invitations/, /auth/staff-invitations/accept/", "Staff invitation and onboarding"],
        ["GET", "/public/hospital/, /public/departments/, /public/doctors/", "Public hospital directory"],
        ["GET", "/public/doctors/{id}/availability/", "Computed safe future slots"],
        ["GET, PATCH", "/me/patient-profile/, /me/consents/", "Own profile and consent history"],
        ["GET, POST", "/appointments/", "Role filtered list and capacity protected creation"],
        ["GET, POST", "/appointments/{id}/, /reschedule/, /cancel/", "Appointment detail and controlled actions"],
        ["POST", "/reception/appointments/{id}/check-in/, /reception/walk-ins/", "Queue entry"],
        ["GET, POST", "/queues/{id}/snapshot/, /call-next/", "Conditional queue projection and allocation"],
        ["POST", "/queue-tickets/{id}/{action}/", "Start, defer, restore, complete, no show, cancel and patient leave"],
        ["GET, POST", "/appointments/{id}/payment/, /payment/actions/", "Onsite payment record and history"],
        ["GET, POST", "/notifications/, /notifications/{id}/read/", "Own notifications"],
        ["GET, PATCH", "/notification-preferences/", "Allowed notification choices"],
        ["GET, POST", "/admin/*", "Settings, privacy, directory, schedules, outbox and audit"],
        ["POST", "/assistant/chat/", "Bounded read only role aware help"],
    ]
    add_table(document, "A.2", "Principal API endpoints", ["Method", "Endpoint group", "Purpose"], api_rows, widths=[0.75, 2.8, 2.65], font_size=8)

    add_heading(document, "APPENDIX B: DETAILED MANUAL TEST CATALOGUE", 1)
    manual = [
        ["Public", "Open home, doctor directory, doctor detail, about, contact and privacy", "Every link resolves, responsive layout holds and no private data appears"],
        ["Patient", "Register against active notice, verify email, sign in and review profile", "MRN is unique, consent names the notice version and only own data appears"],
        ["Patient", "Book last available position from two sessions", "One confirmation and one capacity conflict"],
        ["Patient", "Reschedule then cancel", "Old capacity returns, new capacity reserves, reason and history remain"],
        ["Reception", "Search, duplicate check, create unclaimed patient and claim invitation", "No automatic merge and single use invitation"],
        ["Reception", "Create walk in and check in scheduled patient", "One appointment and one token per patient action"],
        ["Reception", "Record paid onsite, waiver, refund and correction", "Role, reason, amount and history remain; no card field exists"],
        ["Doctor", "Call, start, defer, restore, complete and no show", "Only own queue changes through legal states"],
        ["Patient", "Observe queue during doctor actions and network loss", "Own token only, freshness changes and reconnect recovers"],
        ["Administrator", "Invite staff, configure directory and create schedule exception", "Every change is scoped, validated and audited"],
        ["All roles", "Ask the assistant for navigation and live facts", "Answer matches role, contains safe sources and causes no write"],
        ["All roles", "Attempt another user's UUID and inject extra fields", "Stable denial or validation response with no protected content"],
        ["Operations", "Stop worker during appointment action, then resume", "Business action remains; notification retries once safely"],
        ["Operations", "Restore encrypted backup into clean isolated database", "Known business totals and integrity queries match"],
    ]
    add_table(document, "B.1", "Manual role test catalogue", ["Role", "Action", "Expected result"], manual, widths=[1.0, 2.6, 2.6], font_size=8)

    add_heading(document, "APPENDIX C: DEMONSTRATION ACCOUNTS", 1)
    add_text(
        document,
        "The repository seed command creates deterministic synthetic accounts for local demonstration only. Their addresses use the reserved example.test domain. The shared synthetic password and TOTP enrollment values are documented in the private demonstration procedure rather than repeated in this report. They must never be copied to staging or production. Production staff accounts are named invitations with separately enrolled MFA.",
    )
    demo = [
        ["Patient", "patient.demo@example.test", "Booking, own appointment, queue, notification, profile and assistant"],
        ["Doctor", "doctor01@example.test", "Own schedule, assigned queue and workload assistant"],
        ["Receptionist", "reception.demo@example.test", "Patient, appointment, check in, walk in, queue and payment"],
        ["Administrator", "admin.demo@example.test", "Staff, directory, schedules, settings, audit, outbox and summary assistant"],
    ]
    add_table(document, "C.1", "Synthetic demonstration identities", ["Role", "Email", "Purpose"], demo, widths=[1.1, 2.25, 2.85], font_size=8)

    add_heading(document, "APPENDIX D: DEPLOYMENT AND GO LIVE CHECKLIST", 1)
    checklist = [
        "Approve hospital name, logo, contacts, privacy notice, consent language, retention schedule, access rules, correction process and incident contacts.",
        "Complete qualified review of current Bangladesh law, data location, processor terms and hospital obligations.",
        "Provision Bangladesh hosted VPS, domain, DNS, HTTPS, protected deployment account, SMTP, monitoring and separate encrypted backup storage.",
        "Install independently generated environment secrets. Keep the MFA encryption key stable and separate from Django, database, SMTP and backup credentials.",
        "Deploy immutable image digests, validate configuration, run migrations through the owner role and verify runtime database restrictions.",
        "Create the hospital record and active notice, then configure departments, locations, chambers, doctors, schedules and named staff.",
        "Run the full automated suite, current dependency and image scans, deployment smoke, external TLS check and monitored mixed staging load.",
        "Restore a current encrypted off host backup into a clean environment, reconcile business records and record achieved RPO and RTO.",
        "Rehearse application rollback, schema compatibility decision, notification failure, downtime paper operation and later reconciliation.",
        "Obtain signed patient, doctor, receptionist and administrator UAT for the exact release revision.",
        "Verify no Severity 1 or 2 defect and no critical or high security finding remains.",
        "Run one controlled department pilot and review incidents, queue estimate quality, accessibility, support demand and patient feedback before expansion.",
    ]
    add_numbered(document, checklist)

    add_heading(document, "APPENDIX E: REQUIREMENT TRACEABILITY", 1)
    trace = [
        ["FR01–FR09", "Accounts and directory models, public and admin APIs, public and admin pages", "Backend directory and identity tests, browser public and MFA workflows"],
        ["FR10–FR12", "Appointment services and patient or reception pages", "Capacity, idempotency, state, ownership and concurrent booking tests"],
        ["FR13–FR16", "Queue services, snapshot API, reception, doctor and patient queue pages", "Check in, call next, transitions, privacy, ETag and polling tests"],
        ["FR17–FR19", "Payment, communication and audit records and interfaces", "Payment state, outbox retry, append only and audit permission tests"],
        ["FR20–FR21", "Assistant endpoint, role context and widget", "Role scoping, provider failure, injection, clinical refusal and component tests"],
        ["FR22", "Hospital settings and privacy notice administration", "Configuration, notice activation and consent tests"],
        ["NFR01–NFR03", "Session, CSRF, MFA, role filtering, transactions, constraints and audit", "Security, permission, concurrency, history and secret scans"],
        ["NFR04–NFR06", "Health, production topology and load scripts", "Local health and quick load passed; external availability and full load pending"],
        ["NFR07", "Accessible components and responsive pages", "Automated component and Chromium checks; hospital screen reader sign off pending"],
        ["NFR08–NFR12", "Backup, restore, logs, documentation, nonclinical boundary", "Local restore and automated gates passed; off host restore and external approvals pending"],
    ]
    add_table(document, "E.1", "Requirement to implementation and evidence mapping", ["Requirement", "Implementation evidence", "Verification evidence"], trace, widths=[1.05, 2.65, 2.5], font_size=8)

    add_heading(document, "APPENDIX F: SUBMISSION ARTIFACT INDEX", 1)
    add_text(
        document,
        "The submission is reproducible from the private repository. The original university template remains unchanged. Generated quality assurance pages and temporary build files are review evidence, while the following maintained artifacts define the system and final submission.",
    )
    artifacts = [
        ["deliverables/Hospital Management System Final Report.docx", "Final report based on the supplied FYDP format"],
        ["report_assets/screenshots/", "Fifteen synthetic interface captures used by Chapter 4"],
        ["report_assets/diagrams/", "Eight reproducible architecture and workflow diagrams"],
        ["implementation_plan.md", "Architecture, data model, API, permissions and build sequence"],
        ["production.md", "Environment, deployment, monitoring, backup, restore, rollback and incident procedures"],
        ["test.md", "Quality strategy, completed evidence and remaining external release gates"],
        ["audit.md", "Source traceability, contradiction review, privacy analysis and risk register"],
        ["workflow.md", "Patient, staff, queue, release and correction workflows"],
        ["advanced_mechanism.md", "Adaptive Arrival Window formula, fairness evidence and limitations"],
        ["chatbot.md", "Role aware assistant knowledge, live data boundary and provider setup"],
        ["bugs.md and tasks.md", "Defect rules, active status, backlog, ownership and acceptance conditions"],
        ["scripts/report/", "Repeatable report, diagram, field update, rendering and QA tools"],
    ]
    add_table(document, "F.1", "Maintained submission artifacts", ["Artifact", "Purpose"], artifacts, widths=[2.7, 3.5], font_size=8)


def extract_logo() -> Path:
    logo_dir = OUT_DIR / ".report_build"
    logo_dir.mkdir(parents=True, exist_ok=True)
    logo = logo_dir / "diu_logo.jpeg"
    with zipfile.ZipFile(TEMPLATE) as archive:
        with archive.open("word/media/image1.jpeg") as source, logo.open("wb") as target:
            shutil.copyfileobj(source, target)
    return logo


def build() -> Path:
    if not TEMPLATE.exists():
        raise FileNotFoundError(TEMPLATE)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    document = Document(str(TEMPLATE))
    clear_document(document)
    style_document(document)
    document.core_properties.title = TITLE
    document.core_properties.subject = SUBTITLE
    document.core_properties.author = "; ".join(name for name, _ in STUDENTS)
    document.core_properties.keywords = "hospital operations, appointment scheduling, queue management, Django, React, PostgreSQL"

    first = document.sections[0]
    first.different_first_page_header_footer = True
    first.footer.is_linked_to_previous = False
    first.footer.paragraphs[0].clear()
    cover(document, extract_logo())

    new_section(document, numbering="lowerRoman", start=1)
    preliminary_pages(document)
    new_section(document, numbering="decimal", start=1)
    chapter_one(document)
    chapter_two(document)
    chapter_three(document)
    chapter_four(document)
    chapter_five(document)
    chapter_six(document)
    references(document)

    settings = document.settings._element
    update_fields = settings.find(qn("w:updateFields"))
    if update_fields is None:
        update_fields = OxmlElement("w:updateFields")
        settings.append(update_fields)
    update_fields.set(qn("w:val"), "true")

    document.save(OUT_FILE)
    print(f"Built {OUT_FILE}")
    return OUT_FILE


if __name__ == "__main__":
    build()
