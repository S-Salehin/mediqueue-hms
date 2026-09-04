"""Generate restrained academic diagrams for the final report."""

from __future__ import annotations

import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "report_assets" / "diagrams"
SIZE = (1800, 1000)

INK = "#172B3A"
ACCENT = "#19766D"
LINE = "#6F8798"
LIGHT_LINE = "#B9C6CF"
BLUE = "#EAF2F7"
GREEN = "#E9F4F1"
WARM = "#FBF3DE"
ROSE = "#F8ECEE"
GRAY = "#F5F7F8"
WHITE = "#FFFFFF"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = ("arialbd.ttf", "calibrib.ttf") if bold else ("arial.ttf", "calibri.ttf")
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F_TITLE = load_font(27, True)
F_BODY = load_font(23)
F_SMALL = load_font(20)
F_TINY = load_font(17)
F_LABEL = load_font(19, True)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", SIZE, WHITE)
    return image, ImageDraw.Draw(image)


def _lines(text: str, width: int) -> list[str]:
    output: list[str] = []
    for block in text.split("\n"):
        output.extend(textwrap.wrap(block, width=width, break_long_words=False) or [""])
    return output


def text_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], text: str, *,
             font=F_BODY, fill=INK, width=26, align="center") -> None:
    x1, y1, x2, y2 = xy
    lines = _lines(text, width)
    leading = round(font.size * 1.28)
    y = y1 + max(8, (y2 - y1 - leading * len(lines)) // 2)
    for line in lines:
        bounds = draw.textbbox((0, 0), line, font=font)
        line_width = bounds[2] - bounds[0]
        x = x1 + 16 if align == "left" else x1 + (x2 - x1 - line_width) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += leading


def card(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str, detail: str = "", *,
         fill=WHITE, outline=INK, detail_width=29) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=12, fill=fill, outline=outline, width=2)
    if detail:
        draw.text((x1 + 22, y1 + 18), title, font=F_LABEL, fill=INK)
        draw.line((x1 + 20, y1 + 54, x2 - 20, y1 + 54), fill=LIGHT_LINE, width=2)
        text_box(draw, (x1 + 7, y1 + 62, x2 - 7, y2 - 8), detail, font=F_SMALL,
                 width=detail_width)
    else:
        text_box(draw, xy, title, font=F_LABEL, width=detail_width)


def group(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str) -> None:
    draw.rounded_rectangle(xy, radius=14, fill=GRAY, outline=LIGHT_LINE, width=2)
    draw.text((xy[0] + 20, xy[1] + 16), title, font=F_LABEL, fill=INK)


def arrow(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], *, color=ACCENT,
          width=4, dashed=False) -> None:
    if dashed:
        for start, end in zip(points, points[1:]):
            length = math.dist(start, end)
            if length == 0:
                continue
            for offset in range(0, int(length), 18):
                end_offset = min(offset + 10, length)
                p1 = (start[0] + (end[0] - start[0]) * offset / length,
                      start[1] + (end[1] - start[1]) * offset / length)
                p2 = (start[0] + (end[0] - start[0]) * end_offset / length,
                      start[1] + (end[1] - start[1]) * end_offset / length)
                draw.line((p1, p2), fill=color, width=width)
    else:
        draw.line(points, fill=color, width=width, joint="curve")
    if len(points) < 2:
        return
    start, end = points[-2], points[-1]
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 14
    left = (end[0] - size * math.cos(angle - math.pi / 6),
            end[1] - size * math.sin(angle - math.pi / 6))
    right = (end[0] - size * math.cos(angle + math.pi / 6),
             end[1] - size * math.sin(angle + math.pi / 6))
    draw.polygon((end, left, right), fill=color)


def note(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], text: str, *, width=95) -> None:
    draw.rounded_rectangle(xy, radius=10, fill=GRAY, outline=LIGHT_LINE, width=2)
    text_box(draw, (xy[0] + 10, xy[1] + 5, xy[2] - 10, xy[3] - 5), text,
             font=F_TINY, width=width)


def save(image: Image.Image, name: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT / name, "PNG", optimize=True)


def methodology() -> None:
    image, draw = canvas()
    draw.line((145, 215, 1655, 215), fill=ACCENT, width=4)
    steps = [
        ("1", "Understand", "Requirements, users, risks and scope"),
        ("2", "Design", "Permissions, states, data and API contracts"),
        ("3", "Build", "One complete React, API and database slice"),
        ("4", "Verify", "Unit, API, browser, security and accessibility"),
        ("5", "Review", "Hospital role walkthrough and correction"),
        ("6", "Release", "Evidence, migration, rollback and gates"),
    ]
    for index, (number, title, detail) in enumerate(steps):
        x = 55 + index * 290
        cx = x + 125
        draw.ellipse((cx - 38, 177, cx + 38, 253), fill=WHITE, outline=ACCENT, width=4)
        text_box(draw, (cx - 38, 177, cx + 38, 253), number, font=F_LABEL, fill=ACCENT)
        card(draw, (x, 315, x + 250, 660), title, detail, detail_width=20)
    note(draw, (240, 770, 1560, 900),
         "A failed check returns the work to the earliest affected stage. A failed launch gate prevents the use of real patient data.", width=118)
    save(image, "01_incremental_methodology.png")


def architecture() -> None:
    image, draw = canvas()
    group(draw, (50, 90, 400, 890), "Client zone")
    group(draw, (445, 90, 1450, 890), "Application host")
    group(draw, (1495, 90, 1750, 890), "Approved service")
    arrow(draw, [(350, 360), (525, 360)])
    arrow(draw, [(785, 360), (890, 360)])
    arrow(draw, [(1130, 455), (1130, 610)])
    arrow(draw, [(1250, 710), (1320, 710)])
    arrow(draw, [(1440, 710), (1535, 710)])
    card(draw, (100, 260, 350, 460), "Web browser", "Patient and staff\nReact interface", fill=BLUE)
    card(draw, (525, 240, 785, 480), "Caddy gateway", "HTTPS termination\nStatic assets\nSecurity headers\n/api/v1 proxy", fill=GREEN)
    card(draw, (890, 225, 1370, 455), "Django REST API", "Session and CSRF protection\nRole and object checks\nDomain services and audit", detail_width=38)
    card(draw, (890, 610, 1250, 815), "PostgreSQL 18", "Business records\nRow locks and constraints\nOutbox and audit", fill=BLUE)
    card(draw, (1320, 610, 1440, 815), "Worker", "Claims outbox\nSafe retry", fill=WARM, detail_width=15)
    card(draw, (1535, 610, 1710, 815), "SMTP", "Minimal email\nDelivery result", detail_width=18)
    note(draw, (500, 540, 815, 635), "Private application network. PostgreSQL has no public port.", width=32)
    save(image, "02_system_architecture.png")


def roles() -> None:
    image, draw = canvas()
    arrow(draw, [(420, 245), (600, 245), (600, 400), (665, 400)])
    arrow(draw, [(420, 710), (600, 710), (600, 580), (665, 580)])
    arrow(draw, [(1380, 245), (1200, 245), (1200, 400), (1135, 400)])
    arrow(draw, [(1380, 710), (1200, 710), (1200, 580), (1135, 580)])
    card(draw, (70, 145, 420, 345), "Patient", "Own profile, appointments, queue token, notifications and consent", fill=BLUE, detail_width=31)
    card(draw, (70, 610, 420, 810), "Receptionist", "Registration, booking, check in, walk in, queue and onsite payment", fill=WARM, detail_width=31)
    card(draw, (1380, 145, 1730, 345), "Doctor", "Own schedule, assigned patients and own live queue", fill=GREEN, detail_width=31)
    card(draw, (1380, 610, 1730, 810), "Administrator", "Staff, directory, schedules, settings, reports and audit", fill=ROSE, detail_width=31)
    card(draw, (665, 315, 1135, 665), "Hospital Operations API", "Default deny authorization\nFiltered querysets\nObject level checks\nImmutable audit events", outline=ACCENT, detail_width=34)
    note(draw, (545, 825, 1255, 950),
         "Staff use TOTP MFA. Patients verify email ownership. Sessions remain HttpOnly, and browser tokens are not stored in local storage.", width=70)
    save(image, "03_role_access_context.png")


def appointment_queue() -> None:
    image, draw = canvas()
    draw.text((55, 75), "Appointment lifecycle", font=F_TITLE, fill=INK)
    draw.text((55, 495), "Queue lifecycle after check in", font=F_TITLE, fill=INK)
    arrow(draw, [(285, 225), (420, 225)])
    arrow(draw, [(650, 225), (760, 225), (760, 155), (900, 155)])
    arrow(draw, [(650, 225), (900, 225)])
    arrow(draw, [(650, 225), (760, 225), (760, 355), (900, 355)])
    card(draw, (55, 155, 285, 295), "Availability", "Computed from schedule and capacity", fill=BLUE, detail_width=24)
    card(draw, (420, 155, 650, 295), "Confirmed", "Capacity reserved", fill=GREEN, detail_width=24)
    card(draw, (900, 100, 1165, 210), "Cancelled", "Terminal", fill=ROSE, detail_width=22)
    card(draw, (900, 225, 1165, 335), "Completed", "Terminal", fill=GREEN, detail_width=22)
    card(draw, (900, 350, 1165, 460), "No show", "Terminal", fill=ROSE, detail_width=22)
    note(draw, (1260, 145, 1735, 385),
         "Appointment and queue states remain separate. Check in creates one queue ticket. Completion or no show closes the related appointment through the controlled service path.", width=43)
    queue_y = 650
    boxes = [(55, "Check in"), (340, "Waiting"), (625, "Called"), (910, "In service"), (1195, "Completed")]
    for index in range(len(boxes) - 1):
        arrow(draw, [(boxes[index][0] + 210, queue_y), (boxes[index + 1][0], queue_y)])
    for x, title in boxes:
        card(draw, (x, queue_y - 65, x + 210, queue_y + 65), title)
    card(draw, (555, 820, 765, 930), "Deferred", "Reason required", fill=WARM, detail_width=22)
    card(draw, (910, 820, 1120, 930), "No show", "Reason required", fill=ROSE, detail_width=22)
    arrow(draw, [(445, 715), (445, 875), (555, 875)])
    arrow(draw, [(765, 875), (800, 875), (800, 715), (730, 715)])
    arrow(draw, [(1015, 715), (1015, 820)])
    save(image, "04_appointment_queue_workflow.png")


def adaptive_window() -> None:
    image, draw = canvas()
    inputs = [
        ((70, 120, 410, 275), "Schedule baseline", "Configured consultation duration", BLUE),
        ((70, 375, 410, 530), "Observed service", "Latest 20 valid completed visits", GREEN),
        ((70, 630, 410, 785), "Live position", "People ahead in the current queue", WARM),
    ]
    for xy, _, _, _ in inputs:
        arrow(draw, [(xy[2], (xy[1] + xy[3]) // 2), (545, 500)])
    arrow(draw, [(1005, 500), (1150, 500)])
    for xy, title, detail, fill in inputs:
        card(draw, xy, title, detail, fill=fill, detail_width=30)
    card(draw, (545, 190, 1005, 810), "Transparent estimator", "Fewer than five visits\nUse schedule duration\n\nFive or more visits\n70% recent median\n30% schedule duration\n\nClamp to 5 to 60 minutes\nUse median absolute deviation\nfor the uncertainty range", outline=ACCENT, detail_width=34)
    card(draw, (1150, 165, 1730, 835), "Patient safe result", "Own queue token\nCurrently served token\nPeople ahead\nEstimated wait range\nRecommended arrival window\nConfidence and sample count\nLast updated time\n\nNo patient identity disclosure\nNo medical priority decision", fill=GREEN, outline=ACCENT, detail_width=38)
    save(image, "05_adaptive_arrival_window.png")


def assistant() -> None:
    image, draw = canvas()
    arrow(draw, [(300, 470), (420, 470)])
    arrow(draw, [(710, 470), (820, 470)])
    arrow(draw, [(1110, 470), (1200, 470)])
    arrow(draw, [(1470, 470), (1570, 470)])
    arrow(draw, [(565, 760), (565, 640)])
    card(draw, (50, 350, 300, 590), "Signed in user", "Question and bounded recent messages", fill=BLUE, detail_width=24)
    card(draw, (420, 300, 710, 640), "Safety gate", "Role from session\nRate and length limits\nPrompt injection screening\nMedical advice boundary", fill=ROSE, detail_width=27)
    card(draw, (820, 300, 1110, 640), "Intent handler", "Local system guide\nDeterministic answers\nApproved live fact queries\nOptional provider routing", fill=WARM, detail_width=27)
    card(draw, (1200, 300, 1470, 640), "Response guard", "Plain text only\nNo write operation\nNo credentials or secrets\nRequest ID recorded", fill=GREEN, detail_width=25)
    card(draw, (1570, 350, 1750, 590), "Reply", "Role scoped\nRead only", fill=BLUE, detail_width=18)
    card(draw, (380, 760, 750, 930), "Allowlisted role context", "Own records, assigned schedule or approved aggregate counts only", detail_width=35)
    note(draw, (860, 760, 1510, 930),
         "The local answer path remains available when the optional language provider is disabled, unavailable or unsafe.", width=67)
    save(image, "06_role_aware_assistant.png")


def deployment() -> None:
    image, draw = canvas()
    group(draw, (370, 80, 1470, 610), "Bangladesh VPS  |  Ubuntu 24.04 LTS  |  host firewall  |  key based SSH")
    arrow(draw, [(310, 300), (450, 300)])
    arrow(draw, [(700, 300), (790, 300)])
    arrow(draw, [(1050, 400), (1050, 465)])
    arrow(draw, [(1180, 520), (1250, 520)])
    arrow(draw, [(1050, 595), (1050, 665), (400, 665), (400, 715)])
    arrow(draw, [(925, 595), (925, 790)])
    arrow(draw, [(400, 800), (520, 800)], dashed=True)
    card(draw, (55, 220, 310, 380), "Internet clients", "HTTPS only", fill=BLUE)
    card(draw, (450, 210, 700, 390), "Caddy", "TLS and same origin gateway", fill=GREEN, detail_width=20)
    card(draw, (790, 190, 1310, 400), "Django API", "Application service\nHealth endpoints\nAudit and outbox writes", detail_width=38)
    card(draw, (790, 465, 1180, 595), "PostgreSQL 18", "Private network and persistent volume", fill=BLUE, detail_width=35)
    card(draw, (1250, 465, 1410, 595), "Worker", "Outbox retry", fill=WARM, detail_width=16)
    card(draw, (55, 690, 400, 865), "Encrypted backup", "Daily full copy\nHourly recovery points\n30 day retention", fill=BLUE, detail_width=30)
    card(draw, (520, 715, 870, 890), "Restore rehearsal", "Clean environment\nRPO 1 hour\nRTO 4 hours", fill=GREEN, detail_width=30)
    card(draw, (925, 715, 1410, 890), "Monitoring and alerts", "Health, logs, storage, database, outbox, certificate and backup age", fill=ROSE, detail_width=42)
    save(image, "07_deployment_topology.png")


def data_model() -> None:
    image, draw = canvas()
    groups = [
        ((45, 115, 395, 505), "Identity", "User\nRoleAssignment\nStaffInvitation\nStaffMFADevice\nLoginAudit", BLUE),
        ((475, 115, 825, 505), "Directory and consent", "Hospital\nDepartment, location, chamber\nDoctorProfile, PatientProfile\nPrivacyNoticeVersion\nConsentRecord", GREEN),
        ((905, 115, 1255, 505), "Appointments and queue", "Schedule and exception\nAppointment and history\nQueueSession and ticket\nQueueEvent\nQueueEstimateRecord", WARM),
        ((1335, 115, 1685, 505), "Communication and control", "Notification and preference\nOutbox and attempt\nPaymentRecord and history\nAuditEvent\nIdempotencyRecord", ROSE),
    ]
    for xy, *_ in groups:
        x = (xy[0] + xy[2]) // 2
        arrow(draw, [(x, xy[3]), (x, 660)], color=LINE)
    arrow(draw, [(395, 310), (475, 310)])
    arrow(draw, [(825, 310), (905, 310)])
    arrow(draw, [(1255, 310), (1335, 310)])
    for xy, title, detail, fill in groups:
        card(draw, xy, title, detail, fill=fill, detail_width=31)
    card(draw, (170, 660, 1560, 910), "Integrity foundation", "UUID external identifiers. Restrictive deletion. Append only history, consent, audit and notification attempts. One queue ticket per appointment. One active service ticket per queue. Capacity cannot be exceeded. Terminal appointment states cannot reopen. Payment uses BDT minor units and stores no card data.", outline=ACCENT, detail_width=105)
    save(image, "08_core_data_model.png")


def main() -> None:
    methodology()
    architecture()
    roles()
    appointment_queue()
    adaptive_window()
    assistant()
    deployment()
    data_model()
    print(f"Generated 8 report diagrams in {OUTPUT}")


if __name__ == "__main__":
    main()
