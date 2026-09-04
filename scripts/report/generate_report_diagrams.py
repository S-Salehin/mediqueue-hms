"""Generate the project diagrams used by the final report.

The diagrams are deliberately drawn from the implemented architecture and workflow.
They do not depend on a diagram service, which keeps the report build reproducible.
"""

from __future__ import annotations

import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "report_assets" / "diagrams"

NAVY = "#13324A"
TEAL = "#087F73"
MINT = "#DDF4EF"
BLUE = "#DDECF7"
AMBER = "#FFF0C7"
ROSE = "#FCE0E3"
INK = "#17232D"
MUTED = "#526471"
LINE = "#8BA2B2"
WHITE = "#FFFFFF"
BG = "#F7FAFB"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


F_TITLE = font(34, True)
F_HEAD = font(24, True)
F_BODY = font(20)
F_SMALL = font(17)
F_SMALL_BOLD = font(17, True)


def canvas(title: str, subtitle: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (1600, 900), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1600, 92), fill=NAVY)
    draw.text((55, 22), title, fill=WHITE, font=F_TITLE)
    if subtitle:
        draw.text((57, 105), subtitle, fill=MUTED, font=F_SMALL)
    return image, draw


def wrapped(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, *,
            text_font=F_BODY, fill=INK, align="center", max_chars=24) -> None:
    x1, y1, x2, y2 = box
    lines = textwrap.wrap(text, width=max_chars, break_long_words=False)
    line_height = int(text_font.size * 1.25)
    total = len(lines) * line_height
    y = y1 + max(8, (y2 - y1 - total) // 2)
    for line in lines:
        bounds = draw.textbbox((0, 0), line, font=text_font)
        width = bounds[2] - bounds[0]
        x = x1 + 12 if align == "left" else x1 + (x2 - x1 - width) // 2
        draw.text((x, y), line, fill=fill, font=text_font)
        y += line_height


def box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], label: str, *,
        fill=WHITE, outline=LINE, width=3, radius=16, text_font=F_BODY,
        text_fill=INK, max_chars=24) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    wrapped(draw, xy, label, text_font=text_font, fill=text_fill, max_chars=max_chars)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], *,
          fill=TEAL, width=5, label: str | None = None) -> None:
    draw.line((start, end), fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 15
    left = (
        end[0] - size * math.cos(angle - math.pi / 6),
        end[1] - size * math.sin(angle - math.pi / 6),
    )
    right = (
        end[0] - size * math.cos(angle + math.pi / 6),
        end[1] - size * math.sin(angle + math.pi / 6),
    )
    draw.polygon((end, left, right), fill=fill)
    if label:
        mx = (start[0] + end[0]) // 2
        my = (start[1] + end[1]) // 2
        bounds = draw.textbbox((0, 0), label, font=F_SMALL)
        draw.rectangle((mx - 8, my - 13, mx + bounds[2] + 8, my + 13), fill=BG)
        draw.text((mx, my - 11), label, fill=MUTED, font=F_SMALL)


def save(image: Image.Image, name: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT / name, "PNG", optimize=True)


def methodology() -> None:
    image, draw = canvas(
        "Incremental delivery and verification method",
        "Each usable slice passes implementation, review, automated checks and role based acceptance.",
    )
    steps = [
        ("1", "Understand", "Audit source documents, users, risks and release boundary"),
        ("2", "Design", "Define permissions, states, data constraints and interface contracts"),
        ("3", "Build", "Implement one vertical workflow across React, API and PostgreSQL"),
        ("4", "Verify", "Run unit, API, browser, security and accessibility checks"),
        ("5", "Review", "Exercise the workflow as the intended hospital role"),
        ("6", "Release", "Record evidence, migration, rollback and remaining launch gates"),
    ]
    x_positions = [60, 315, 570, 825, 1080, 1335]
    for index, (number, head, detail) in enumerate(steps):
        x = x_positions[index]
        draw.ellipse((x, 215, x + 88, 303), fill=TEAL, outline=NAVY, width=3)
        wrapped(draw, (x, 215, x + 88, 303), number, text_font=F_HEAD, fill=WHITE)
        box(draw, (x - 20, 340, x + 210, 600), f"{head}\n\n{detail}", fill=WHITE,
            outline=TEAL, text_font=F_SMALL, max_chars=21)
        if index < len(steps) - 1:
            arrow(draw, (x + 92, 259), (x_positions[index + 1] - 8, 259))
    draw.rounded_rectangle((210, 695, 1390, 810), radius=20, fill=MINT, outline=TEAL, width=3)
    wrapped(
        draw,
        (230, 705, 1370, 800),
        "Feedback returns to the earliest affected step. A failed permission test returns to design. A failed workflow returns to implementation. A failed launch gate prevents real patient data.",
        text_font=F_BODY,
        max_chars=104,
    )
    save(image, "01_incremental_methodology.png")


def architecture() -> None:
    image, draw = canvas(
        "System architecture",
        "Same origin web application with a versioned API, transactional database and database backed email outbox.",
    )
    box(draw, (70, 210, 350, 390), "Patient and staff browsers\nResponsive React application", fill=BLUE, outline=NAVY)
    box(draw, (480, 170, 760, 430), "Caddy web gateway\nHTTPS termination\nStatic React assets\nSecurity headers\n/api/v1 proxy", fill=MINT, outline=TEAL)
    box(draw, (890, 150, 1190, 450), "Django REST API\nSession and CSRF\nRole and object checks\nDomain services\nAudit recording", fill=WHITE, outline=NAVY)
    box(draw, (1280, 165, 1530, 335), "Notification worker\nSafe template rendering\nRetry control", fill=AMBER, outline="#B37A00")
    box(draw, (890, 590, 1190, 795), "PostgreSQL 18\nBusiness records\nRow locks\nConstraints\nOutbox and audit", fill=BLUE, outline=NAVY)
    box(draw, (1280, 595, 1530, 790), "Approved SMTP service\nMinimal email content\nDelivery outcome", fill=WHITE, outline=LINE)
    arrow(draw, (350, 300), (480, 300), label="HTTPS")
    arrow(draw, (760, 300), (890, 300), label="HTTP private")
    arrow(draw, (1040, 450), (1040, 590), label="SQL")
    arrow(draw, (1190, 265), (1280, 265), label="outbox signal")
    arrow(draw, (1405, 335), (1405, 595), label="SMTP")
    arrow(draw, (1280, 690), (1190, 690), label="claim jobs")
    draw.text((72, 465), "Trust boundary", fill=NAVY, font=F_SMALL_BOLD)
    draw.line((70, 495, 760, 495), fill=NAVY, width=3)
    draw.text((90, 515), "Public network", fill=MUTED, font=F_SMALL)
    draw.text((510, 515), "Gateway", fill=MUTED, font=F_SMALL)
    draw.text((930, 515), "Private application network", fill=MUTED, font=F_SMALL)
    save(image, "02_system_architecture.png")


def roles() -> None:
    image, draw = canvas(
        "Role and access context",
        "Every protected query is filtered by role and ownership before object data is returned.",
    )
    box(draw, (605, 300, 995, 590), "Hospital Operations API\n\nDefault deny authorization\nObject level access checks\nImmutable audit events", fill=MINT, outline=TEAL, text_font=F_HEAD, max_chars=29)
    role_boxes = [
        ((80, 185, 420, 375), "Patient\nOwn profile, appointments, queue token, notifications and consent", BLUE),
        ((80, 570, 420, 760), "Receptionist\nPatient registration, booking, check in, walk in, queue and onsite payment", AMBER),
        ((1180, 185, 1520, 375), "Doctor\nOwn schedule, assigned patients and own live queue", MINT),
        ((1180, 570, 1520, 760), "Administrator\nStaff, directory, schedules, settings, reports and audit", ROSE),
    ]
    for xy, label, color in role_boxes:
        box(draw, xy, label, fill=color, outline=NAVY, text_font=F_SMALL, max_chars=31)
    arrow(draw, (420, 280), (605, 385), label="own data")
    arrow(draw, (420, 665), (605, 520), label="operational scope")
    arrow(draw, (1180, 280), (995, 385), label="assigned scope")
    arrow(draw, (1180, 665), (995, 520), label="configured scope")
    draw.rounded_rectangle((485, 690, 1115, 815), radius=18, fill=WHITE, outline=LINE, width=3)
    wrapped(draw, (505, 702, 1095, 805), "Staff sign in with TOTP MFA. Patients confirm email ownership. Session cookies remain HttpOnly and browser tokens are not stored in local storage.", text_font=F_SMALL, max_chars=70)
    save(image, "03_role_access_context.png")


def appointment_queue() -> None:
    image, draw = canvas(
        "Appointment and queue workflow",
        "Appointment status and queue status are separate state machines joined at reception check in.",
    )
    appt_y = 245
    items = [
        (80, "Availability\ncomputed"),
        (340, "Appointment\nconfirmed"),
        (600, "Reception\ncheck in"),
        (860, "Queue ticket\nwaiting"),
        (1120, "Called and\nin service"),
        (1380, "Completed"),
    ]
    for x, label in items:
        box(draw, (x, appt_y, x + 180, appt_y + 125), label, fill=WHITE, outline=TEAL, text_font=F_SMALL, max_chars=18)
    for index in range(len(items) - 1):
        arrow(draw, (items[index][0] + 180, appt_y + 62), (items[index + 1][0], appt_y + 62))
    box(draw, (330, 510, 535, 630), "Cancelled", fill=ROSE, outline="#A84151", text_font=F_SMALL)
    box(draw, (890, 510, 1095, 630), "Deferred then\nrestored", fill=AMBER, outline="#B37A00", text_font=F_SMALL)
    box(draw, (1160, 510, 1365, 630), "No show", fill=ROSE, outline="#A84151", text_font=F_SMALL)
    arrow(draw, (430, 370), (430, 510), fill="#A84151", label="before service")
    arrow(draw, (950, 370), (990, 510), fill="#B37A00", label="reason required")
    arrow(draw, (1210, 370), (1260, 510), fill="#A84151", label="reason required")
    arrow(draw, (1095, 570), (1120, 345), fill="#B37A00")
    draw.rounded_rectangle((245, 705, 1355, 810), radius=18, fill=BLUE, outline=NAVY, width=3)
    wrapped(draw, (270, 713, 1330, 802), "PostgreSQL transactions, row locks, unique constraints and idempotency records protect the last slot, one check in, one active patient and one payment action when requests compete or repeat.", text_font=F_BODY, max_chars=105)
    save(image, "04_appointment_queue_workflow.png")


def adaptive_window() -> None:
    image, draw = canvas(
        "Adaptive Arrival Window calculation",
        "A transparent operational estimate supports arrival planning without medical triage or hidden prioritisation.",
    )
    inputs = [
        ((70, 180, 355, 315), "Configured slot duration\nSchedule baseline", BLUE),
        ((70, 385, 355, 520), "Latest 20 valid visits\nCompleted service durations", MINT),
        ((70, 590, 355, 725), "Current queue position\nPeople ahead and state", AMBER),
    ]
    for xy, label, fill in inputs:
        box(draw, xy, label, fill=fill, outline=NAVY, text_font=F_SMALL, max_chars=27)
        arrow(draw, (355, (xy[1] + xy[3]) // 2), (520, 450))
    box(draw, (520, 260, 920, 645), "Estimator v1\n\nIf fewer than 5 visits:\nuse configured duration\n\nOtherwise:\n0.70 x observed median\n+ 0.30 x configured duration\n\nClamp to 5 to 60 minutes\nUse median absolute deviation\nfor the uncertainty range", fill=WHITE, outline=TEAL, text_font=F_SMALL, max_chars=34)
    arrow(draw, (920, 450), (1070, 450))
    box(draw, (1070, 200, 1515, 700), "Patient safe output\n\nQueue token\nCurrently served token\nEstimated wait range\nRecommended arrival window\nConfidence label\nLast updated time\n\nNever another patient's name\nNever a clinical priority decision", fill=MINT, outline=TEAL, text_font=F_HEAD, max_chars=33)
    draw.rounded_rectangle((500, 735, 1520, 825), radius=18, fill=ROSE, outline="#A84151", width=3)
    wrapped(draw, (520, 742, 1500, 817), "Staff overrides require a reason and create an audit event. Accuracy, interval coverage, overrides, stale snapshots and notification delivery remain measurable after operational data becomes available.", text_font=F_SMALL, max_chars=103)
    save(image, "05_adaptive_arrival_window.png")


def assistant() -> None:
    image, draw = canvas(
        "Role aware help assistant",
        "Deterministic guidance and allowlisted live facts remain available when an external language provider is absent.",
    )
    box(draw, (60, 300, 330, 520), "Signed in user\nQuestion and recent user messages", fill=BLUE, outline=NAVY)
    box(draw, (430, 165, 760, 355), "Safety gate\nPrompt injection patterns\nMedical advice boundary\nLength and rate limits", fill=ROSE, outline="#A84151", text_font=F_SMALL, max_chars=30)
    box(draw, (430, 530, 760, 720), "Role context builder\nAllowlisted counts, schedules, queue state and own records", fill=MINT, outline=TEAL, text_font=F_SMALL, max_chars=31)
    box(draw, (880, 165, 1210, 355), "Local answer path\nSystem guide\nDeterministic intent handlers\nNo provider dependency", fill=AMBER, outline="#B37A00", text_font=F_SMALL, max_chars=31)
    box(draw, (880, 530, 1210, 720), "Optional Groq path\nFixed HTTPS endpoint\nSafe context only\nPlain text normalisation", fill=WHITE, outline=NAVY, text_font=F_SMALL, max_chars=31)
    box(draw, (1325, 300, 1545, 520), "Reply\nAnswer only\nNo write action\nNo secrets\nRequest ID", fill=BLUE, outline=NAVY, text_font=F_SMALL, max_chars=20)
    arrow(draw, (330, 410), (430, 260))
    arrow(draw, (330, 410), (430, 625))
    arrow(draw, (760, 260), (880, 260))
    arrow(draw, (760, 625), (880, 625))
    arrow(draw, (1210, 260), (1325, 375))
    arrow(draw, (1210, 625), (1325, 445))
    draw.text((790, 438), "Provider unavailable or unsafe request", fill=MUTED, font=F_SMALL)
    draw.line((880, 520, 880, 370, 1170, 370), fill=LINE, width=3)
    save(image, "06_role_aware_assistant.png")


def deployment() -> None:
    image, draw = canvas(
        "Pilot deployment and recovery topology",
        "A small maintainable deployment keeps the public surface narrow and the recovery evidence explicit.",
    )
    box(draw, (50, 180, 315, 325), "Internet clients\nHTTPS only", fill=BLUE, outline=NAVY)
    box(draw, (420, 155, 720, 350), "Bangladesh VPS\nUbuntu 24.04 LTS\nHost firewall\nKey based SSH", fill=MINT, outline=TEAL)
    draw.rounded_rectangle((805, 135, 1540, 610), radius=22, fill=WHITE, outline=NAVY, width=4)
    draw.text((840, 155), "Private Docker network", fill=NAVY, font=F_HEAD)
    box(draw, (850, 230, 1060, 350), "Caddy", fill=MINT, outline=TEAL)
    box(draw, (1120, 230, 1330, 350), "Django API", fill=BLUE, outline=NAVY)
    box(draw, (1120, 420, 1330, 540), "Worker", fill=AMBER, outline="#B37A00")
    box(draw, (850, 420, 1060, 540), "PostgreSQL", fill=WHITE, outline=NAVY)
    arrow(draw, (315, 250), (420, 250), label="443")
    arrow(draw, (720, 250), (850, 290))
    arrow(draw, (1060, 290), (1120, 290))
    arrow(draw, (1225, 350), (1010, 420))
    arrow(draw, (1120, 480), (1060, 480))
    box(draw, (95, 625, 430, 785), "Encrypted backup repository\nDaily full backup\nHourly recovery points\n30 day retention", fill=BLUE, outline=NAVY, text_font=F_SMALL, max_chars=31)
    box(draw, (610, 650, 930, 785), "Monitoring and alerts\nHealth, logs, disk, database, outbox and backup age", fill=ROSE, outline="#A84151", text_font=F_SMALL, max_chars=31)
    box(draw, (1110, 650, 1450, 785), "Recovery target\nRPO 1 hour\nRTO 4 hours\nRestore must be rehearsed", fill=MINT, outline=TEAL, text_font=F_SMALL, max_chars=31)
    arrow(draw, (905, 540), (430, 680), label="encrypted copy")
    arrow(draw, (1010, 610), (770, 650), label="telemetry")
    arrow(draw, (430, 705), (1110, 705), label="clean restore exercise")
    save(image, "07_deployment_topology.png")


def data_model() -> None:
    image, draw = canvas(
        "Core data model",
        "UUID identifiers, restrictive deletion, append only histories and explicit state records preserve operational traceability.",
    )
    groups = [
        ((45, 160, 345, 360), "Identity\nUser\nRoleAssignment\nStaffInvitation\nStaffMFADevice\nLoginAudit", BLUE),
        ((420, 160, 720, 390), "Directory and consent\nHospital\nDepartment, Location, Chamber\nDoctorProfile\nPatientProfile\nPrivacyNoticeVersion\nConsentRecord", MINT),
        ((795, 145, 1125, 420), "Appointments and queue\nSchedule, ScheduleException\nAppointment, AppointmentHistory\nQueueSession, QueueTicket\nQueueEvent\nQueueEstimateRecord", AMBER),
        ((1200, 160, 1545, 390), "Communication and control\nNotification and Preference\nNotificationOutbox and Attempt\nPaymentRecord and History\nAuditEvent\nIdempotencyRecord", ROSE),
    ]
    for xy, label, fill in groups:
        box(draw, xy, label, fill=fill, outline=NAVY, text_font=F_SMALL, max_chars=32)
    arrow(draw, (345, 260), (420, 260), label="profiles")
    arrow(draw, (720, 280), (795, 280), label="doctor/patient")
    arrow(draw, (1125, 280), (1200, 280), label="events")
    box(draw, (175, 555, 1425, 770), "Integrity rules\n\nOne active queue ticket per appointment. One called or in service ticket per queue. Slot capacity cannot be exceeded. Terminal appointment states cannot be reopened. History, consent, audit and notification attempt records are append only. Payment stores BDT minor units and no card data.", fill=WHITE, outline=TEAL, text_font=F_BODY, max_chars=100)
    for x in (195, 535, 875, 1215):
        arrow(draw, (x, 420 if x in (875,) else 390 if x in (535, 1215) else 360), (x, 555), fill=LINE)
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
