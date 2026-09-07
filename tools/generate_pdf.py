#!/usr/bin/env python3
"""
generate_pdf.py
Builds a comprehensive, publication-grade Circuit Diagram and Engineering Reference PDF:
- Page 1: Cover & Architecture Equivalence Matrix (Proposal vs Prototype)
- Page 2: Diagram A - Original In-Wall Smart Switch Architecture (Full Page)
- Page 3: Diagram B - Current Physical Demonstration Prototype (Full Page)
- Page 4: Technical Pinout Schedule, State Machine & Bill of Materials (BOM)
"""

import os
import hashlib

# Patch for python 3.8 / openssl compatibility with reportlab
orig_md5 = hashlib.md5
def safe_md5(*args, **kwargs):
    kwargs.pop('usedforsecurity', None)
    return orig_md5(*args, **kwargs)
hashlib.md5 = safe_md5

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register TrueType fonts to ensure embedded, publication-grade font rendering across all PDF engines
FONT_DIR = "/usr/share/fonts/liberation-sans-fonts"
pdfmetrics.registerFont(TTFont('Helvetica', f'{FONT_DIR}/LiberationSans-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Helvetica-Bold', f'{FONT_DIR}/LiberationSans-Bold.ttf'))
pdfmetrics.registerFont(TTFont('Helvetica-Oblique', f'{FONT_DIR}/LiberationSans-Italic.ttf'))
pdfmetrics.registerFont(TTFont('Helvetica-BoldOblique', f'{FONT_DIR}/LiberationSans-BoldItalic.ttf'))

from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = str(REPO_ROOT / "docs" / "circuit_diagrams.pdf")
DIAGRAM_A = str(REPO_ROOT / "assets" / "diagrams" / "diagram_a_original.png")
DIAGRAM_B = str(REPO_ROOT / "assets" / "diagrams" / "diagram_b_prototype.png")

class NumberedCanvas(canvas.Canvas):
    """Custom canvas that adds page numbers and running header/footer."""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Top Running Header (pages 2+)
        if self._pageNumber > 1:
            self.drawString(36, 566, "Project Proposal: Automated Low-Cost In-Wall Microcontroller Switch | Group: ZLATANFC")
            self.drawRightString(805, 566, "IIUM Energy Conservation (SDG 7 & 9)")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 560, 805, 560)

        # Bottom Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 30, 805, 30)

        self.drawString(36, 20, "KICT & KOE | International Islamic University Malaysia")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(805, 20, page_text)
        self.restoreState()

def build_pdf():
    doc = SimpleDocTemplate(
        PDF_PATH,
        pagesize=landscape(A4),
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=34
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=2
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
        spaceAfter=6
    )

    h1_style = ParagraphStyle(
        'Heading1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=4,
        spaceAfter=2
    )

    diag_h1 = ParagraphStyle(
        'DiagHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=0,
        spaceAfter=2
    )

    diag_sub = ParagraphStyle(
        'DiagSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.5,
        textColor=colors.HexColor("#334155"),
        spaceBefore=0,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.8,
        leading=10.5,
        textColor=colors.white,
        alignment=1
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.8,
        textColor=colors.HexColor("#1E293B")
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.8,
        textColor=colors.HexColor("#0F172A")
    )

    story = []

    # =========================================================================
    # PAGE 1: COVER & ARCHITECTURAL EQUIVALENCE MATRIX
    # =========================================================================
    banner_data = [[
        Paragraph(
            "<b>INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA (IIUM)</b><br/>"
            "<b>KICT & KOE — Kulliyyah of Information & Comm. Tech. & Kulliyyah of Engineering</b><br/>"
            "<font size=7 color='#475569'>Smart Campus Energy Conservation Initiative | SDG 7: Clean Energy | SDG 9: Innovation & Infrastructure</font>",
            subtitle_style
        ),
        Paragraph(
            "<b>Group: ZLATANFC</b><br/>"
            "<b>Project: Automated In-Wall Switch</b><br/>"
            "<font size=7 color='#059669'>● Bench Hardware Prototype Verified</font>",
            subtitle_style
        )
    ]]
    banner_table = Table(banner_data, colWidths=[520, 250])
    banner_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(banner_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=6))

    story.append(Paragraph("CIRCUIT SCHEMATICS & HARDWARE ARCHITECTURE REFERENCE", title_style))
    story.append(Paragraph(
        "<b>Document Scope:</b> This technical reference provides full engineering circuit diagrams and component specifications for both "
        "<b>(A) The Original Proposed Commercial In-Wall Smart Switch</b> designed for 240VAC campus retrofitting, and "
        "<b>(B) The Physical Demonstration Prototype</b> currently constructed, flashed, and fully operational on the breadboard bench.",
        body_style
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Executive Comparison: Proposal Specification vs. Bench Demonstration Prototype", h1_style))
    story.append(Paragraph(
        "To ensure 100% electrical safety during classroom laboratory testing under KOE supervision, the proof-of-concept (POC) bench prototype "
        "implements a safe low-voltage (5V DC) equivalent architecture that maps 1-to-1 to all features of the final in-wall module without exposing students to hazardous 240VAC mains power.",
        body_style
    ))
    story.append(Spacer(1, 4))

    matrix_data = [
        [
            Paragraph("Subsystem / Domain", table_header),
            Paragraph("Original Proposed In-Wall Design (Diagram A)", table_header),
            Paragraph("Current Physical Demo Prototype (Diagram B)", table_header),
            Paragraph("Functional Equivalence & Engineering Rationale", table_header)
        ],
        [
            Paragraph("<b>Core Controller</b>", table_cell_bold),
            Paragraph("ESP32-C3 SuperMini (32-bit RISC-V @ 160MHz, built-in Wi-Fi 4 / BLE 5)", table_cell),
            Paragraph("Arduino Uno R3 (ATmega328P @ 16MHz, USB CDC Serial @ 115200 baud)", table_cell),
            Paragraph("Executes identical timetable state machine, auto-shutdown delays, manual override debounce, and EEPROM non-volatile schedule memory.", table_cell)
        ],
        [
            Paragraph("<b>Power Architecture</b>", table_cell_bold),
            Paragraph("240VAC Mains -> 2A Fuse + MOV (14D471K) -> HLK-PM01 (5V 3W) -> AMS1117 (3.3V)", table_cell),
            Paragraph("5V DC regulated power via USB Power Bank (untethered) or PC Host USB Cable", table_cell),
            Paragraph("Eliminates high-voltage shock and fire risks on the bench while supplying identical stable 5V and 3.3V logic rails.", table_cell)
        ],
        [
            Paragraph("<b>Output Actuation (Lights & AC)</b>", table_cell_bold),
            Paragraph("2x Optocoupled 5V Relays (10A 250VAC) with 1N4007 flyback diodes switching 240V loads", table_cell),
            Paragraph("3x Ballasted LEDs: Yellow (Lights), Blue (AC), Red (Standby / Idle) + 220 Ohm", table_cell),
            Paragraph("Provides immediate, direct visual confirmation of appliance switching states without needing high-power inductive AC loads on the breadboard.", table_cell)
        ],
        [
            Paragraph("<b>Manual Override Switch</b>", table_cell_bold),
            Paragraph("Standard physical wall rocker switch wired as dry contact to GPIO9 with 10k pullup", table_cell),
            Paragraph("Tactile Pushbutton 1 (Pin 10, INPUT_PULLUP) acting as manual classroom toggle", table_cell),
            Paragraph("Validates the offline-first requirement: physical override toggles appliances instantly even during server disconnects.", table_cell)
        ],
        [
            Paragraph("<b>Clock & Status Display</b>", table_cell_bold),
            Paragraph("Virtual status reported over MQTT network telemetry to central university dashboard", table_cell),
            Paragraph("5641AS 4-Digit Display (multiplexed via 74HC595 shift register + Pins A0-A3)", table_cell),
            Paragraph("Provides live local visual feedback of 24-hr system clock (HH.MM) and countdown timers during pre-cooling and auto-shutdown phases.", table_cell)
        ],
        [
            Paragraph("<b>Demonstration Accelerator</b>", table_cell_bold),
            Paragraph("Real-time university academic schedule (running at 1x real seconds)", table_cell),
            Paragraph("Tactile Pushbutton 2 (Pin 9, INPUT_PULLUP) accelerating simulation 600x (1 sec = 10 min)", table_cell),
            Paragraph("Allows academic evaluators and technicians to observe an entire 24-hour campus schedule cycle in just 2.4 minutes.", table_cell)
        ],
        [
            Paragraph("<b>Central Management GUI</b>", table_cell_bold),
            Paragraph("Central FastAPI web backend + MQTT broker communicating over campus Wi-Fi", table_cell),
            Paragraph("Python CustomTkinter Desktop GUI (`switch_gui.py`) over USB Serial CDC", table_cell),
            Paragraph("Supports live schedule uploading, real-time status monitoring, manual remote triggers, and EEPROM non-volatile flash saving.", table_cell)
        ]
    ]

    col_widths = [95, 220, 220, 235]
    matrix_table = Table(matrix_data, colWidths=col_widths, repeatRows=1)
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(matrix_table)
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: DIAGRAM A (ORIGINAL IN-WALL RETROFIT CIRCUIT)
    # =========================================================================
    story.append(Paragraph("DIAGRAM A: ORIGINAL PROPOSED IN-WALL SMART SWITCH ARCHITECTURE", diag_h1))
    story.append(Paragraph(
        "<b>Architecture:</b> 240VAC Mains -&gt; 2A Fuse &amp; 14D471K MOV -&gt; HLK-PM01 (5V DC) -&gt; AMS1117-3.3 LDO -&gt; "
        "ESP32-C3 SuperMini MCU -&gt; Galvanic Optocoupler Isolation (PC817) -&gt; Dual 10A 250VAC Relays -&gt; Classroom Lights &amp; AC Unit.",
        diag_sub
    ))
    # Dimensions: 740 x 440 pt
    story.append(Image(DIAGRAM_A, width=740, height=440))
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: DIAGRAM B (PHYSICAL DEMONSTRATION PROTOTYPE)
    # =========================================================================
    story.append(Paragraph("DIAGRAM B: PHYSICAL DEMONSTRATION HARDWARE PROTOTYPE (BENCH CIRCUIT)", diag_h1))
    story.append(Paragraph(
        "<b>Architecture:</b> Arduino Uno R3 (ATmega328P) via 5V Powerbank -&gt; SN74HC595N Shift Register (D8, D7, D6) -&gt; "
        "5641AS 4-Digit Display (Cathodes A0-A3) -&gt; 3x LEDs (Lights D13, AC D12, Standby D11) -&gt; 2x Buttons (Override D10, Accel D9) -&gt; CustomTkinter GUI.",
        diag_sub
    ))
    # Dimensions: 740 x 440 pt
    story.append(Image(DIAGRAM_B, width=740, height=440))
    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: TECHNICAL PINOUT SCHEDULE, STATE MACHINE & BILL OF MATERIALS
    # =========================================================================
    story.append(Paragraph("TECHNICAL SPECIFICATIONS, STATE MACHINE & BILL OF MATERIALS (BOM)", title_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#065F46"), spaceAfter=5))

    pinout_data = [
        [Paragraph("Arduino Pin", table_header), Paragraph("Connected Component", table_header), Paragraph("Breadboard Location", table_header), Paragraph("Electrical Configuration", table_header)],
        [Paragraph("<b>Pin 13</b>", table_cell_bold), Paragraph("Yellow LED (Classroom Lights)", table_cell), Paragraph("Rows 1–2", table_cell), Paragraph("OUTPUT, Active HIGH via 220 Ohm ballast resistor", table_cell)],
        [Paragraph("<b>Pin 12</b>", table_cell_bold), Paragraph("Blue LED (Air Conditioner)", table_cell), Paragraph("Rows 5–6", table_cell), Paragraph("OUTPUT, Active HIGH via 220 Ohm ballast resistor", table_cell)],
        [Paragraph("<b>Pin 11</b>", table_cell_bold), Paragraph("Red LED (Standby / Idle)", table_cell), Paragraph("Rows 9–10", table_cell), Paragraph("OUTPUT, Active HIGH via 220 Ohm ballast resistor", table_cell)],
        [Paragraph("<b>Pin 10</b>", table_cell_bold), Paragraph("Tactile Button 1 (Manual Override)", table_cell), Paragraph("Row 20", table_cell), Paragraph("INPUT_PULLUP, Active LOW, Debounced (50ms)", table_cell)],
        [Paragraph("<b>Pin 9</b>", table_cell_bold), Paragraph("Tactile Button 2 (Speed Accel 600x)", table_cell), Paragraph("Row 25", table_cell), Paragraph("INPUT_PULLUP, Active LOW, Fast-forward clock", table_cell)],
        [Paragraph("<b>Pin 8</b>", table_cell_bold), Paragraph("74HC595 Serial Data (DS / SER)", table_cell), Paragraph("Row 35j (Pin 14)", table_cell), Paragraph("OUTPUT, Synchronous serial bitstream", table_cell)],
        [Paragraph("<b>Pin 7</b>", table_cell_bold), Paragraph("74HC595 Storage Latch (ST_CP)", table_cell), Paragraph("Row 37j (Pin 12)", table_cell), Paragraph("OUTPUT, Rising-edge parallel transfer pulse", table_cell)],
        [Paragraph("<b>Pin 6</b>", table_cell_bold), Paragraph("74HC595 Shift Clock (SH_CP)", table_cell), Paragraph("Row 38j (Pin 11)", table_cell), Paragraph("OUTPUT, Rising-edge bit shift clock pulse", table_cell)],
        [Paragraph("<b>Pin A0</b>", table_cell_bold), Paragraph("5641AS Digit 1 Cathode (Leftmost)", table_cell), Paragraph("Row 55c (Pin 12)", table_cell), Paragraph("OUTPUT, Active LOW multiplex current sink", table_cell)],
        [Paragraph("<b>Pin A1</b>", table_cell_bold), Paragraph("5641AS Digit 2 Cathode", table_cell), Paragraph("Row 52c (Pin 9)", table_cell), Paragraph("OUTPUT, Active LOW multiplex current sink", table_cell)],
        [Paragraph("<b>Pin A2</b>", table_cell_bold), Paragraph("5641AS Digit 3 Cathode", table_cell), Paragraph("Row 51c (Pin 8)", table_cell), Paragraph("OUTPUT, Active LOW multiplex current sink", table_cell)],
        [Paragraph("<b>Pin A3</b>", table_cell_bold), Paragraph("5641AS Digit 4 Cathode (Rightmost)", table_cell), Paragraph("Row 50i (Pin 6)", table_cell), Paragraph("OUTPUT, Active LOW multiplex current sink", table_cell)],
        [Paragraph("<b>5V / GND</b>", table_cell_bold), Paragraph("Power Rails & 74HC595 VCC/MR/OE", table_cell), Paragraph("Rows 33-40 & Rails", table_cell), Paragraph("VCC=5V (P16), MR=5V (P10), OE=GND (P13), GND=GND (P8)", table_cell)]
    ]
    pinout_table = Table(pinout_data, colWidths=[65, 135, 95, 175])
    pinout_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#065F46")),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 1.8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.8),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))

    bom_data = [
        [Paragraph("Item / Component", table_header), Paragraph("Target Spec (Diagram A)", table_header), Paragraph("Bench POC (Diagram B)", table_header), Paragraph("Est. Cost (MYR)", table_header)],
        [Paragraph("Microcontroller", table_cell_bold), Paragraph("ESP32-C3 SuperMini", table_cell), Paragraph("Arduino Uno R3 (ATmega328P)", table_cell), Paragraph("RM 12.50 / RM 18.00", table_cell)],
        [Paragraph("AC-DC Power Module", table_cell_bold), Paragraph("HLK-PM01 (240V -> 5V 3W)", table_cell), Paragraph("USB 5V Powerbank Cable", table_cell), Paragraph("RM 9.80 / RM 0.00", table_cell)],
        [Paragraph("Surge Protection", table_cell_bold), Paragraph("14D471K MOV + 2A Fuse", table_cell), Paragraph("Host USB Overcurrent Limit", table_cell), Paragraph("RM 1.20 / RM 0.00", table_cell)],
        [Paragraph("Switching Elements", table_cell_bold), Paragraph("2x 5V 10A Relays + PC817", table_cell), Paragraph("3x 5mm LEDs (Y, B, R) + 220R", table_cell), Paragraph("RM 5.60 / RM 0.90", table_cell)],
        [Paragraph("Display / Indicator", table_cell_bold), Paragraph("Onboard Status LED", table_cell), Paragraph("5641AS 4-Digit Display", table_cell), Paragraph("RM 0.20 / RM 4.50", table_cell)],
        [Paragraph("Shift Register IC", table_cell_bold), Paragraph("Not Required (Ample GPIO)", table_cell), Paragraph("SN74HC595N 8-bit SIPO", table_cell), Paragraph("RM 0.00 / RM 1.50", table_cell)],
        [Paragraph("Manual Controls", table_cell_bold), Paragraph("Wall Rocker Switch Contact", table_cell), Paragraph("2x Tactile Pushbuttons", table_cell), Paragraph("RM 2.50 / RM 0.60", table_cell)],
        [Paragraph("<b>TOTAL ESTIMATE</b>", table_cell_bold), Paragraph("<b>~RM 31.80 per unit</b>", table_cell_bold), Paragraph("<b>~RM 25.50 (POC Parts)</b>", table_cell_bold), Paragraph("<b>Target < RM 35</b>", table_cell_bold)]
    ]
    bom_table = Table(bom_data, colWidths=[90, 100, 95, 65])
    bom_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 1.8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.8),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))

    state_desc = Paragraph(
        "<b>Firmware State Machine Logic (`smart_switch.ino`):</b><br/>"
        "● <b>PRE_COOLING (T - 15m):</b> AC turns ON (Blue LED active), Lights stay OFF. Display counts down remaining pre-cooling minutes.<br/>"
        "● <b>CLASS_OCCUPIED (T_start to T_end):</b> AC and Lights both ON (Blue & Yellow LEDs active). Countdown displays minutes until class dismissal.<br/>"
        "● <b>AUTO_SHUTDOWN (T_end + 10m):</b> Post-class grace period. If no consecutive class scheduled, appliances cut off. Flashes warning countdown.<br/>"
        "● <b>STANDBY_IDLE:</b> All appliances OFF. Red LED active. Display displays live 24-hr clock (HH.MM) with blinking colon.<br/>"
        "● <b>NIGHTLY SWEEP (22:00):</b> Hard shutoff signal cuts any active appliances left running overnight.<br/>"
        "● <b>MANUAL OVERRIDE:</b> Instant dry-contact interrupt toggle. User can turn room ON/OFF anytime; auto-clears at start of next scheduled event.",
        body_style
    )

    layout_data = [
        [
            Paragraph("<b>Hardware Pinout Map (Breadboard POC)</b>", h1_style),
            Paragraph("<b>Component Bill of Materials (BOM) & Costs</b>", h1_style)
        ],
        [
            pinout_table,
            bom_table
        ],
        [
            Paragraph("<b>Operational State Machine Architecture</b>", h1_style),
            Paragraph("<b>Safety & Compliance Highlights (KOE / IIUM)</b>", h1_style)
        ],
        [
            state_desc,
            Paragraph(
                "<b>1. Supervised Installation:</b> Lab technician review required prior to 240VAC wall box integration.<br/>"
                "<b>2. Creepage & Clearance:</b> PCB layout requires minimum 4.0mm air gap and 6.3mm creepage between 240V mains traces and low-voltage logic.<br/>"
                "<b>3. Surge Suppression:</b> 14D471K MOV clamps inductive surges up to 4500A; 2A slow-blow fuse isolates circuit during catastrophic faults.<br/>"
                "<b>4. DPGA Open-Source:</b> All schematics, Gerber files, and firmware are released under permissive open-source licenses supporting SDG 7 & 9.",
                body_style
            )
        ]
    ]

    layout_table = Table(layout_data, colWidths=[470, 300])
    layout_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(layout_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF Successfully Generated at: {PDF_PATH}")

if __name__ == "__main__":
    build_pdf()
