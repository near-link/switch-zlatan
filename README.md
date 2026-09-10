# Automated Low-Cost In-Wall Microcontroller Switch
## Autonomous Multi-Tier Energy Management and IoT Actuation System
**Project Group:** ZLATANFC  
**Target SDGs:** SDG 7 (Affordable and Clean Energy), SDG 9 (Industry, Innovation and Infrastructure), SDG 12 (Responsible Consumption and Production)  
**Target Facilities:** Institutional Academic Buildings, Lecture Halls, and Laboratories (IIUM Pilot Rollout)  

---

## System Overview

This project provides an automated, timetable-driven power management solution designed to eliminate idle energy waste in institutional facilities. Classroom air conditioning and lighting loads are autonomously synchronized to academic course schedules, enforcing pre-cooling cycles before lectures, automated shutdown after dismissal, and guaranteed physical manual override.

The repository documents two distinct system implementations:
1. **Section 1: Physical Demonstration Prototype (Breadboard POC):** The benchtop educational proof of concept engineered for live presentation, evaluation, and safe hardware demonstration.
2. **Section 2: Commercial Production System (Industrial In-Wall Specification):** The scalable, commercial-grade building management architecture featuring custom in-wall smart switches and a dedicated Raspberry Pi Edge Gateway.

---

# SECTION 1: Physical Demonstration Prototype (Breadboard POC)

The demonstration kit is engineered as a safe, 5V DC low-voltage bench build. It enables evaluators to verify autonomous scheduling, acoustic state notifications, real-time clock acceleration, and manual fail-safe actuation without exposure to 240V mains hazards.

## 1.1 Prototype Hardware Architecture

```
                       [ Laptop / Host Controller ]
                                     |
                                     | USB Serial (/dev/ttyACM0 @ 9600 baud)
                                     v
                           [ Arduino Uno R3 ]
                   (ATmega328P, 16 MHz, 5V Logic)
                  +------------------+------------------+
                  | (EEPROM: Permanent Schedule Memory) |
                  v                                     v
          [ Inputs and Logic ]                 [ Outputs and Actuators ]
      +-- Button 1 (Pin 10): Manual Override       +-- Pin 13: Classroom Lighting LED
      +-- Button 2 (Pin 9):  Fast-Forward Clock    +-- Pin 12: Air Conditioning (AC) LED
      +-- 9V Battery (DC Barrel Jack)              +-- Pin 11: Standby / Status LED
      +-- USB 5V (Tethered / Gateway mode)         +-- Pin 5:  Piezo Beeper
                                                   +-- 4-Digit Clock (5641AS Display)
                                                       +-- Pins 8, 7, 6 (74HC595 Driver)
                                                       +-- Pins A0-A3 (Cathode Digits 1-4)
```

## 1.2 Hardware Pinout Schedule

| Arduino Pin | Breadboard Location | Component / Subsystem | Functional Role in Prototype |
| :--- | :--- | :--- | :--- |
| **GND** | Blue (-) Rail | System Ground | Common ground reference across all modules |
| **5V** | Red (+) Rail | Logic Power Rail | Powers 74HC595 shift register, display, and buttons |
| **Pin 13** | Row 3a | Yellow LED (5mm) | Classroom Lighting Circuit (simulates 480W luminaire load) |
| **Pin 12** | Row 8a | Blue LED (5mm) | Air Conditioning Circuit (simulates 2,200W HVAC compressor) |
| **Pin 11** | Row 13a | Red LED (5mm) | Standby and Status indicator (solid during off-hours, blinks in grace) |
| **Pin 10** | Row 19a (Extender) | Momentary Pushbutton 1 | Manual Wall Switch (offline fail-safe toggle and override) |
| **Pin 9** | Row 24a (Extender) | Momentary Pushbutton 2 | Clock Accelerator (fast-forwards time at 10 simulated min/sec) |
| **Pin 5** | Row 28a | Piezo Beeper | Acoustic feedback for mode changes, warnings, and alerts |
| **Pin 8** | Row 35j | 74HC595 Pin 14 (DS) | Shift Register Serial Data line |
| **Pin 7** | Row 37j | 74HC595 Pin 12 (ST_CP) | Shift Register Storage Latch Clock |
| **Pin 6** | Row 38j | 74HC595 Pin 11 (SH_CP) | Shift Register Shift Clock |
| **Pin A0** | Row 55c | 5641AS Digit 1 | Common Cathode: Tens of Hours digit |
| **Pin A1** | Row 52c | 5641AS Digit 2 | Common Cathode: Hours digit and Colon |
| **Pin A2** | Row 51c | 5641AS Digit 3 | Common Cathode: Tens of Minutes digit |
| **Pin A3** | Row 50i | 5641AS Digit 4 | Common Cathode: Minutes digit |

## 1.3 Quickstart and Local Execution

### Flashing the Microcontroller Firmware
Flashing the C++ firmware to the Arduino Uno takes one command:
```bash
./flash.sh
```
This script automatically releases any open serial port locks, compiles the sketch with `arduino-cli`, and uploads to `/dev/ttyACM0`.

### Running the Edge Web Gateway
Launch the FastAPI edge gateway server:
```bash
./run_web.sh
```
- Local URL: `http://localhost:8000`
- Network URL: `http://<laptop-ip>:8000`
- Automatically discovers and interfaces with the Arduino on `/dev/ttyACM0`.
- Includes password-protected login, weekly timetable editor, digital twin telemetry feed, and diagnostics console.

### Running Desktop GUI (Alternative)
A standalone CustomTkinter graphical interface is also available:
```bash
./run_gui.sh
```

## 1.4 Evaluator Untethered Demonstration Runbook

The prototype can be demonstrated fully untethered to evaluators:

1. **Battery Hand-Off:** Connect a standard 9V battery to the Arduino DC barrel jack. The onboard regulator switches power cleanly with zero reset.
2. **Unplug USB:** Disconnect the USB cable. The ATmega328P maintains the current timetable in non-volatile EEPROM and continues clock counting and display multiplexing uninterrupted.
3. **Walk to Evaluator:**
   - **Standby State:** Show that only the Red LED is lit while the clock ticks. Yellow (Lights) and Blue (AC) remain cut, demonstrating zero idle power waste.
   - **Fast-Forward Simulation:** Hold Button 2 (Pin 9). The 4-digit clock races forward at 10 simulated minutes per second:
     - 10 minutes prior to class: Blue LED (AC) turns ON automatically (pre-cooling phase).
     - Class start: Yellow LED (Lights) turns ON alongside AC.
     - Class dismissal: Grace period countdown begins, Red LED blinks, and beeper sounds warning tones.
     - 10 minutes after class: Automated shutdown isolates both Yellow and Blue loads.
   - **Offline Manual Override:** Press Button 1 (Pin 10) during an off-period. Lights engage instantly. This demonstrates that network or server outages will never leave instructors locked out of classroom utilities.

---

# SECTION 2: Commercial Production System (Industrial In-Wall Specification)

The commercial production design transitions the verified firmware logic into an industrial, scalable Building Management System (BMS). It consists of two dedicated hardware layers:
1. **In-Wall Smart Switch Units:** Installed inside standard wall boxes across all classrooms.
2. **Central Raspberry Pi Edge Gateway:** Installed in each floor or wing distribution board, functioning simultaneously as the command dispatcher and the secure web gateway host.

## 2.1 Production System Architecture

```
 [ Authorized Facility Managers / Technicians ]
                        |
                        | Encrypted Ingress (HTTPS / WSS + Password Auth)
                        v
 +-----------------------------------------------------------------------------+
 |   PROTECTED PUBLIC DOMAIN (Cloudflare Zero Trust / Secure Edge Tunnel)     |
 |   Domain: switch.domain.edu (or trycloudflare edge route)                   |
 +--------------------------------------+--------------------------------------+
                                        |
                                        v
 +-----------------------------------------------------------------------------+
 |   RASPBERRY PI EDGE GATEWAY AND BMS CONTROLLER (1 per Floor / Wing)        |
 |                                                                             |
 |   [ ROLE 1: SECURE WEB SERVER HOST ]                                        |
 |   +-- FastAPI REST API and Real-Time WebSocket Telemetry Daemon             |
 |   +-- SQLite Timetable Database (web/timetable.db)                          |
 |   +-- Local Schedule Cache (Zero-Downtime Campus Network Resilience)        |
 |   +-- Protected Public Domain Ingress Handler                               |
 |                                                                             |
 |   [ ROLE 2: CENTRAL COMMAND AND CONTROL MASTER ]                            |
 |   +-- Real-Time Schedule and Policy Command Dispatcher                      |
 |   +-- High-Precision Calendar NTP Time Synchronization Service              |
 |   +-- Multi-Room Fleet Broadcast Arbitration Engine                         |
 |   +-- Communication Interface: MQTT over TLS (Wi-Fi/VLAN) / RS-485 Modbus   |
 +--------------------------------------+--------------------------------------+
                                        |
                  +---------------------+---------------------+
                  | Local Secure Wi-Fi / Private VLAN /       |
                  | Industrial RS-485 Modbus RTU Bus          |
                  v                                           v
 +----------------------------------+     +----------------------------------+
 |  ROOM 1 IN-WALL SMART SWITCH     |     |  ROOM N IN-WALL SMART SWITCH     |
 |  Standard BS 4662 (86x86x47mm)   |     |  Standard BS 4662 (86x86x47mm)   |
 |                                  |     |                                  |
 |  +-- ESP32-S3 SoC (Dual-Core)    |     |  +-- ESP32-S3 SoC (Dual-Core)    |
 |  +-- Hi-Link HLK-PM01 (AC-DC)    |     |  +-- Hi-Link HLK-PM01 (AC-DC)    |
 |  +-- Dual 16A Latching Relays    |     |  +-- Dual 16A Latching Relays    |
 |  +-- MOV + RC Snubber Protection |     |  +-- MOV + RC Snubber Protection |
 |  +-- DS3231 RTC + CR1220 Battery |     |  +-- DS3231 RTC + CR1220 Battery |
 |  +-- Tactile Rocker Wall Plate   |     |  +-- Tactile Rocker Wall Plate   |
 +----------------------------------+     +----------------------------------+
```

## 2.2 Dual-Role Raspberry Pi Edge Gateway

In production, a dedicated industrial Raspberry Pi (Raspberry Pi 4 Model B, Raspberry Pi 5, or Compute Module 4 with eMMC) is deployed inside the sub-distribution panel of each building wing or floor. It serves two distinct, mission-critical functions:

### Role 1: Command and Control Master
The Raspberry Pi functions as the local orchestrator for all in-wall switches within its assigned zone:
- **Central Timetable Dispatcher:** Automatically pushes weekly class schedules, pre-cooling parameters, and grace period thresholds to in-wall units.
- **Clock and Synchronization Master:** Maintains synchronized calendar time via Network Time Protocol (NTP), broadcasting time sync packets to all in-wall RTCs to eliminate drift.
- **Command Arbitration:** Translates campus-wide operations (such as semester breaks, holiday overrides, and emergency building shutdowns) into room-specific actuation commands.
- **Multi-Drop Industrial Fieldbus:** Communicates with in-wall switches over MQTT over TLS across an isolated facilities VLAN or via a shielded, daisy-chained RS-485 Modbus RTU serial bus (supporting runs up to 1,200 meters through existing electrical conduits).

### Role 2: Edge Web Server via Protected Public Domain
The same Raspberry Pi hosts the central management portal and securely exposes it to authorized staff over the internet:
- **Embedded Web Server:** Runs the production FastAPI application, WebSocket telemetry bridge, and SQLite database engine directly on Linux.
- **Zero-Downtime Edge Resilience:** Even if the central university datacenter or wide-area internet connection drops, the Raspberry Pi continues operating locally, maintaining classroom schedules without interruption.
- **Protected Public Domain Exposure:** The Raspberry Pi establishes an encrypted outbound tunnel (such as Cloudflare Zero Trust / Cloudflare Tunnel or SSH reverse proxy over TLS) to a public domain (for example, `switch.institution.edu` or a secure trycloudflare endpoint).
- **No Inbound Port Forwarding Required:** The tunnel requires zero open inbound firewall ports on the university network, shielding the campus from port scans, unauthorized probing, and DDoS attacks.
- **Access Authentication:** Remote access is gated behind web session password authentication and TLS encryption, allowing facility directors, engineers, and authorized lecturers to securely monitor room occupancy, adjust schedules, or trigger manual overrides from any browser or smartphone worldwide.

## 2.3 In-Wall Switch Hardware Specifications

### Mechanical Enclosure and Compliance
- **Standard Backbox Form Factor:** Form-fitted for British Standard **BS 4662:2006+A1:2009** flush metal conduit boxes (86 mm width x 86 mm height x 47 mm depth), standard across Malaysian and Commonwealth institutional facilities.
- **PCB Construction:** Custom 2-layer FR-4 glass epoxy printed circuit board (1.6 mm thickness, 2 oz copper on high-voltage AC paths).
- **High-Voltage Isolation:** Creepage and clearance distances between mains 240V AC and low-voltage 3.3V/5V DC planes exceed 6.3 mm, complying with **IEC 60669-2-1** and **UL 60730-1**.
- **Terminal Blocks:** Rising-cage screw terminal blocks accepting up to 4.0 mm² solid or stranded building conductors (Live In, Neutral, Switched Lighting, Switched HVAC).

### Microcontroller and Timekeeping
- **Microcontroller:** Espressif **ESP32-S3** System-on-Chip (Dual-Core 32-bit Xtensa LX7 @ 240 MHz, 512 KB SRAM, 8 MB Flash).
  - Integrated 2.4 GHz Wi-Fi (802.11 b/g/n) and Bluetooth Low Energy 5.0.
  - Hardware cryptographic accelerators for AES-256, RSA-3072, and secure boot verification.
- **Hardware Real-Time Clock:** Maxim **DS3231** I2C high-precision RTC with internal temperature-compensated crystal oscillator (TCXO), rated to +/- 2 ppm accuracy (less than 1 minute drift per year).
- **Battery Backup:** On-board **CR1220 lithium coin cell**, providing up to 10 years of autonomous timekeeping during total building blackouts.
- **Clock Acceleration Button Removal:** The 10x fast-forward button present on the demonstration kit is omitted from the production unit; production switches operate strictly in real time, with rapid testing restricted to authenticated maintenance APIs.

### Power Supply and Actuation Subsystems
- **Integrated Isolated Power Supply:** Hi-Link **HLK-PM01** (or Mean Well IRM-03-5) step-down power module.
  - Input: 100V to 240V AC, 50/60 Hz.
  - Output: Regulated 5V DC @ 600 mA (3W max).
  - Isolation Barrier: 3,000V AC input-to-output galvanic isolation.
  - Quiescent Standby Power: Less than or equal to 0.1 W.
- **Bi-Stable Magnetic Latching Relays:** Dual 16A / 250V AC latching relays (Omron G5RL-K or Panasonic ADW11).
  - **Zero Quiescent Hold Power:** Unlike traditional electromagnetic relays that consume 0.5W to 0.8W continuously while energized, magnetic latching relays use an internal permanent magnet to remain latched in either the ON or OFF state. They require only a brief 15 ms pulse to toggle and consume **0 Watts** during steady state.
  - **Brownout Immunity:** Relays maintain their mechanical contact state through grid power dips and interruptions.
- **Surge Suppression and Arc Quenching:**
  - **14D471K Metal Oxide Varistor (MOV):** Clamps mains voltage transients up to 4,500A.
  - **RC Snubber Circuit:** 100 Ohm metal oxide resistor paired in series with a 0.1 uF X2-rated suppression film capacitor placed directly across the HVAC relay contacts to eliminate inductive kickback arcing during compressor disconnection.
  - **Protection Fuse:** 2A slow-blow ceramic fuse isolates the switch assembly during catastrophic line faults.

### User Interface and Interaction
- **Wall Faceplate:** Minimalist fire-retardant polycarbonate wall plate featuring dual momentary tactile rockers (Lighting and HVAC).
- **Status Indication:** Dual-color micro-LED ring indicators embedded flush within the switch frame to provide clear visual feedback without ambient glare.
- **Quick-Access QR Code:** Each faceplate carries a laser-etched room identifier QR code. Faculty members can scan the code to load the room controller directly on mobile devices without physical contact.

---

# Technical Equivalence Matrix (Demo vs. Production)

| Technical Dimension | Section 1: Demonstration Prototype | Section 2: Commercial Production System |
| :--- | :--- | :--- |
| **Primary Microcontroller** | Arduino Uno R3 (ATmega328P @ 16 MHz, 5V) | Espressif ESP32-S3 (Dual-Core LX7 @ 240 MHz, 3.3V) |
| **Form Factor / Enclosure** | Solderless breadboard bench kit | British Standard BS 4662 (86x86x47mm) steel backbox |
| **Internal Power Supply** | 5V USB / 9V DC barrel jack battery | Hi-Link HLK-PM01 isolated 100-240V AC to 5V DC PSU |
| **Load Actuation** | 5mm Diffused LEDs (Yellow, Blue) | Dual 16A / 250V AC Bi-Stable Magnetic Latching Relays |
| **Quiescent Coil Power** | Standard GPIO drive (approx. 20 mA) | **0.0 Watts** (15 ms pulse latching mechanism) |
| **Transient Protection** | Low-voltage current limiting resistors | 14D471K MOV (4,500A clamp) + RC Snubber network |
| **Hardware Real-Time Clock** | Arduino millis() software timer tracking | Maxim DS3231 TCXO RTC (+/- 2 ppm) + NTP sync |
| **Clock Battery Backup** | External 9V demonstration battery | On-board CR1220 coin cell (10-year lifespan) |
| **Local Time Display** | 4-Digit 7-segment 5641AS LED display | Compact OLED status display / Flush LED halo |
| **Central Controller / BMS** | Developer laptop running FastAPI bridge | **Dedicated Raspberry Pi 4/5 Edge Gateway** |
| **Controller Command Role** | Direct USB Serial CDC (/dev/ttyACM0) | **Command Master via MQTT over TLS / RS-485 Bus** |
| **Remote Web Access** | Localhost / Local Area Network | **Protected Public Domain (Cloudflare / TLS Tunnel)** |
| **Access Control** | Browser session password prompt | Role-Based Access Control (RBAC) + QR code tokens |
| **Clock Accelerator** | Physical Button 2 (10 simulated min/sec) | Omitted in production; accessible via debug API |
| **Target Application** | Academic presentation and thesis defense | Campus-wide building energy retrofit (250+ rooms) |

---

# Campus Energy Economics and SDG Impact

## Single Classroom Impact (Annual Savings)
- **Lighting Load:** 480W (12 troffers @ 40W each)
- **HVAC Load:** 2,200W (2.5 HP split inverter unit)
- **Average Manual Runtime:** 12.5 hours per day (frequently left running through lunch, breaks, and evenings)
- **Automated Scheduled Runtime:** 6.2 hours per day (strictly restricted to registered lecture hours)
- **Daily Energy Reduction:** 16.9 kWh saved per classroom per day (50.4% total energy reduction)
- **Financial Savings:** RM 6.17 saved per day / **RM 1,851 saved per classroom annually** (at RM 0.365/kWh across 300 academic days)

## Campus-Wide Fleet Scaling (250 Classrooms)
- **Annual Campus Energy Saved:** 1,267,500 kWh / year
- **Annual Campus Utility Bill Reduction:** **RM 462,750 / year**
- **Estimated Full Retrofit Capital Cost:** RM 122,500 (250 switch units + floor edge gateways)
- **Project Capital Payback Period:** **3.18 Months**

## Sustainable Development Goals (SDG) Alignment
- **SDG 7 (Affordable and Clean Energy):** Directly curbs institutional electrical waste and eliminates unnecessary baseload generation.
- **SDG 9 (Industry, Innovation and Infrastructure):** Provides resilient edge automation where individual classrooms maintain autonomous operation through network failures.
- **SDG 12 (Responsible Consumption and Production):** Drop-in retrofit into existing BS 4662 conduit backboxes eliminates the need for masonry demolition or replacing legacy wiring.

---

# Technical Documentation Index

Detailed engineering references, schematics, and presentation runbooks are located in [`docs/`](docs/):

| Document | Description |
| :--- | :--- |
| [docs/SYSTEM_SPECIFICATION.md](docs/SYSTEM_SPECIFICATION.md) | Full system architecture, mathematical formulations, state machine logic, and serial protocols |
| [docs/PRODUCTION_SPECIFICATION.md](docs/PRODUCTION_SPECIFICATION.md) | In-depth commercial dual-relay specifications, PCB layouts, MOV snubber equations, and campus topology |
| [docs/DEMO_SPECIFICATION.md](docs/DEMO_SPECIFICATION.md) | Breadboard demonstration prototype build, hardware pinouts, power safety, and complete bill of materials |
| [docs/DEMO_OVERVIEW.md](docs/DEMO_OVERVIEW.md) | Live evaluation runbook, core talking points, and academic thesis alignment |
| [docs/DEMO_PRESETS_GUIDE.md](docs/DEMO_PRESETS_GUIDE.md) | Six evaluator test scenarios (Morning Class, Fast-Forward, Pre-cool, Grace Period, Weekend Off, Force ON) |
| [docs/SMART_SWITCH_EXECUTIVE_GUIDE.md](docs/SMART_SWITCH_EXECUTIVE_GUIDE.md) | Executive summary, commercial business case, university ROI models, and SDG mapping |
| [docs/circuit_diagrams.pdf](docs/circuit_diagrams.pdf) | Official 4-page publication-grade circuit schematic documentation |
| [docs/SECURITY_ARCHITECTURE.md](docs/SECURITY_ARCHITECTURE.md) | Full security architecture, edge gateway HMAC authentication, and cloud reverse proxy specs |

---

# Software Directory Structure

```
automated-in-wall-switch/
├── README.md                         # Main engineering overview and quickstart hub
├── flash.sh                          # One-command Arduino firmware flashing launcher
├── run_web.sh                        # FastAPI Web Gateway and Cloud tunnel launcher
├── run_gui.sh                        # CustomTkinter Desktop GUI launcher
│
├── smart_switch/                     # Embedded Arduino C++ Firmware
│   └── smart_switch.ino              # Autonomous EEPROM engine, multiplexing and state machine
│
├── web/                              # Edge Gateway and Digital Twin Web Application
│   ├── server.py                     # FastAPI REST API and WebSocket telemetry hub
│   ├── serial_bridge.py              # Thread-safe USB Serial CDC communication bridge
│   ├── database.py                   # SQLite persistence layer and audit logger
│   ├── timetable.db                  # Pre-seeded IIUM academic timetable and policies
│   └── static/                       # Industrial Brutalist frontend (HTML/CSS/JS)
│       ├── index.html                # Web dashboard and digital twin UI
│       ├── app.js                    # Client-side state and WebSocket management
│       ├── style.css                 # Dark-mode Brutalist stylesheet and animations
│       └── wallpaper.png             # UI textured wallpaper
│
├── desktop/                          # Alternative Offline Desktop Interface
│   └── switch_gui.py                 # CustomTkinter desktop monitor and timetable manager
│
├── docs/                             # Engineering and Academic Specifications
│   ├── SYSTEM_SPECIFICATION.md       # High-level architecture, circuit math and telemetry
│   ├── PRODUCTION_SPECIFICATION.md   # Commercial dual-relay, PCB and MOV snubber specifications
│   ├── DEMO_SPECIFICATION.md         # Breadboard prototype build and pinout mapping
│   ├── DEMO_OVERVIEW.md              # Live demonstration quick-reference
│   ├── DEMO_PRESETS_GUIDE.md         # Evaluator scenario presets and presentation scripts
│   ├── SMART_SWITCH_EXECUTIVE_GUIDE.md # SDG alignment and executive summary
│   ├── SECURITY_ARCHITECTURE.md      # Security architecture, edge HMAC auth & reverse proxy specs
│   └── circuit_diagrams.pdf         # 4-page full engineering schematic PDF
│
├── assets/                           # Schematics and Visual Artifacts
│   ├── diagrams/                     # Architecture and bench schematics (PNG)
│   │   ├── diagram_a_original.png    # Commercial production block diagram
│   │   └── diagram_b_prototype.png   # Bench prototype circuit wiring diagram
│   └── screenshots/                  # Digital twin and UI dashboard captures
│
├── tools/                            # Developer Tooling and Automation Scripts
│   ├── generate_diagrams.py          # Python matplotlib diagram generator
│   └── generate_pdf.py               # ReportLab PDF schematic compiler
│
└── scripts/                          # Cloudflare and Network Utilities
    ├── tunnel_start.sh               # Cloudflare Tunnel public URL generator
    ├── tunnel_status.sh              # Tunnel status inspector
    └── tunnel_stop.sh                # Tunnel termination script
```
