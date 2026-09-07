# Automated Low-Cost In-Wall Microcontroller Switch
## Complete Technical Specification & System Architecture Document
**Project Group:** ZLATANFC (KICT & KOE, International Islamic University Malaysia)  
**Target SDGs:** SDG 7 (Affordable and Clean Energy) & SDG 9 (Industry, Innovation & Infrastructure)  
**Deployment Target:** Institutional Retrofit (International Islamic University Malaysia, KICT & KOE)  
**Reference Room:** E1-2-14 (Level 2, Block E1)  
**System Status:** Operational / Verified with Hardware-in-the-Loop Test Suites  

---

## Table of Contents
1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [High-Level Architecture & Block Diagram](#2-high-level-architecture--block-diagram)
3. [Hardware Specification & Pinout Mapping](#3-hardware-specification--pinout-mapping)
4. [Firmware Engine & State Machine (`smart_switch.ino`)](#4-firmware-engine--state-machine-smart_switchino)
5. [Intelligent Manual Override & Schedule Arbitration](#5-intelligent-manual-override--schedule-arbitration)
6. [Physical Switch Interaction Matrix (UX Design)](#6-physical-switch-interaction-matrix-ux-design)
7. [Edge Gateway & Software Stack (`web/`)](#7-edge-gateway--software-stack-web)
8. [Data Models & Timetable Persistence](#8-data-models--timetable-persistence)
9. [Energy Economics & Load Calculation](#9-energy-economics--load-calculation)
10. [Demonstration & Evaluation Runbook](#10-demonstration--evaluation-runbook)
11. [Automated Verification & Test Suites](#11-automated-verification--test-suites)

---

## 1. Executive Summary & Problem Statement

### 1.1 The Challenge
Modern academic institutions waste substantial electrical energy due to unoccupied classrooms running lighting and HVAC (Heating, Ventilation, and Air Conditioning) systems continuously outside of scheduled lecture hours. Traditional Building Management Systems (BMS) suffer from three critical bottlenecks:
1. **Prohibitive Capital Cost:** Industrial BACnet/Modbus installations cost thousands of dollars per room, requiring invasive rewiring.
2. **Central Network Vulnerability:** Pure cloud or centralized architectures lock occupants out of basic appliance control when local campus Wi-Fi or central servers suffer outages.
3. **Inflexible Manual Wall Switches:** Conventional manual wall toggles lack scheduled turn-off, leading to appliances being left on overnight or through weekends.

### 1.2 The Solution
The **Automated Low-Cost In-Wall Microcontroller Switch** solves these challenges by combining:
* An **ultra-low-cost edge microcontroller (Arduino Uno / ATmega328P)** retrofittable directly into standard wall-box infrastructure for under $15 in component cost.
* **On-device autonomous intelligence:** Permanent EEPROM timetable storage and real-time state arbitration, allowing 100% standalone operation without continuous computer tethering.
* **Intelligent manual override mechanics:** Eliminates occupant frustration via early-dismissal latching, ad-hoc 60-minute auto-off timers, and presentation slide mode.
* **Plug-and-play Edge Gateway:** A local Web dashboard (FastAPI + WebSockets) simulating a Raspberry Pi edge coordinator, providing live telemetry, i-Ma'luum portal timetable synchronization, and emergency remote control.

---

## 2. High-Level Architecture & Block Diagram

```
                              ┌────────────────────────────────────────────────────────┐
                              │           Central Campus ERP / i-Ma'luum               │
                              │           Academic Timetable Database                  │
                              └───────────────────────────┬────────────────────────────┘
                                                          │ HTTP REST / JSON
                                                          ▼
                              ┌────────────────────────────────────────────────────────┐
                              │            Edge Gateway (Raspberry Pi / Laptop)        │
                              │  ├── FastAPI REST & Telemetry Server (Port 8000)       │
                              │  ├── SQLite Engine (timetable.db: Rooms, Rules, Logs)  │
                              │  ├── WebSocket Server (10 Hz Live Digital Twin)        │
                              │  └── Serial Bridge Worker Thread                       │
                              └───────────────────────────┬────────────────────────────┘
                                                          │ Full-Duplex USB Serial
                                                          │ (/dev/ttyACM0 @ 9600 baud)
                                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       Automated In-Wall Switch (Arduino Uno R3)                                       │
│                                                                                                                        │
│  ┌───────────────────────────┐     ┌──────────────────────────────────────────────────┐     ┌───────────────────────┐  │
│  │   Physical User Inputs    │     │                 ATmega328P Core                  │     │  Actuators & Displays │  │
│  │                           │     │                                                  │     │                       │  │
│  │ 🔘 Button 1 (Pin 10):     │────>│ • Non-Blocking Cooperative Scheduler             │────>│ 🟡 Yellow LED (Pin 13)│  │
│  │    Manual Override        │     │ • 7-Day Academic Timetable Engine                │     │    Classroom Lights   │  │
│  │                           │     │ • 4-State Override & Boundary Arbitrator         │     │                       │  │
│  │ 🔘 Button 2 (Pin 9):      │────>│ • EEPROM Permanent Configuration Storage         │────>│ 🔵 Blue LED (Pin 12)  │  │
│  │    Speed / Clock Accel    │     │ • Watch-Style Progressive Acceleration Engine    │     │    Air Conditioner    │  │
│  │                           │     │ • Alphanumeric Splash & Audio Tone Synthesizer   │     │                       │  │
│  │ 🔘 Button 3 (Pin 2):      │────>│                                                  │────>│ 🔴 Red LED (Pin 11)   │  │
│  │    Day Switch / Peek      │     └──────────────────────────┬───────────────────────┘     │    Standby Indicator  │  │
│  └───────────────────────────┘                                │                             │                       │  │
│                                                               │ Shift Reg (Pins 6, 7, 8)    │ 🔊 Piezo (Pin 3)      │  │
│                                                               │ Cathodes (Pins A0-A3)       │    Audio Feedback     │  │
│                                                               ▼                             └───────────────────────┘  │
│                                              ┌─────────────────────────────────┐                                       │
│                                              │ 4-Digit 7-Segment Clock (5641AS)│                                       │
│                                              │ Displays HH:MM, Day, & Splashes │                                       │
│                                              └─────────────────────────────────┘                                       │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Hardware Specification & Pinout Mapping

### 3.1 Bill of Materials (BOM)

| Component | Part / IC | Description | Quantity |
| :--- | :--- | :--- | :--- |
| **Microcontroller** | Arduino Uno R3 | Microchip ATmega328P (16 MHz, 5V, 32KB Flash, 2KB SRAM, 1KB EEPROM) | 1 |
| **Shift Register** | 74HC595 | 8-Bit Serial-In, Parallel-Out Shift Register (DIP-16) for segment lines A–G + DP | 1 |
| **Digital Display** | 5641AS / 5643AS | 4-Digit 7-Segment Common Cathode LED Display (0.56") with center colon | 1 |
| **Lighting Actuator** | 5mm Diffused Yellow LED | Models classroom fluorescent / LED luminaire circuit | 1 |
| **HVAC Actuator** | 5mm Diffused Blue LED | Models split-unit or chilled-water Air Conditioning contactor | 1 |
| **Standby Actuator** | 5mm Diffused Red LED | Indicates idle standby mode and grace period countdown | 1 |
| **Acoustic Transducer**| Passive Piezo Buzzer | 5V Piezoelectric sounder for tone and audio alert generation | 1 |
| **Tactile Switches** | 6x6mm Momentary Push | Wall switch toggle (Btn 1), clock accelerator (Btn 2), day selector (Btn 3) | 3 |
| **Current Limiters** | 220 $\Omega$ Resistors | LED & segment current limiting (protects ATmega328P GPIO from overcurrent)| 11 |
| **Pull-Up Resistors** | Internal Pull-ups | ATmega328P 20k–50k $\Omega$ software internal pull-ups activated on input pins | 3 |
| **Dual Power Source** | 9V DC Battery & Barrel | 9V PP3 alkaline battery with 2.1mm center-positive barrel connector for untethered mobility | 1 |

### 3.2 Complete Arduino Pinout Table

| Arduino Pin | Breadboard Row | Component / Connection | Hardware Role & Signal Specification |
| :--- | :--- | :--- | :--- |
| **GND** | Blue `(-)` Rail | Common Ground | System signal & power ground return |
| **5V** | Red `(+)` Rail | 5V Power Supply Rail | VCC for 74HC595 (Pin 16) and breadboard power |
| **Pin 2** | Row `16j` | 🔘 **Button 3 (Day Switch)** | Active-LOW input (`INPUT_PULLUP`). Tap to Peek active day, Hold 600ms to advance day once. |
| **Pin 3** | Row `21j` | 🔊 **Piezo Buzzer** | PWM output driven by `tone()` / `noTone()`. Frequencies: 800 Hz – 3800 Hz. |
| **Pin 6** | Row `38j` | 74HC595 Pin 11 (`SH_CP`) | Shift Register Clock. Triggers byte bit shift on rising edge. |
| **Pin 7** | Row `37j` | 74HC595 Pin 12 (`ST_CP`) | Shift Register Storage / Latch Clock. Updates parallel output registers. |
| **Pin 8** | Row `35j` | 74HC595 Pin 14 (`DS`) | Serial Data Input. Transmits active-HIGH segment bitmasks. |
| **Pin 9** | Row `24a` | 🔘 **Button 2 (Clock Accel)** | Active-LOW input (`INPUT_PULLUP`). Progressive digital watch style fast-forward. |
| **Pin 10** | Row `19a` | 🔘 **Button 1 (Manual Switch)**| Active-LOW input (`INPUT_PULLUP`). Wall toggle: Tap switches modes; Hold 1.2s toggles Presentation. |
| **Pin 11** | Row `13a` | 🔴 **Red LED (Standby/Status)**| Output via 220 $\Omega$ resistor. Solid ON in Standby; 2 Hz flashing during Grace Period. |
| **Pin 12** | Row `8a` | 🔵 **Blue LED (Air Conditioner)**| Output via 220 $\Omega$ resistor. ON during Pre-cooling, Class Active, and Presentation modes. |
| **Pin 13** | Row `3a` | 🟡 **Yellow LED (Lights)** | Output via 220 $\Omega$ resistor. ON during Class Active mode; forced OFF in Presentation mode. |
| **Pin A0** | Row `55c` | Display Digit 1 (`DIG1`) | Active-LOW Common Cathode driver for Tens of Hours digit. |
| **Pin A1** | Row `52c` | Display Digit 2 (`DIG2`) | Active-LOW Common Cathode driver for Hours digit + Center Colon. |
| **Pin A2** | Row `51c` | Display Digit 3 (`DIG3`) | Active-LOW Common Cathode driver for Tens of Minutes digit. |
| **Pin A3** | Row `50i` | Display Digit 4 (`DIG4`) | Active-LOW Common Cathode driver for Minutes digit. |

---

## 4. Firmware Engine & State Machine (`smart_switch.ino`)

The firmware operates as a non-blocking cooperative execution loop without any `delay()` calls, ensuring multiplexing stability, debounced button responsiveness, and real-time serial telemetry processing.

### 4.1 System States

```
                ┌────────────────────────────────────────────────────────┐
                │                     STATE_STANDBY                      │
                │     Off-hours: Lights OFF, AC OFF, Red LED Solid ON    │
                └───────────────────────────┬────────────────────────────┘
                                            │ Current Time reaches (Class Start - PreCool)
                                            ▼
                ┌────────────────────────────────────────────────────────┐
                │                     STATE_PRECOOL                      │
                │    10 min pre-cool: Lights OFF, AC ON, Red LED OFF     │
                └───────────────────────────┬────────────────────────────┘
                                            │ Current Time reaches Class Start Time
                                            ▼
                ┌────────────────────────────────────────────────────────┐
                │                  STATE_CLASS_ACTIVE                    │
                │     Lecture in session: Lights ON, AC ON, Red LED OFF  │
                └───────────────────────────┬────────────────────────────┘
                                            │ Current Time reaches Class End Time
                                            ▼
                ┌────────────────────────────────────────────────────────┐
                │                  STATE_GRACE_PERIOD                    │
                │  10 min vacate warning: Lights ON, AC ON, Red Blinking │
                └───────────────────────────┬────────────────────────────┘
                                            │ Grace window expires
                                            ▼
                               [ Return to STATE_STANDBY ]
```

### 4.2 Display Multiplexing & Alphanumeric Splash Engine
The 4-digit 7-segment display is driven via persistence of vision (POV) at **250 Hz (1 ms per digit multiplex cycle)**:
* Each digit is enabled sequentially via its cathode pin (`A0`–`A3` pulled LOW) while the 74HC595 outputs the segment pattern.
* **Center Colon Handling:** Driven via the Decimal Point (DP) pin of Digit 2, synchronized to blink at exactly 1 Hz (`currentSecond % 2 == 0`).
* **Alphanumeric Character Generator:** Supports full decimal numbers (`0`–`9`) as well as dedicated mode splash banners:
  * `AUto` (`PAT_AUTO`): Displayed upon returning to automatic schedule mode.
  * `F-On` (`PAT_FON`): Displayed upon manual force ON (+60 min ad-hoc run).
  * `F-OF` (`PAT_FOFF`): Displayed upon manual early dismissal force OFF.
  * `PrES` (`PAT_PRES`): Displayed upon engaging Presentation projector mode.
  * `dAY1` to `dAY7` (`PAT_DAY`): Splashed during day peeking, day switching, and midnight rollover.

### 4.3 Progressive Acceleration Engine (Digital Watch Style)
Holding Button 2 (Pin 9) advances simulated time progressively through 4 distinct speed tiers:
* **Initial Tap:** Immediate `+1 minute` bump with a 2800 Hz tap pip.
* **Tier 1 (0 – 1.5s hold):** `+1 minute` every 160 ms (~6 min/sec).
* **Tier 2 (1.5s – 3.2s hold):** `+2 minutes` every 100 ms (~20 min/sec) with a 2800 Hz transition chime.
* **Tier 3 (3.2s – 5.5s hold):** `+5 minutes` every 75 ms (~66 min/sec) with a 3300 Hz transition chime.
* **Tier 4 (> 5.5s hold):** `+15 minutes` every 50 ms (~300 min/sec / 5 hours per sec!) with a 3800 Hz warp chime.
* **Smooth Release:** Upon button release, the clock seamlessly resumes normal ticking from the reached time, accompanied by a 2200 Hz release confirmation chime.

---

## 5. Intelligent Manual Override & Schedule Arbitration

The system features an autonomous arbitration engine that resolves conflicts between manual wall actions and scheduled timetable sessions.

### 5.1 Override Modes

| Mode Enum | Constant | Description | Actuator Behavior |
| :--- | :---: | :--- | :--- |
| `OVERRIDE_AUTO` | `0` | **Strict Timetable Adherence.** Microcontroller evaluates underlying class schedule. | Determined by `STATE_STANDBY`, `PRECOOL`, `CLASS_ACTIVE`, or `GRACE`. |
| `OVERRIDE_FORCE_ON` | `1` | **Ad-Hoc Room Usage.** Forced ON outside scheduled hours with a 60-min auto-off countdown. | Yellow (Lights) ON, Blue (AC) ON, Red LED pulsing warning. |
| `OVERRIDE_FORCE_OFF` | `2` | **Early Class Dismissal.** Lecturer turns off switch early; room remains locked OFF until session finishes. | Yellow OFF, Blue OFF, Red LED slow 1 Hz pulse. |
| `OVERRIDE_PRESENTATION`| `3`| **Slide Projector Mode.** Engaged during class for slide presentations. | Yellow (Lights) OFF, Blue (AC) ON, Red LED OFF. |

### 5.2 Symmetrical Two-Stroke Toggle Mechanics

Any press of the manual switch while an override is active always executes **`engageAuto()`**:

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 OVERRIDE_AUTO (Normal)                 │
                  └───────────────┬────────────────────────┬───────────────┘
                                  │                        │
               Tap during Standby │                        │ Tap during Class
                                  ▼                        ▼
     ┌──────────────────────────────────────┐    ┌──────────────────────────────────────┐
     │          OVERRIDE_FORCE_ON           │    │          OVERRIDE_FORCE_OFF          │
     │      (Ad-Hoc 60-min Countdown)       │    │       (Early Class Dismissal)        │
     └──────────────────┬───────────────────┘    └──────────────────┬───────────────────┘
                        │                                           │
                        │ Tap again                                 │ Tap again
                        └───────────────────►◄──────────────────────┘
                                      Returns to AUTO
                                 (Appliance follows schedule)
```

1. **During Scheduled OFF (Standby) $\rightarrow$ Tap ON $\rightarrow$ Tap OFF:**
   * **Tap 1:** Engages `FORCE_ON` (Lights ON, AC ON, 60-min timer starts, display splashes `F-On`).
   * **Tap 2:** Cancels countdown, returns to `AUTO`. Timetable is checked $\rightarrow$ since it is off-hours, appliances immediately shut down to Standby (`0 W` load, display splashes `AUto`).
2. **During Scheduled ON (Class) $\rightarrow$ Tap OFF $\rightarrow$ Tap ON:**
   * **Tap 1:** Engages `FORCE_OFF` (Lights OFF, AC OFF, display splashes `F-OF`). Appliance remains locked off until class ends.
   * **Tap 2:** Clears dismissal lock, returns to `AUTO`. Timetable is checked $\rightarrow$ since class is still in progress, appliances immediately re-energize (display splashes `AUto`).

### 5.3 Automated Boundary Re-Synchronization
* **Early Dismissal Expiration:** When `currentTotalMin >= forceOffUntilMin` (class and grace period finish), the system automatically drops `OVERRIDE_FORCE_OFF` and returns to `AUTO` (`STANDBY`). Subsequent scheduled classes turn on and pre-cool normally.
* **Ad-Hoc Absorption:** If an ad-hoc `FORCE_ON` is running and the clock enters a scheduled pre-cooling or class period, the system automatically absorbs the session into the timetable, clearing the countdown without cutting power.
* **Pre-Shutdown Warning Beeps:** During the final 5 minutes of an ad-hoc `FORCE_ON`, the piezo sounder emits warning beeps at the 5, 4, 3, 2, and 1-minute marks, followed by rapid beeps in the final 10 seconds before auto-shutdown.
* **Midnight Rollover Failsafe (`00:00:00`):** Every midnight, all active overrides and timers are purged, resetting the system to `OVERRIDE_AUTO` on the new day.

---

## 6. Physical Switch Interaction Matrix (UX Design)

| Hardware Control | Input Action | Duration Threshold | Acoustic Feedback | Visual Display | Firmware State Transition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Button 3 (Pin 2)<br>Day Switch** | **Short Tap** | `< 600 ms` | Soft Chirp (`2400 Hz, 25ms`) | Displays `dAY1`..`dAY7` for 1.5s | **Peeks current day.** Does NOT mutate day index. |
| **Button 3 (Pin 2)<br>Day Switch** | **Hold** | `>= 600 ms` | Confirmation Chime (`3000 Hz, 60ms`) | Displays new day banner | **Advances day by +1 ONCE.** Latches until release. |
| **Button 1 (Pin 10)<br>Wall Switch** | **Short Tap** (in Standby) | `< 1200 ms` | Energetic Chime (`2600 Hz, 60ms`) | Splashes `F-On` for 1.5s | Engages `OVERRIDE_FORCE_ON` (60 min timer). |
| **Button 1 (Pin 10)<br>Wall Switch** | **Short Tap** (in Class) | `< 1200 ms` | Low Tone (`1600 Hz, 60ms`) | Splashes `F-OF` for 1.5s | Engages `OVERRIDE_FORCE_OFF` until class ends. |
| **Button 1 (Pin 10)<br>Wall Switch** | **Short Tap** (in Override) | `< 1200 ms` | Reset Chime (`2000 Hz, 40ms`) | Splashes `AUto` for 1.5s | Returns immediately to `OVERRIDE_AUTO`. |
| **Button 1 (Pin 10)<br>Wall Switch** | **Hold** | `>= 1200 ms` | Projector Tone (`2700 Hz, 80ms`) | Splashes `PrES` for 1.5s | Toggles `OVERRIDE_PRESENTATION` (Lights OFF, AC ON). |
| **Button 2 (Pin 9)<br>Clock Accel** | **Short Tap** | Instant | Tap Pip (`2800 Hz, 25ms`) | Digit bumps +1 min | Steps clock forward by `+1 minute`. |
| **Button 2 (Pin 9)<br>Clock Accel** | **Continuous Hold** | `> 0 ms` | Multi-tier harmonic tones | High-speed clock race | Progressive acceleration (up to 300 min/sec). |

---

## 7. Edge Gateway & Software Stack (`web/`)

The edge gateway software is written in modern Python (FastAPI + AsyncIO + PySerial) designed to run as a native `systemd` service on a Raspberry Pi or local building controller.

```
automated-in-wall-switch/
├── README.md                         # Main engineering overview & evaluation hub
├── flash.sh                          # One-command Arduino firmware flashing
├── run_web.sh                        # FastAPI Web Gateway & Cloud tunnel launcher
├── run_gui.sh                        # CustomTkinter Desktop GUI launcher
│
├── smart_switch/                     # Embedded Arduino C++ Firmware
│   └── smart_switch.ino              # Autonomous EEPROM engine, multiplexing & state machine
│
├── web/                              # Edge Gateway & Digital Twin Web Application
│   ├── server.py                     # FastAPI REST API & WebSocket telemetry hub
│   ├── serial_bridge.py              # Thread-safe USB Serial CDC communication bridge
│   ├── database.py                   # SQLite persistence layer & audit logger
│   ├── timetable.db                  # Pre-seeded IIUM academic timetable & policies
│   └── static/                       # Industrial Brutalist frontend (HTML/CSS/JS)
│
├── desktop/                          # Alternative Desktop Interface
│   └── switch_gui.py                 # CustomTkinter desktop monitor & timetable manager
│
├── docs/                             # Full Engineering & Academic Specifications
│   ├── SYSTEM_SPECIFICATION.md       # High-level architecture, circuit math & telemetry
│   ├── PRODUCTION_SPECIFICATION.md   # Commercial dual-relay, PCB & MOV snubber specifications
│   ├── DEMO_SPECIFICATION.md         # Breadboard prototype build & pinout mapping
│   ├── DEMO_OVERVIEW.md              # Live demonstration quick-reference
│   ├── DEMO_PRESETS_GUIDE.md         # Evaluator scenario presets & presentation scripts
│   ├── SMART_SWITCH_EXECUTIVE_GUIDE.md # SDG alignment & executive summary
│   └── circuit_diagrams.pdf         # 4-page full engineering schematic PDF
│
├── assets/                           # Schematics & Visual Artifacts
│   ├── diagrams/                     # Architecture & bench schematics (PNG)
│   └── screenshots/                  # Digital twin & UI dashboard captures
│
├── tools/                            # Developer Tooling & PDF/Schematic Compilers
│   ├── generate_diagrams.py          # Python matplotlib diagram generator
│   └── generate_pdf.py               # ReportLab PDF schematic compiler
│
└── scripts/                          # Cloudflare & Network Utilities
    ├── tunnel_start.sh
    ├── tunnel_status.sh
    └── tunnel_stop.sh
```

### 7.1 Serial Bridge Protocol (`web/serial_bridge.py`)
Communication occurs across USB Serial at `9600 baud, 8-N-1`:

* **Inbound Telemetry Packet (Arduino $\rightarrow$ Gateway, sent every 1000 ms or on change):**
  ```
  TLM:<HH:MM:SS>,<STATE>,<YELLOW>,<BLUE>,<RED>,<OVERRIDE_CODE>,<SPEED_FACTOR>,<DAY_STR>,<TIMER_REMAINING_MIN>
  ```
  *Example:* `TLM:09:15:00,CLASS,1,1,0,0,1,MON,0` (Monday 09:15:00, Class Active, Lights ON, AC ON, Standby OFF, AUTO mode, 1X speed, 0 timer).
  *Example:* `TLM:20:30:12,FORCE_ON,1,1,0,1,1,FRI,45` (Friday 20:30:12, Force ON, Lights ON, AC ON, 45 minutes remaining).

* **Outbound Gateway Commands (Gateway $\rightarrow$ Arduino):**
  * `SYNC:<HH>:<MM>:<SS>`: Synchronizes hardware clock to edge server time.
  * `SET_DAY:<MON|TUE|WED|THU|FRI|SAT|SUN>`: Sets current operating day.
  * `SET_SCHED:<sH1>:<sM1>:<eH1>:<eM1>:<sH2>:<sM2>:<eH2>:<eM2>:<precool>:<grace>`: Flashes active schedule into EEPROM.
  * `FORCE_ON:<minutes>`: Commands ad-hoc run with specific countdown timer.
  * `FORCE_OFF`: Commands early dismissal shutdown.
  * `PRESENTATION`: Commands projector mode (Lights OFF, AC ON).
  * `AUTO_MODE`: Commands return to timetable schedule.
  * `SET_SPEED:<1|60|600>`: Sets software simulation multiplier.
  * `BEEP:<freq>:<duration_ms>`: Remotely triggers hardware piezo sounder.

---

## 8. Data Models & Timetable Persistence

The database schema (`web/timetable.db`) supports multi-room academic environments organized around university course timing blocks.

### 8.1 SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    building TEXT NOT NULL,
    level INTEGER NOT NULL,
    room TEXT NOT NULL,
    label TEXT NOT NULL,
    day_of_week INTEGER NOT NULL, -- 0=Mon, 1=Tue, ..., 6=Sun
    start_hour INTEGER NOT NULL,
    start_minute INTEGER NOT NULL,
    end_hour INTEGER NOT NULL,
    end_minute INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    precool_minutes INTEGER DEFAULT 10,
    grace_minutes INTEGER DEFAULT 10,
    speed_factor INTEGER DEFAULT 1,
    last_deployed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    details TEXT
);
```

### 8.2 IIUM Academic Period Definitions
The backend implements native mapping for official IIUM academic course blocks:
* **Period 1 (P1):** 08:30 – 10:00
* **Period 2 (P2):** 10:00 – 11:30
* **Period 3 (P3):** 11:30 – 13:00
* **Period 4 (P4):** 14:00 – 15:30
* **Period 5 (P5):** 15:30 – 17:00

When classes are synced from the i-Ma'luum portal or configured via the matrix UI, morning courses (< 13:00) are merged into Morning Slot 1, and afternoon courses (>= 13:00) into Afternoon Slot 2, deploying cleanly to the Arduino's dual-window daily EEPROM slots.

---

## 9. Energy Economics & Load Calculation

The system calculates real-time electrical demand and simulated operational savings based on typical institutional classroom equipment:

### 9.1 Electrical Load Ratings
* **Classroom Lighting Circuit (Yellow LED):** Standard 12-luminaire fluorescent / LED troffer array $\approx$ **480 Watts (2.0 Amps @ 240V AC)**.
* **Classroom Air Conditioning Unit (Blue LED):** Commercial 2.5 HP split inverter unit $\approx$ **2,200 Watts (9.17 Amps @ 240V AC)**.
* **Microcontroller Switch Quiescent Draw (Standby Red LED):** Logic circuit + LED $\approx$ **0.5 Watts (0.002 Amps @ 240V AC)**.

### 9.2 Financial & Carbon Impact Calculation
Assuming a typical Malaysian commercial tariff (**RM 0.365 / kWh**):
* **Full Room Load (Lights + AC):** $2,680\text{ W} = 2.68\text{ kW}$. Hourly running cost: **RM 0.98 / hour**.
* **Unattended Waste (Before Automation):** Lecture halls left on for an average of 4.5 unattended hours per day $\rightarrow$ $12.06\text{ kWh/day} \approx \text{RM } 4.40\text{/day}$ or **RM 1,320 / room / year**.
* **Savings with Automated In-Wall Switch:** Autonomous shutoff, 10-minute pre-cooling restriction, and early dismissal auto-resync eliminate over **85% of idle consumption**, saving **~RM 1,120 and 1.8 metric tonnes of $\text{CO}_2$ per classroom annually**.

---

## 10. Demonstration & Evaluation Runbook

For live bench presentation to university evaluators or technical examiners:

### Phase 1: Tethered Edge Gateway Demonstration
1. Launch the web gateway daemon:
   ```bash
   ./run_web.sh
   ```
2. Open browser to `http://localhost:8000`.
3. Demonstrate live telemetry:
   * Click **`SYNC HOST TIME`** $\rightarrow$ Observe hardware clock and digital twin synchronize immediately.
   * Click **`TEST BEEPER [PIN 3]`** $\rightarrow$ Hear physical 2200 Hz verification tone from the breadboard.
   * Click **`FORCE ON [+60M]`** $\rightarrow$ Watch Yellow and Blue LEDs ignite, display splashes `F-On`, load jumps to 2680 W.
   * Click **`PRESENTATION`** $\rightarrow$ Watch Yellow LED extinguish (projector mode) while Blue LED (AC) stays on; display splashes `PrES`.
   * Click **`AUTO SCHEDULE`** $\rightarrow$ Watch system return smoothly to scheduled state; display splashes `AUto`.

### Phase 2: Autonomous Untethered Hand-Off (SDG 9 Proof)
1. Plug the **9V Battery clip** into the round black **DC Barrel Jack** of the Arduino Uno.
   *(The onboard auto-selector switches to battery power seamlessly without reboot).*
2. **Unplug the USB cable from the laptop.**
   *(The 4-digit clock continues ticking and the LEDs maintain their exact state).*
3. Carry the breadboard over to the evaluators:
   * **Test Day Switch (Button 3):**
     * **Tap:** Observe display splash `dAY1` (peeks active day without advancing).
     * **Hold for 600ms:** Hear 3000 Hz confirmation chime and observe display step to `dAY2` (advances once and stops).
   * **Test Clock Acceleration (Button 2):**
     * Hold Button 2 to race the clock into the next class.
     * At 10 mins before class: Blue LED ignites (`PRECOOL`).
     * At class start time: Yellow LED ignites (`CLASS ACTIVE`).
     * At class finish: Red LED blinks (`GRACE PERIOD`).
     * At grace finish: System shuts down automatically into `STANDBY`.
   * **Test Manual Wall Switch (Button 1):**
     * Tap during class: Early dismissal `FORCE_OFF` activates.
     * Tap again: Instantly restores `AUTO` class operation.
     * Hold for 1.2s: Engages Presentation projector mode (`PrES`).

---

## 11. Automated Verification & Test Suites

The codebase includes two automated end-to-end Python test suites that validate all serial protocols, boundary transitions, and timing constraints against the physical hardware.

### 11.1 Running Test Suites
```bash
# Test 1: Intelligent Manual Override & Boundary Re-Sync Suite
python3 scratch/test_override_and_day_ux.py

# Test 2: Full System Integration & Telemetry Suite
python3 scratch/test_demo_e2e.py
```

### 11.2 Verification Matrix

| Test Suite | Subtest Scenario | Verified Behavior | Exit Result |
| :--- | :--- | :--- | :---: |
| `test_override_and_day_ux.py` | Step 1: Monday Standby Init | Room sits in scheduled `STANDBY`, `override_mode=0`, load=0W | **PASS** |
| `test_override_and_day_ux.py` | Step 2: Ad-Hoc `FORCE_ON` | Utilities ignite, 60m countdown active, `override_mode=1` | **PASS** |
| `test_override_and_day_ux.py` | Step 3: Presentation Mode | Yellow LED turns OFF, Blue LED remains ON, `override_mode=3` | **PASS** |
| `test_override_and_day_ux.py` | Step 4: Return to `AUTO` | Returns to schedule, restores `STANDBY`, `override_mode=0` | **PASS** |
| `test_override_and_day_ux.py` | Step 5: Early Dismissal & Boundary Re-sync | Forces OFF during class; auto-reverts to `AUTO` at boundary; subsequent class `PRECOOL` fires on time | **PASS** |
| `test_override_and_day_ux.py` | Step 6: Ad-Hoc Timer Expiry | Advance past 30m countdown; shuts utilities off to `STANDBY` | **PASS** |
| `test_demo_e2e.py` | Hardware Status & Port | Verified `/dev/ttyACM0` connection and telemetry heartbeat | **PASS** |
| `test_demo_e2e.py` | EEPROM Batch Deployment | Deployed 8 multi-day schedule packets into EEPROM memory | **PASS** |
| `test_demo_e2e.py` | Day Jumps | Verified hardware day transitions (`MON` $\rightarrow$ `TUE` $\rightarrow$ `WED`) | **PASS** |
| `test_demo_e2e.py` | State Simulation Jumps | Verified `PRECOOL`, `CLASS`, `GRACE`, and `STANDBY` transitions | **PASS** |
| `test_demo_e2e.py` | Beeper Sounder | Verified frequency tone dispatch on Pin 3 | **PASS** |
| `test_demo_e2e.py` | Timetable Matrix CRUD | Verified slot toggling (vacant $\leftrightarrow$ occupied) idempotence | **PASS** |
| `test_demo_e2e.py` | Audit Logging | Verified SQLite audit trail tracking across all actions | **PASS** |
