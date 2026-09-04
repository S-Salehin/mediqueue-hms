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
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "FYDP Tamplate.docx"
OUT_DIR = ROOT / "deliverables"
OUT_FILE = OUT_DIR / "Hospital Management System Final Report.docx"
DIAGRAM_DIR = ROOT / "report_assets" / "diagrams"
SCREENSHOT_DIR = ROOT / "report_assets" / "screenshots"

TITLE = "Hospital Management System: A Web Application"
SUBTITLE = "Production Pilot with Adaptive Queue and Role Aware Assistance"
STUDENTS = [
    ("Md. Sobuj Mia", "0242220005101064"),
    ("Md. Ismail Hossain", "0242220005101051"),
]
SUPERVISOR = "Md. Ferdouse Ahmed Foysal"
CO_SUPERVISOR = "Shah Md. Tanvir Siddiquee"
SUBMISSION_DATE = "September 05, 2026"

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
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.font.color.rgb = RGBColor.from_string(INK)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    normal.paragraph_format.space_after = Pt(6)

    heading_settings = {
        "Heading 1": (16, NAVY, 12, 8),
        "Heading 2": (14, NAVY, 10, 6),
        "Heading 3": (12, TEAL, 8, 4),
        "Heading 4": (12, INK, 7, 3),
    }
    for name, (size, color, before, after) in heading_settings.items():
        style = document.styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    for name in ("Figure Caption", "Table Caption", "Source Note", "Code Block"):
        if name not in document.styles:
            document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    for name in ("Figure Caption", "Table Caption"):
        style = document.styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(10)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(NAVY)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        style.paragraph_format.space_before = Pt(4)
        style.paragraph_format.space_after = Pt(8)
        style.paragraph_format.keep_with_next = True
    source = document.styles["Source Note"]
    source.font.name = "Times New Roman"
    source.font.size = Pt(9)
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
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(3.0)
        section.right_margin = Cm(2.2)
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


def add_numbered(document: Document, items: list[str]) -> None:
    for index, item in enumerate(items, 1):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.left_indent = Cm(0.6)
        paragraph.paragraph_format.first_line_indent = Cm(-0.6)
        paragraph.add_run(f"{index}. ").bold = True
        paragraph.add_run(item)


def add_bullets(document: Document, items: list[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.left_indent = Cm(0.6)
        paragraph.paragraph_format.first_line_indent = Cm(-0.4)
        paragraph.add_run("• ").bold = True
        paragraph.add_run(item)


def add_heading(document: Document, text: str, level: int = 1) -> None:
    paragraph = document.add_heading(text, level=level)
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
        set_cell_shading(cell, NAVY)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_margins(cell)
        if widths:
            cell.width = Inches(widths[index])
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.0
            for run in paragraph.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(font_size)
                run.font.bold = True
                run.font.color.rgb = RGBColor.from_string(WHITE)
    for row_index, values in enumerate(rows):
        row = table.add_row()
        prevent_row_split(row)
        if row_index % 2:
            for cell in row.cells:
                set_cell_shading(cell, "F5F8F9")
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
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(font_size)
    document.add_paragraph()


def add_figure(document: Document, number: str, title: str, path: Path, *, width=6.3,
               source: str | None = None) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(3)
    shape = paragraph.add_run().add_picture(str(path), width=Inches(width))
    shape._inline.docPr.set("descr", title)
    shape._inline.docPr.set("title", f"Figure {number}")
    caption = document.add_paragraph(style="Figure Caption")
    caption.add_run(f"Figure {number}: {title}")
    if source:
        add_text(document, source, style="Source Note")


def page_break(document: Document) -> None:
    document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def new_section(document: Document, *, numbering: str, start: int) -> None:
    section = document.add_section(WD_SECTION.NEW_PAGE)
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.2)
    section.header_distance = Cm(1.2)
    section.footer_distance = Cm(1.2)
    section.footer.is_linked_to_previous = False
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(footer, "PAGE")
    for run in footer.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(10)
    set_page_number(section, numbering, start)


def chapter(document: Document, number: int, title: str, overview: str, *, start_on_new_page: bool = True) -> None:
    if start_on_new_page:
        page_break(document)
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(f"CHAPTER {number}")
    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(15)
    run.font.color.rgb = RGBColor.from_string(NAVY)
    heading = document.add_heading(title.upper(), level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_text(document, overview)


def cover(document: Document, logo: Path) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(5)
    shape = paragraph.add_run().add_picture(str(logo), width=Inches(1.55))
    shape._inline.docPr.set("descr", "Daffodil International University logo")
    shape._inline.docPr.set("title", "University logo")
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(18)
    r = p.add_run(TITLE)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(23)
    r.font.color.rgb = RGBColor.from_string(NAVY)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(SUBTITLE)
    r.italic = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(14)
    r.font.color.rgb = RGBColor.from_string(TEAL)
    add_text(document, "By", align=WD_ALIGN_PARAGRAPH.CENTER)
    for name, student_id in STUDENTS:
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(name)
        r.bold = True
        r.font.size = Pt(13)
        p.add_run(f"\nID: {student_id}")
    add_text(document, "FINAL YEAR DESIGN PROJECT REPORT", align=WD_ALIGN_PARAGRAPH.CENTER)
    add_text(
        document,
        "This report is presented in partial fulfillment of the requirements for the degree of Bachelor of Science in Computer Science and Engineering.",
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("Supervised by\n").bold = True
    p.add_run(f"{SUPERVISOR}\nLecturer\nDepartment of Computer Science and Engineering")
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("Co-Supervised by\n").bold = True
    p.add_run(f"{CO_SUPERVISOR}\nLecturer\nDepartment of Computer Science and Engineering")
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    r = p.add_run("DAFFODIL INTERNATIONAL UNIVERSITY")
    r.bold = True
    r.font.size = Pt(14)
    p.add_run(f"\nDhaka, Bangladesh\n{SUBMISSION_DATE}")
    for cover_paragraph in document.paragraphs:
        cover_paragraph.paragraph_format.line_spacing = 1.0
        cover_paragraph.paragraph_format.space_after = Pt(2)


def preliminary_pages(document: Document) -> None:
    add_heading(document, "APPROVAL", 1)
    add_text(
        document,
        f"This project titled “{TITLE}”, submitted by {STUDENTS[0][0]} and {STUDENTS[1][0]} to the Department of Computer Science and Engineering, Daffodil International University, has been prepared in partial fulfillment of the requirements for the degree of Bachelor of Science in Computer Science and Engineering. The work, report, demonstration, and supporting evidence are presented for academic evaluation and approval as to their style and contents.",
    )
    add_text(document, "Supervisor signature: ____________________________________", align=WD_ALIGN_PARAGRAPH.LEFT)
    add_text(document, f"{SUPERVISOR}\nLecturer, Department of Computer Science and Engineering\nDaffodil International University")
    add_text(document, "Co-supervisor signature: _________________________________", align=WD_ALIGN_PARAGRAPH.LEFT)
    add_text(document, f"{CO_SUPERVISOR}\nLecturer, Department of Computer Science and Engineering\nDaffodil International University")
    add_text(document, "Date: ____________________")
    page_break(document)

    add_heading(document, "BOARD OF EXAMINERS", 1)
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
    add_heading(document, "DECLARATION", 1)
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

    add_heading(document, "ACKNOWLEDGEMENTS", 1)
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

    add_heading(document, "ABSTRACT", 1)
    add_text(
        document,
        "Hospitals lose time and create avoidable uncertainty when appointment booking, reception check in, queue progress, onsite payment recording, and communication are kept in separate manual processes. This project develops a web based hospital operations pilot for one small hospital with up to 30 doctors, 500 appointments in a day, and 50 concurrent users. The system provides separate workspaces for patients, doctors, receptionists, and administrators. It covers doctor directories, schedules and closures, patient registration with generated medical record numbers, appointment booking and rescheduling, walk ins, check in, live privacy safe queue tokens, onsite BDT payment status, notifications, consent, and immutable audit evidence. The implementation uses React 19, Django 5.2 LTS, Django REST Framework, PostgreSQL 18, Caddy, and Docker. Transactional domain services combine row locks, uniqueness constraints, idempotency records, state validation, and business histories to protect competing operations. The main design contribution is an Adaptive Arrival Window that combines the configured visit duration with recent valid service durations and reports a bounded wait range without performing clinical triage or changing first in first out order. A read only role aware assistant explains workflows and uses only allowlisted live facts. It retains a deterministic local answer path when the optional external language provider is unavailable. The completed local candidate passed 129 Django tests with 87 percent line coverage, 57 frontend tests with 88.88 percent line coverage, six Chromium workflow scenarios, security and dependency checks, a 50 user quick read test, and an encrypted backup restoration exercise. Real patient use remains intentionally blocked until the hospital approves its identity, privacy and retention rules, legal review, staff access, external infrastructure, restoration evidence, and signed user acceptance. The result is therefore a tested production candidate and academic implementation, not a claim of unrestricted clinical deployment.",
    )
    page_break(document)

    add_heading(document, "TABLE OF CONTENTS", 1)
    p = document.add_paragraph()
    add_field(p, 'TOC \\o "1-4" \\h \\z \\u', "Right click and update the table of contents")
    page_break(document)
    add_heading(document, "LIST OF FIGURES", 1)
    p = document.add_paragraph()
    add_field(p, 'TOC \\h \\z \\t "Figure Caption,1"', "Right click and update the list of figures")
    page_break(document)
    add_heading(document, "LIST OF TABLES", 1)
    p = document.add_paragraph()
    add_field(p, 'TOC \\h \\z \\t "Table Caption,1"', "Right click and update the list of tables")
    page_break(document)
    add_heading(document, "LIST OF ABBREVIATIONS", 1)
    add_table(
        document,
        "A.1",
        "Abbreviations used in the report",
        ["Abbreviation", "Meaning"],
        [
            ["API", "Application Programming Interface"],
            ["ASVS", "Application Security Verification Standard"],
            ["CSRF", "Cross Site Request Forgery"],
            ["ETag", "HTTP entity tag used for conditional queue reads"],
            ["FHIR", "Fast Healthcare Interoperability Resources"],
            ["FYDP", "Final Year Design Project"],
            ["MFA", "Multi Factor Authentication"],
            ["MRN", "Medical Record Number"],
            ["RPO", "Recovery Point Objective"],
            ["RTO", "Recovery Time Objective"],
            ["SQA", "Software Quality Assurance"],
            ["TOTP", "Time Based One Time Password"],
            ["UAT", "User Acceptance Testing"],
            ["WCAG", "Web Content Accessibility Guidelines"],
        ],
        widths=[1.35, 4.85],
    )


def chapter_one(document: Document) -> None:
    chapter(
        document,
        1,
        "Introduction",
        "This chapter explains the hospital operations problem, the reason for building the system, the precise objectives, the implementation boundary, and the method used to turn the original academic idea into a verifiable production candidate.",
        start_on_new_page=False,
    )
    add_heading(document, "1.1 Background and Problem Statement", 2)
    add_text(
        document,
        "An outpatient visit begins before a patient enters a consultation room. The patient has to find an appropriate doctor, understand where and when that doctor works, obtain a valid appointment, arrive at the correct location, report to reception, wait for a fair turn, and receive confirmation when the visit ends. Reception staff must identify the patient correctly, avoid duplicate records, protect the final available capacity, accommodate walk ins, and explain delays. Doctors need a current view of their own queue without gaining unrelated access. Administrators have to configure services and retain enough evidence to understand who changed what. A weak system may display a polished dashboard while still allowing double booking, exposure of another patient, or an unexplained queue override.",
    )
    add_text(
        document,
        "The supplied university proposal described a basic appointment application. It did not provide transferred source code, a trustworthy data model, role boundaries, concurrency rules, an audit design, backup evidence, or a defensible production scope. Several sample interface images exposed patient names in queue contexts, and the supplied bibliography could not be verified as written. Treating those materials as complete requirements would have created risk. The project was therefore reanalysed from the beginning, while retaining the approved educational objective of a web based hospital management system.",
    )
    add_text(
        document,
        "The defined problem is to coordinate nonclinical outpatient operations for one small hospital in a way that is understandable to patients and staff, resistant to repeated or competing requests, privacy aware, accessible, auditable, and feasible to operate on modest infrastructure. The system deliberately does not store diagnoses, prescriptions, clinical notes, test results, card details, or automated triage decisions. That boundary keeps the project focused and prevents an appointment pilot from being misrepresented as a complete electronic medical record.",
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

    add_heading(document, "1.3 Objectives", 2)
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

    add_heading(document, "1.4 Scope and Boundary", 2)
    add_table(
        document,
        "1.1",
        "Release scope and exclusions",
        ["Included in the pilot", "Excluded from the pilot"],
        [
            ["Patient and staff identity, email verification, invitation and staff MFA", "Electronic medical record notes, diagnoses, prescriptions and clinical decision support"],
            ["Departments, locations, chambers, doctors, schedules, closures and capacity", "Laboratory, radiology, pharmacy, inpatient care, beds and nursing records"],
            ["Appointment booking, rescheduling, cancellation, check in and walk ins", "Insurance claims, payroll, inventory, accounting and financial settlement"],
            ["Live queue, operational estimate, defer, restore, no show and completion", "Online card processing, mobile wallet credential storage and card data"],
            ["In application and minimal email notifications", "SMS, native mobile applications and video consultation"],
            ["Onsite payment status in BDT, audit, backup and recovery controls", "Automated medical triage, diagnosis, clinical priority and multi hospital tenancy"],
        ],
        widths=[3.1, 3.1],
    )
    add_text(
        document,
        "The codename MediQueue is used only for development and demonstration. It is configurable because production identity belongs to the hospital. The capacity assumption is one hospital, no more than 30 doctors, approximately 500 appointments on a busy day, and 50 concurrent users. Synthetic records are mandatory until the launch conditions in Chapter 5 are approved.",
    )

    add_heading(document, "1.5 Development Method", 2)
    add_text(
        document,
        "The project used short, evidence driven increments because the delivery window was unusually small. Each increment crossed the whole stack: requirement, permission rule, database constraint, API contract, interface state, automated test, and role walkthrough. Work was not counted as complete when only a page existed. A booking increment, for example, had to preserve capacity under contention, return the stable error envelope, show an understandable result, write history, and remain inaccessible to an unauthorised user.",
    )
    add_figure(document, "1.1", "Incremental delivery and verification method", DIAGRAM_DIR / "01_incremental_methodology.png")
    add_text(
        document,
        "The method kept documentation beside the code. Requirements, implementation decisions, workflow states, release gates, defects, tests, production procedures, the adaptive mechanism, and the assistant boundary each have a maintained Markdown record. A change to a public state, permission, API, or operational procedure requires the matching documentation and regression test in the same revision.",
    )

    add_heading(document, "1.6 Project Outcome", 2)
    add_text(
        document,
        "The outcome is a working local production candidate with a same origin React interface, Django API, PostgreSQL database, notification worker, Caddy gateway, reproducible container definitions, synthetic demonstration records, and repository based quality checks. Four role workspaces and the public doctor directory are usable. The queue estimate and assistant are implemented with conservative safety boundaries. The repository includes deployment, backup, restoration, monitoring, rollback, testing, and incident procedures.",
    )
    add_text(
        document,
        "The outcome is not represented as a live clinical system. External staging procurement, final hospital branding, current legal review, approved privacy and retention text, named staff enrollment, signed hospital UAT, production SMTP, off host recovery proof, and a controlled department pilot remain mandatory. This distinction is important because passing local software tests does not grant organisational authority to collect real patient data.",
    )

    add_heading(document, "1.7 Organization of the Report", 2)
    add_text(
        document,
        "Chapter 2 reviews scheduling, attendance, self service access, queue systems, related products, and the gap addressed by this project. Chapter 3 presents stakeholders, requirements, architecture, data design, workflows, API contracts, security, user experience, the adaptive mechanism, and the assistant design. Chapter 4 explains the implementation, interfaces, test evidence, performance evidence, and results. Chapter 5 maps standards, professional responsibilities, project management, complex engineering problems, knowledge profiles, and activities. Chapter 6 concludes the work, states its limitations honestly, and identifies future development. Appendices provide the API inventory, test catalogue, deployment checklist, demonstration guide, and requirement traceability.",
    )


def chapter_two(document: Document) -> None:
    chapter(
        document,
        2,
        "Background",
        "This chapter establishes the scheduling and patient flow background, reviews verifiable literature and comparable systems, and explains the gap between a general appointment portal and the proposed operational pilot.",
    )
    add_heading(document, "2.1 Domain Background", 2)
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

    add_heading(document, "2.2 Literature Review", 2)
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

    add_heading(document, "2.3 Similar Applications", 2)
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

    add_heading(document, "2.4 Gap Analysis", 2)
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

    add_heading(document, "2.5 Novelty Boundary", 2)
    add_text(
        document,
        "The project does not claim that queues, median service estimates, reminders, language models, or role based access were invented here. Its novel contribution is the implementation combination: a first in first out hospital queue, a transparent adaptive arrival range, freshness and confidence indicators, recorded fairness overrides, a role aware read only assistant, and transactional audit evidence in one small hospital production candidate. The contribution is described as original project engineering, not as a worldwide first. A real pilot must collect error, interval coverage, override, and user acceptance evidence before any stronger effectiveness claim is made.",
    )

    add_heading(document, "2.6 Summary", 2)
    add_text(
        document,
        "The background review shows that scheduling and attendance are context dependent operational problems. Comparable products validate demand for digital booking and queue communication but do not remove the need for a careful local design. The identified gap leads directly to the requirements and architecture in Chapter 3.",
    )


def chapter_three(document: Document) -> None:
    chapter(
        document,
        3,
        "Requirement Analysis and Design Specification",
        "This chapter converts the problem into verifiable functional and quality requirements. It then presents the role model, architecture, records, interfaces, workflows, security controls, adaptive estimate, assistant, alternatives, and project plan.",
    )
    add_heading(document, "3.1 Stakeholders and Operating Assumptions", 2)
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

    add_heading(document, "3.2 Role and System Context", 2)
    add_figure(document, "3.1", "Role and access context", DIAGRAM_DIR / "03_role_access_context.png")
    add_text(
        document,
        "Patients can see only their own claimed profile, appointments, queue ticket, payment summary, notifications, and consent. Doctors can see only their linked schedule and the minimum patient identity associated with their appointments and queue. Receptionists receive operational access needed for registration and flow, but cannot create privileged staff. Administrators configure the service and review audit records. Staff actions require completed TOTP MFA. Querysets are filtered before object lookup so changing a UUID cannot turn a forbidden object into a disclosed object.",
    )

    add_heading(document, "3.3 Functional Requirements", 2)
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

    add_heading(document, "3.4 Nonfunctional Requirements", 2)
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

    add_heading(document, "3.5 Architecture", 2)
    add_figure(document, "3.2", "System architecture", DIAGRAM_DIR / "02_system_architecture.png")
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

    add_heading(document, "3.6 Data Model and Integrity", 2)
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

    add_heading(document, "3.7 Appointment and Queue State Design", 2)
    add_figure(document, "3.4", "Appointment and queue workflow", DIAGRAM_DIR / "04_appointment_queue_workflow.png")
    add_text(
        document,
        "Appointment states are confirmed, cancelled, completed, and no_show. Queue states are waiting, called, in_service, deferred, completed, no_show, and cancelled. Cancelled, completed, and no show appointments are terminal. Queue defer and restore are explicit because temporarily passing a patient should not be disguised as cancellation. Every override requires a reason and records the previous state, new state, actor, time, and request identifier.",
    )
    add_text(
        document,
        "A write request carries an Idempotency-Key. The server associates its digest with the authenticated actor, route scope, and request digest. An exact retry receives the stored outcome. Reusing the key with a different body is rejected. For competing actions, PostgreSQL row locks serialize the schedule, appointment, queue session, or ticket that owns the invariant. Database constraints remain the final protection if application checks race. PostgreSQL documentation distinguishes row level locking and constraint enforcement, which are both used here [23], [24].",
    )

    add_heading(document, "3.8 API Contract", 2)
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

    add_heading(document, "3.9 Adaptive Arrival Window", 2)
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

    add_heading(document, "3.10 Role Aware Assistant", 2)
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

    add_heading(document, "3.11 Security and Privacy Design", 2)
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

    add_heading(document, "3.12 User Interface and Accessibility Design", 2)
    add_text(
        document,
        "The interface uses a quiet hospital palette, clear page titles, familiar form labels, status text in addition to colour, visible keyboard focus, responsive navigation, and action placement close to the relevant record. Patient pages emphasise the next decision. Reception pages place search, appointment action, and queue action in operational order. Doctor pages minimise navigation around the current queue. Administrator pages separate configuration resources instead of presenting one crowded dashboard.",
    )
    add_text(
        document,
        "Loading, empty, success, validation error, server failure, offline queue, reconnecting, stale data, destructive confirmation, and permission denial are designed states. Queue changes use screen reader announcements without repeating another patient identity. The target is WCAG 2.2 AA [19]. Automated checks support, but do not replace, keyboard and screen reader review with hospital users.",
    )

    add_heading(document, "3.13 Alternatives Considered", 2)
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

    add_heading(document, "3.14 Project Plan and Task Allocation", 2)
    plan = [
        ["Planning and audit", "Requirements, scope, risks, documents and repository controls", "Requirement traceability and approved implementation boundary"],
        ["Foundation", "React, Django, PostgreSQL, containers, identity, roles and shared UI", "Healthy same origin application with protected sessions"],
        ["Directory and scheduling", "Hospital configuration, doctors, locations, schedules and capacity", "Public discovery and administrable availability"],
        ["Appointment operations", "Patient identity, booking, rescheduling, cancellation, walk ins and check in", "Transactional appointment workflow"],
        ["Queue and communication", "Queue states, estimator, payment, notifications, audit and assistant", "Complete outpatient operational path"],
        ["Verification", "Unit, API, browser, concurrency, load, security, dependency and recovery checks", "Recorded evidence and defect correction"],
        ["Delivery", "Screenshots, report, staging instructions, release and launch gate review", "Submission package and production candidate"],
    ]
    add_table(document, "3.8", "Project activity plan", ["Work package", "Main work", "Output"], plan, widths=[1.45, 2.65, 2.1], font_size=8)
    add_text(
        document,
        f"{STUDENTS[0][0]} concentrated on requirement consolidation, backend domain design, database integrity, deployment evidence, and report traceability. {STUDENTS[1][0]} concentrated on interface implementation, role journeys, synthetic data, browser verification, and evidence capture. Both members reviewed security boundaries, executed manual role walkthroughs, corrected integration defects, and prepared the final presentation. Git history and automated checks remain the technical evidence; this allocation describes responsibility rather than claiming that either member worked in isolation.",
    )

    add_heading(document, "3.15 Summary", 2)
    add_text(
        document,
        "The design treats authorization, state, concurrency, privacy, and recovery as core functions. The selected architecture remains small enough for the stated pilot but includes the controls needed to test it seriously. Chapter 4 shows how these decisions were implemented and verified.",
    )


def add_interface_evidence(document: Document) -> None:
    figures = [
        ("4.2", "Public home page with hospital service entry points", "01-public-home.png", "The public landing page introduces the service and keeps doctor discovery and account actions clear."),
        ("4.3", "Public doctor directory", "02-doctor-directory.png", "The directory exposes approved professional data and links to safe availability without patient information."),
        ("4.4", "Patient dashboard", "03-patient-dashboard.png", "The patient workspace prioritises the next appointment, notifications and personal actions."),
        ("4.5", "Appointment booking workflow", "04-appointment-booking.png", "Booking moves through doctor, date, slot and review data while the API retains final capacity authority."),
        ("4.6", "Patient assistant showing live availability", "05-patient-assistant-live-availability.png", "The assistant reports safe schedule capacity and explains how to continue without creating an appointment itself."),
        ("4.7", "Reception dashboard", "06-reception-dashboard.png", "Reception receives operational counts and direct access to patient, appointment and queue tasks."),
        ("4.8", "Reception view after appointment check in", "07-reception-checked-in-appointment.png", "Successful check in produces a privacy safe token and one traceable queue ticket."),
        ("4.9", "Doctor dashboard", "08-doctor-dashboard.png", "Doctors see their own service workload, schedule and queue entry points."),
        ("4.10", "Doctor assistant workload answer", "09-doctor-assistant-workload.png", "The live workload answer is derived from the signed in doctor's linked schedule and appointment counts."),
        ("4.11", "Doctor queue after calling the next patient", "10-doctor-queue-called-patient.png", "The queue console applies a controlled state transition and displays only necessary patient identity to assigned staff."),
        ("4.12", "Patient live queue", "11-patient-live-queue-called.png", "The patient sees token progress, an arrival range, confidence and freshness without another patient name."),
        ("4.13", "Administrator dashboard", "12-administrator-dashboard.png", "The administrative workspace provides configuration and operational oversight without bypassing normal record rules."),
        ("4.14", "Administrator schedule management", "13-administrator-schedules.png", "Schedule administration links doctors, chambers, effective dates, duration and slot capacity."),
        ("4.15", "Administrator audit search", "14-administrator-audit-trail.png", "Audit search exposes safe event evidence to the administrator and does not provide update or delete actions."),
        ("4.16", "Administrator assistant summary", "15-administrator-assistant-summary.png", "The administrator receives approved aggregate counts and system guidance without patient names."),
    ]
    for number, title, filename, explanation in figures:
        add_figure(document, number, title, SCREENSHOT_DIR / filename, width=6.2, source="Source: Synthetic demonstration data captured from the implemented local release candidate.")
        add_text(document, explanation)


def chapter_four(document: Document) -> None:
    chapter(
        document,
        4,
        "Implementation and Results",
        "This chapter describes the implemented environment and modules, shows the working interfaces, and reports the verified software quality evidence with clear limits on what local testing can prove.",
    )
    add_heading(document, "4.1 Development and Runtime Environment", 2)
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

    add_heading(document, "4.2 Backend Implementation", 2)
    add_text(
        document,
        "The backend is organised into accounts, directory, operations, communications, help_assistant, and shared core modules. Accounts implements custom users, role assignment, invitations, patient and staff onboarding, MFA, account tokens, login audit, and session controls. Directory implements hospital configuration, departments, locations, chambers, doctor profiles, patient profiles, privacy notice versions, consent, duplicate warnings, and correction history. Operations contains schedules, appointments, queue sessions and tickets, estimates, payments, histories, dashboards, and service functions. Communications contains in application notifications and the email outbox. Core contains stable exceptions, permissions, middleware, throttling, audit, idempotency, logging, and health checks.",
    )
    add_text(
        document,
        "Views remain thin around serializer validation, role filtered lookup, and service invocation. Competing writes run in atomic blocks and acquire rows in a consistent order. For example, rescheduling locks the appointment and both schedule allocations before changing capacity. Call next locks the queue session before selecting an eligible waiting ticket. Append only database triggers protect histories and audit style records from ordinary update or delete operations even if future application code makes a mistake.",
    )

    add_heading(document, "4.3 Frontend Implementation", 2)
    add_text(
        document,
        "The frontend uses route guards for usability, but relies on the API for authority. AuthContext retrieves the current server session, BrandContext retrieves safe hospital presentation values, and the API client obtains a CSRF token before state changing requests. Shared components implement panels, forms, status pills, dialogs, loading placeholders, feedback, pagination, and accessible focus behaviour. Each role has a separate layout and navigation set. Polling logic stops unnecessary foreground frequency when the page is in the background and marks stale data after failed refreshes.",
    )
    add_text(
        document,
        "The assistant is a global authenticated widget. It opens from every role workspace, uses role specific suggestions, labels whether an answer used live information, provides safe internal links returned by the server, and never renders arbitrary HTML. Conversation history is kept short in component state rather than written to browser storage.",
    )

    add_heading(document, "4.4 Deployment Implementation", 2)
    add_figure(document, "4.1", "Pilot deployment and recovery topology", DIAGRAM_DIR / "07_deployment_topology.png")
    add_text(
        document,
        "The planned pilot host has 4 vCPU, 8 GiB RAM, 160 GiB NVMe storage, Ubuntu 24.04 LTS, a Bangladesh location, key based SSH, and a firewall exposing only approved management access and HTTPS. PostgreSQL has no public port. Caddy applies HTTPS and response headers. Production secrets live outside Git in a protected environment file. Images are released by immutable digest through an approved environment.",
    )
    add_text(
        document,
        "Backup design uses pgBackRest with encrypted daily full backups and hourly recovery points on separately approved storage, retained for 30 days. Timers, backup age checks, clean restore instructions, and database reconciliation are included. A rollback distinguishes application rollback from incompatible schema reversal. When a safe reverse migration is unavailable, the documented decision is forward correction or restoration to a verified recovery point.",
    )

    add_heading(document, "4.5 Implemented Interface Evidence", 2)
    add_text(
        document,
        "The following figures were captured from the running application with synthetic Bengali names. They demonstrate the implemented navigation and representative actions. No production identity, patient record, MFA secret, password, API key, or real email address appears in the evidence.",
    )
    add_interface_evidence(document)

    add_heading(document, "4.6 Software Quality Assurance", 2)
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

    add_heading(document, "4.7 Critical Test Scenarios", 2)
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

    add_heading(document, "4.8 Performance and Capacity Interpretation", 2)
    add_text(
        document,
        "The recorded quick local load test ramped to 50 virtual users, held for 60 seconds, and sent 3,638 checked requests through the assembled reverse proxy to public read paths. Its 4.23 millisecond p95 was well below the 500 millisecond quick gate. This proves that the tested local read path remained responsive under that narrow run. It does not prove production network latency, authenticated write capacity, long duration database behaviour, queue freshness under mixed work, or SMTP recovery.",
    )
    add_text(
        document,
        "The release workload remains a five minute ramp to 50 concurrent users, 30 minutes at that level, and five minute ramp down on production sized staging. It mixes directory and availability reads, dashboards, conditional queue snapshots, booking, reception search and check in, doctor transitions, administration reads, and notification recovery. Read p95 must remain below 500 milliseconds, write p95 below 800 milliseconds, unexpected errors below one percent, and queue freshness within 15 seconds. Business reconciliation must then prove that no capacity, token, state, payment, or outbox invariant was lost.",
    )

    add_heading(document, "4.9 Results and Discussion", 2)
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

    add_heading(document, "4.10 Summary", 2)
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
    add_heading(document, "5.1 Applicable Standards and Guidance", 2)
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

    add_heading(document, "5.2 Hardware and Software Constraints", 2)
    add_text(
        document,
        "The pilot assumes ordinary patient and staff browsers rather than dedicated devices. A receptionist benefits from a desktop display and reliable local network, while patient pages must work on narrow mobile screens. The planned VPS is intentionally modest at 4 vCPU and 8 GiB RAM. That constraint influenced the use of conditional polling and a database outbox instead of permanent socket infrastructure and a separate message broker. PostgreSQL memory, worker concurrency, connection counts, container limits, disk growth, backup age, and certificate expiry require monitoring.",
    )

    add_heading(document, "5.3 Communication and Interoperability", 2)
    add_text(
        document,
        "Browser communication uses HTTPS and JSON over a versioned REST interface. The same origin arrangement makes cookie and CSRF boundaries easier to reason about. Email leaves the system only through an approved SMTP service and contains minimal operational text plus a secure link. No SMS or online payment gateway is connected. The database is not public. Future interoperability may map hospital, patient, practitioner, schedule and appointment identifiers to Bangladesh Core FHIR, but the current resources have not passed FHIR profile validation and must not be advertised as conformant.",
    )

    add_heading(document, "5.4 Social, Health, Safety and Cultural Impact", 2)
    add_text(
        document,
        "A clearer appointment and queue experience can reduce unnecessary waiting and repeated enquiries. Privacy safe tokens reduce disclosure in a crowded waiting area. Bengali synthetic names and Bangladesh time and currency make the demonstration relevant to the intended environment. However, digital access can exclude people without email, confidence, literacy, vision, motor ability, or reliable connectivity. Reception assisted registration, account claiming, plain language, responsive layout, keyboard support, and a downtime paper reconciliation procedure are therefore part of the design rather than optional decoration.",
    )
    add_text(
        document,
        "Safety is protected by the nonclinical boundary. A queue estimate may help a patient plan arrival, but it must never tell a person whether symptoms are urgent. The assistant refuses medical advice and directs emergencies to the hospital's approved emergency channel. Staff retain responsibility for operational overrides, and each override leaves a reason. The system should never be used to deny care merely because a patient is not digitally connected.",
    )

    add_heading(document, "5.5 Ethical and Privacy Responsibilities", 2)
    add_text(
        document,
        "Purpose limitation is the main ethical rule. Data collected to book and operate a visit should not silently become advertising, model training, or unrelated profiling data. The system stores no diagnosis, symptom, prescription, or card data. Consent points to the exact published privacy notice version. Staff access is role limited and reviewable. Demonstrations use synthetic identities. Logs and emails use minimal content. The optional assistant receives only allowlisted facts and cannot write to business records.",
    )
    add_text(
        document,
        "Transparency also applies to estimation. The patient receives a range and confidence rather than a false promise. Staff can see why an estimate was produced and must explain overrides. The hospital must approve the language used for consent, retention, incident communication, and patient correction. Legal review cannot be replaced by a software statement saying that the service is compliant.",
    )

    add_heading(document, "5.6 Sustainability", 2)
    add_text(
        document,
        "The design favours a small operational footprint, supported software, container reuse, conditional responses, bounded polling and one database. Fewer services reduce idle compute, backup complexity and operator training. Sustainable operation also includes routine patching, image rebuilds, storage monitoring, deletion according to an approved retention schedule, and deactivation instead of unnecessary duplication. Accessibility and assisted workflows support social sustainability by keeping the service usable for more patients.",
    )

    add_heading(document, "5.7 Project Management and Financial Analysis", 2)
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

    add_heading(document, "5.8 Complex Engineering Problem Mapping", 2)
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

    add_heading(document, "5.9 Knowledge Profile Mapping", 2)
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

    add_heading(document, "5.10 Complex Engineering Activities", 2)
    ea_rows = [
        ["EA1", "Range of resources", "Source documents, application code, database, containers, cloud repository, standards, research, test tools and operational procedures."],
        ["EA2", "Level of interaction", "Continuous coordination across four user roles, academic supervision, development, operations and approval owners."],
        ["EA3", "Innovation", "Transparent adaptive arrival range and role aware live assistant integrated with transactional queue evidence."],
        ["EA4", "Consequences", "A defect can expose patient identity, waste capacity, alter service order or prevent recovery, so release gates reflect consequence."],
        ["EA5", "Familiarity", "Common web technologies are applied to less routine hospital workflow, privacy and concurrent state problems."],
    ]
    add_table(document, "5.5", "Mapping with complex engineering activities", ["Code", "Activity", "Project rationale"], ea_rows, widths=[0.6, 1.45, 4.15], font_size=8)

    add_heading(document, "5.11 Principal Design Challenges", 2)
    challenges = [
        ["Challenge", "Resolution", "Remaining control"],
        ["No transferred application code", "Built a traceable architecture and tests from the audited requirements", "Hospital validates the workflow on staging"],
        ["Three day completion pressure", "Kept a bounded nonclinical scope and prioritised invariants", "Deferred features remain explicit"],
        ["Slot and queue contention", "Used idempotency, locks, constraints and legal state services", "Full mixed staging load and reconciliation"],
        ["Useful live queue without disclosure", "Used public tokens, own ticket projection, range and freshness", "Waiting area observation during controlled pilot"],
        ["Helpful AI without broad authority", "Allowlisted context, read only endpoint, clinical refusal and local fallback", "Processor approval and response review before provider use"],
        ["Production claim without infrastructure", "Separated completed candidate from external launch gates", "Named owner must approve every real data gate"],
    ]
    add_table(document, "5.6", "Design challenges and resolution", challenges[0], challenges[1:], widths=[1.55, 2.65, 2.0], font_size=8)

    add_heading(document, "5.12 Summary", 2)
    add_text(
        document,
        "The project required choices across standards, software, operations, ethics, accessibility, cost and recovery. Its complexity comes from interdependent consequences rather than from an excessive number of technologies. The mappings show how theoretical knowledge and engineering practice meet in the implemented candidate.",
    )


def chapter_six(document: Document) -> None:
    chapter(
        document,
        6,
        "Conclusion",
        "This chapter summarises the completed work, states its limitations, and identifies a controlled path for future development after the production candidate receives hospital approval.",
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

    add_heading(document, "6.2 Limitations", 2)
    add_numbered(
        document,
        [
            "The system is a single hospital outpatient operations pilot and not an electronic medical record, hospital information suite, or clinical decision system.",
            "The adaptive estimate has deterministic unit evidence but no representative real hospital dataset. Accuracy and patient benefit remain unmeasured until a controlled pilot.",
            "Automated browser evidence uses pinned Chromium. The documented Firefox, WebKit, Edge, Android Chrome, mobile Safari, keyboard and screen reader sign off remains external UAT work.",
            "The quick 50 user read test is not the full 30 minute authenticated mixed workload. Production capacity remains a staging gate.",
            "No production domain, TLS endpoint, SMTP account, Bangladesh VPS, off host backup repository, monitoring destination, or incident rota was supplied for final activation.",
            "The hospital's final identity, privacy notice, consent language, retention schedule, correction policy, downtime policy and legal mapping are not authorised by the software team.",
            "The external language provider is optional. Any exposed development key must be revoked, and a replacement may be installed only in protected environment configuration after processor approval.",
            "Formal FHIR conformance, SMS, online payments, insurance, laboratory, pharmacy, inpatient, inventory, payroll and multi hospital operation are outside the release.",
        ],
    )

    add_heading(document, "6.3 Future Work", 2)
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

    add_heading(document, "6.4 Final Statement", 2)
    add_text(
        document,
        "A hospital system should be judged by the records it protects and the failures it handles, not only by the screens it displays. This project establishes a practical foundation for appointment and queue operations with visible limits, repeatable evidence, and a clear route from academic demonstration to a controlled hospital pilot.",
    )


def references(document: Document) -> None:
    page_break(document)
    add_heading(document, "REFERENCES", 1)
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
    appendices(document)

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
