"""Create compact report figures from the synthetic interface captures."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "report_assets" / "screenshots"
OUTPUT = ROOT / "report_assets" / "diagrams"

GROUPS = [
    (
        "09_public_patient_interfaces.png",
        [
            ("01-public-home.png", "Public home"),
            ("02-doctor-directory.png", "Doctor directory"),
            ("03-patient-dashboard.png", "Patient dashboard"),
            ("04-appointment-booking.png", "Appointment booking"),
        ],
    ),
    (
        "10_patient_assistant_queue.png",
        [
            ("05-patient-assistant-live-availability.png", "Live availability answer"),
            ("11-patient-live-queue-called.png", "Private live queue"),
        ],
    ),
    (
        "11_reception_interfaces.png",
        [
            ("06-reception-dashboard.png", "Reception dashboard"),
            ("07-reception-checked-in-appointment.png", "Completed check in"),
        ],
    ),
    (
        "12_doctor_interfaces.png",
        [
            ("08-doctor-dashboard.png", "Doctor dashboard"),
            ("09-doctor-assistant-workload.png", "Workload answer"),
            ("10-doctor-queue-called-patient.png", "Doctor queue"),
        ],
    ),
    (
        "13_administrator_interfaces.png",
        [
            ("12-administrator-dashboard.png", "Administrator dashboard"),
            ("13-administrator-schedules.png", "Schedule management"),
            ("14-administrator-audit-trail.png", "Audit search"),
            ("15-administrator-assistant-summary.png", "Operational summary"),
        ],
    ),
]


def font(size: int, bold: bool = False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size)


def create_montage(output_name: str, entries: list[tuple[str, str]]) -> None:
    columns = 2 if len(entries) > 1 else 1
    rows = (len(entries) + columns - 1) // columns
    cell_width = 1160
    image_width = 1080
    image_height = 750
    label_height = 50
    gap = 36
    outer = 44
    canvas_width = columns * cell_width + (columns - 1) * gap + outer * 2
    canvas_height = rows * (image_height + label_height) + (rows - 1) * gap + outer * 2
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(canvas)
    label_font = font(29, bold=True)

    for index, (filename, label) in enumerate(entries):
        row = index // columns
        column = index % columns
        x = outer + column * (cell_width + gap)
        y = outer + row * (image_height + label_height + gap)
        image = Image.open(SOURCE / filename).convert("RGB")
        image.thumbnail((image_width, image_height), Image.Resampling.LANCZOS)
        image_x = x + (cell_width - image.width) // 2
        image_y = y
        canvas.paste(image, (image_x, image_y))
        draw.rectangle((image_x - 1, image_y - 1, image_x + image.width, image_y + image.height), outline="#59636e", width=2)
        bounds = draw.textbbox((0, 0), label, font=label_font)
        label_width = bounds[2] - bounds[0]
        draw.text((x + (cell_width - label_width) // 2, y + image_height + 10), label, fill="#111111", font=label_font)

    canvas.save(OUTPUT / output_name, optimize=True)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for output_name, entries in GROUPS:
        create_montage(output_name, entries)
    print(f"Created {len(GROUPS)} interface montage figures")


if __name__ == "__main__":
    main()
