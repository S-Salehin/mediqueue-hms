"""Render every report page and create visual QA contact sheets."""

from __future__ import annotations

import json
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "report_qa" / "Hospital Management System Final Report.pdf"
PAGE_DIR = ROOT / "report_qa" / "pages"
SHEET_DIR = ROOT / "report_qa" / "contact_sheets"


def label_font(size=24):
    path = Path("C:/Windows/Fonts/arialbd.ttf")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def main() -> None:
    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    SHEET_DIR.mkdir(parents=True, exist_ok=True)
    document = fitz.open(PDF)
    findings = []
    rendered = []
    for index, page in enumerate(document):
        matrix = fitz.Matrix(1.6, 1.6)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        path = PAGE_DIR / f"page-{index + 1:03d}.png"
        pixmap.save(path)
        rendered.append(path)
        text = " ".join(page.get_text().split())
        if len(text) < 40:
            findings.append({"page": index + 1, "kind": "sparse_page", "characters": len(text)})
        for block in page.get_text("blocks"):
            x0, y0, x1, y1 = block[:4]
            if x0 < -0.5 or y0 < -0.5 or x1 > page.rect.width + 0.5 or y1 > page.rect.height + 0.5:
                findings.append({"page": index + 1, "kind": "text_outside_page", "box": [x0, y0, x1, y1]})

    thumb_width = 420
    thumb_height = 594
    columns = 4
    rows = 4
    margin = 24
    label_height = 42
    per_sheet = columns * rows
    sheet_font = label_font(22)
    for sheet_index, start in enumerate(range(0, len(rendered), per_sheet), 1):
        entries = rendered[start:start + per_sheet]
        width = margin + columns * (thumb_width + margin)
        height = margin + rows * (thumb_height + label_height + margin)
        sheet = Image.new("RGB", (width, height), "#273641")
        draw = ImageDraw.Draw(sheet)
        for local_index, page_path in enumerate(entries):
            row, column = divmod(local_index, columns)
            x = margin + column * (thumb_width + margin)
            y = margin + row * (thumb_height + label_height + margin)
            with Image.open(page_path) as page_image:
                thumbnail = page_image.copy()
                thumbnail.thumbnail((thumb_width, thumb_height), Image.Resampling.LANCZOS)
                page_x = x + (thumb_width - thumbnail.width) // 2
                sheet.paste(thumbnail, (page_x, y))
            page_number = start + local_index + 1
            label = f"Page {page_number}"
            bounds = draw.textbbox((0, 0), label, font=sheet_font)
            draw.text((x + (thumb_width - (bounds[2] - bounds[0])) // 2, y + thumb_height + 8), label, fill="white", font=sheet_font)
        sheet.save(SHEET_DIR / f"sheet-{sheet_index:02d}.jpg", quality=88, optimize=True)

    report = {
        "pdf": str(PDF),
        "pages": document.page_count,
        "render_scale": 1.6,
        "findings": findings,
        "contact_sheets": len(list(SHEET_DIR.glob("sheet-*.jpg"))),
    }
    (ROOT / "report_qa" / "render-summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
