"""Generate a styled session report PDF."""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# App theme colors
BG = colors.HexColor("#0B1120")
PANEL = colors.HexColor("#131B2E")
EDGE = colors.HexColor("#1F2A44")
TEAL = colors.HexColor("#2DD4BF")
AMBER = colors.HexColor("#F5A524")
RED = colors.HexColor("#EF4444")
TEXT = colors.HexColor("#E5E9F0")
MUTED = colors.HexColor("#7C8AA3")
WHITE = colors.white


def _attentiveness_color(percent):
    if percent >= 80:
        return TEAL
    if percent >= 50:
        return AMBER
    return RED


def _status_label(alerts, warnings, attentiveness):
    if alerts == 0 and warnings == 0 and attentiveness >= 85:
        return "Remarks: Excellent", TEAL
    if alerts == 0 and attentiveness >= 70:
        return "Remarks: Good", TEAL
    if alerts <= 2:
        return "Remarks: Moderate", AMBER
    return "Remarks: Needs Attention", RED


def _hex(color):
    return "#" + color.hexval()[2:]


def build_report_pdf(report_data, output_dir):
    """Build a formatted PDF report and return the filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_report_{timestamp}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="Argus Session Report",
        author="Argus Sleep Monitor",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=26,
        textColor=WHITE,
        leading=30,
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=TEAL,
        leading=14,
        spaceAfter=4,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=BG,
        spaceBefore=6,
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#334155"),
        leading=14,
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=MUTED,
        alignment=TA_CENTER,
    )

    attentiveness = report_data["attentiveness_percent"]
    status_text, status_color = _status_label(
        report_data["total_sleep_alerts"],
        report_data["total_early_warnings"],
        attentiveness,
    )

    # Header banner
    header_inner = Table(
        [[
            Paragraph("ARGUS", title_style),
            Paragraph(
                f'<font color="#2DD4BF"><b>{status_text}</b></font>',
                ParagraphStyle(
                    "StatusBadge",
                    fontName="Helvetica-Bold",
                    fontSize=11,
                    textColor=TEAL,
                    alignment=TA_CENTER,
                ),
            ),
        ]],
        colWidths=[4.2 * inch, 1.8 * inch],
    )
    header_inner.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("BACKGROUND", (0, 0), (-1, -1), BG),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16),
            ("TOPPADDING", (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )

    header_block = Table([[header_inner]], colWidths=[6.7 * inch])
    header_block.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BG),
            ("BOX", (0, 0), (-1, -1), 0, BG),
            ("ROUNDEDCORNERS", [8, 8, 0, 0]),
        ])
    )

    meta_table = Table(
        [[
            Paragraph("Session Report", subtitle_style),
            Paragraph(
                f'Generated {datetime.now().strftime("%d %b %Y, %H:%M")}',
                ParagraphStyle("Gen", fontName="Helvetica", fontSize=9, textColor=MUTED, alignment=TA_CENTER),
            ),
        ]],
        colWidths=[2.5 * inch, 4.2 * inch],
    )
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BG),
            ("LEFTPADDING", (0, 0), (0, 0), 16),
            ("RIGHTPADDING", (1, 0), (1, 0), 16),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ])
    )

    # Summary stat cards
    stat_cards = [
        ("Duration", report_data["duration"], TEAL),
        ("Sleep Alerts", str(report_data["total_sleep_alerts"]), RED
        if report_data["total_sleep_alerts"] else TEAL),
        ("Early Warnings", str(report_data["total_early_warnings"]), AMBER if report_data["total_early_warnings"] else TEAL),
        ("Attentiveness", f'{attentiveness}%', _attentiveness_color(attentiveness)),
    ]

    card_cells = []
    for label, value, accent in stat_cards:
        card_cells.append(
            Paragraph(
                f'<font color="#7C8AA3" size="8">{label.upper()}</font><br/>'
                f'<font color="{_hex(accent)}"><b>{value}</b></font>',
                ParagraphStyle(
                    f"Card_{label}",
                    fontName="Helvetica",
                    fontSize=18,
                    leading=22,
                    alignment=TA_CENTER,
                ),
            )
        )

    stats_table = Table([card_cells], colWidths=[1.6 * inch] * 4, rowHeights=[0.85 * inch])
    stats_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PANEL),
            ("BOX", (0, 0), (-1, -1), 1, EDGE),
            ("INNERGRID", (0, 0), (-1, -1), 1, EDGE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ])
    )

    # Session details
    details_data = [
        ["Session Start", report_data["session_start"]],
        ["Session End", report_data["session_end"]],
        ["Total Duration", report_data["duration"]],
        ["Overall Status", status_text],
    ]
    details_table = Table(details_data, colWidths=[1.8 * inch, 4.9 * inch])
    details_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
            ("BACKGROUND", (1, 0), (1, -1), WHITE),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#0F172A")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 1, EDGE),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )

    # Attentiveness bar
    bar_total = 4.9 * inch
    filled_width = bar_total * (min(max(attentiveness, 0), 100) / 100)
    empty_width = bar_total - filled_width
    bar_color = _attentiveness_color(attentiveness)
    bar_table = Table(
        [["", ""]],
        colWidths=[max(filled_width, 0.001), max(empty_width, 0.001)],
        rowHeights=[0.2 * inch],
    )
    bar_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), bar_color),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0, colors.HexColor("#E2E8F0")),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ])
    )

    # --- Pandas-derived analytics (event breakdown + average gap between alerts) ---
    event_counts = report_data.get("event_counts") or {}
    avg_gap_seconds = report_data.get("avg_gap_seconds")

    analytics_rows = [["Metric", "Value"]]
    if event_counts:
        for event_type, count in event_counts.items():
            analytics_rows.append([event_type, str(count)])
    else:
        analytics_rows.append(["No events recorded", "—"])

    if avg_gap_seconds is not None:
        analytics_rows.append(["Avg. time between alerts", f"{avg_gap_seconds}s"])

    analytics_table = Table(analytics_rows, colWidths=[4.0 * inch, 2.7 * inch], repeatRows=1)
    analytics_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), TEAL),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#334155")),
            ("BOX", (0, 0), (-1, -1), 1, EDGE),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )

    # Events table
    events = report_data.get("events") or []
    event_rows = [["Time", "Elapsed", "Event Type"]]
    for event in events:
        elapsed = event.get("elapsed_seconds", 0)
        mins, secs = divmod(elapsed, 60)
        event_rows.append([
            event.get("time", "—"),
            f"{mins:02d}:{secs:02d}",
            event.get("type", "—"),
        ])

    if len(event_rows) == 1:
        event_rows.append(["—", "—", "No events recorded during this session"])

    events_table = Table(event_rows, colWidths=[1.3 * inch, 1.3 * inch, 4.1 * inch], repeatRows=1)
    event_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEAL),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#334155")),
        ("BOX", (0, 0), (-1, -1), 1, EDGE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(1, len(event_rows)):
        if i % 2 == 0:
            event_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8FAFC")))
        event_type = event_rows[i][2] if len(event_rows[i]) > 2 else ""
        if "Red" in event_type or "Sleep Alert" in event_type:
            event_styles.append(("TEXTCOLOR", (2, i), (2, i), RED))
        elif "Yellow" in event_type or "Early Warning" in event_type:
            event_styles.append(("TEXTCOLOR", (2, i), (2, i), AMBER))
    events_table.setStyle(TableStyle(event_styles))

    story = [
        header_block,
        meta_table,
        Spacer(1, 16),
        stats_table,
        Spacer(1, 18),
        Paragraph("Session Details", section_style),
        details_table,
        Spacer(1, 16),
        Paragraph("Attentiveness Score", section_style),
        Paragraph(
            f'<font color="#64748B">Eye detection rate across the session — '
            f'<b>{attentiveness}%</b></font>',
            body_style,
        ),
        Spacer(1, 6),
        bar_table,
        Spacer(1, 18),
        Paragraph("Event Breakdown", section_style),
        analytics_table,
        Spacer(1, 18),
        Paragraph("Event Timeline", section_style),
        events_table,
        Spacer(1, 24),
        HRFlowable(width="100%", thickness=1, color=EDGE, spaceBefore=6, spaceAfter=10),
        Paragraph(
            "Argus Sleep Monitor · Computer Vision Drowsiness Detection System<br/>"
            "This report was generated automatically at the end of your monitoring session.",
            footer_style,
        ),
    ]

    doc.build(story)
    return filename