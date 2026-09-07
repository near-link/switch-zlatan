# Automated In-Wall Microcontroller Switch
## System Summary: Demo Prototype, Demo vs. Production, & Session Log

---

## 1. The Demo Unit (Hardware & Firmware Architecture)

The demonstration kit is an evaluation proof-of-concept (POC) that simulates an institutional classroom energy management controller on a portable breadboard.

```
                           ┌───────────────────────────┐
                           │      Arduino Uno R3       │
                           │       (ATmega328P)        │
                           └─────────────┬─────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
  [ Physical Inputs ]            [ Display Engine ]             [ Actuators & Audio ]
  🔘 Btn 1 (Pin 10): Override    📟 4-Digit Clock (5641AS)      🟡 Pin 13: Lights LED
  🔘 Btn 2 (Pin 9):  Fast-Fwd    ├── 74HC595 (Pins 6, 7, 8)     🔵 Pin 12: AC Unit LED
  🔘 Btn 3 (Pin 2):  Day Select  └── Cathodes (Pins A0-A3)      🔴 Pin 11: Standby LED
                                                                🔊 Pin 3:  Piezo Buzzer
```

### 1.1 Physical Control Interfaces & UX
* **Button 1 (Pin 10) — Manual Wall Switch Override:**
  * **Short Tap (`< 1.2s`):** Symmetrical two-stroke toggle:
    * In **Standby (Off-Hours):** Engages `FORCE_ON` (Lights ON, AC ON) with a **60-minute auto-off countdown** (splashes `F-On`).
    * In **Class (In-Session):** Engages `FORCE_OFF` for **early dismissal** (splashes `F-OF`). Room stays locked off until the scheduled session + grace period ends.
    * When **any override is active:** Cancels the override and immediately **returns to `AUTO` schedule** (splashes `AUto`).
  * **Hold (`>= 1.2s`):** Toggles **Presentation Mode** (splashes `PrES`). Extinguishes lighting for projector slide visibility while keeping AC running.
* **Button 2 (Pin 9) — Digital Watch Fast-Forward:**
  * Allows evaluators to observe hours of scheduled transitions in seconds without waiting in real time.
  * 4-tier progressive acceleration:
    * Tap: `+1 minute` bump.
    * Hold 0–1.5s: `+1 min` every 160ms.
    * Hold 1.5–3.2s: `+2 min` every 100ms (2800 Hz gear-shift chime).
    * Hold 3.2–5.5s: `+5 min` every 75ms (3300 Hz chime).
    * Hold > 5.5s: `+15 min` every 50ms (3800 Hz warp chime $\approx$ 5 hours/second!).
* **Button 3 (Pin 2) — Day Selector Switch:**
  * **Tap (`< 600ms`):** **Tap-to-Peek.** Splashes current day banner (`dAY1` to `dAY7`) for 1.5s with a soft chirp (`2400 Hz`). **Does not alter the day.**
  * **Hold (`>= 600ms`):** **Hold-to-Advance Once.** Advances day by `+1` with a loud confirmation chime (`3000 Hz`). **Latches immediately** so it only steps once per physical press and never auto-scrolls.

### 1.2 Display & Actuators
* **4-Digit 7-Segment Display (5641AS via 74HC595):** 250 Hz persistence-of-vision multiplexing. Shows `HH:MM` with a 1 Hz blinking colon, as well as temporary alphanumeric splash banners (`AUto`, `F-On`, `F-OF`, `PrES`, `dAY1`–`dAY7`).
* **Yellow LED (Pin 13):** Classroom lighting circuit (480 W equivalent load).
* **Blue LED (Pin 12):** Air conditioning circuit (2200 W equivalent load).
* **Red LED (Pin 11):** Standby indicator (solid during off-hours; 2 Hz flashing during 10-minute post-class grace period).
* **Piezo Buzzer (Pin 3):** Acoustic feedback for button taps, state transitions, day increments, and a 5-minute pre-shutdown warning countdown before ad-hoc auto-off.
* **Dual Power Architecture:** Runs tethered via laptop USB, or untethered via a **9V battery plugged into the DC barrel jack** for handheld demonstrations to judges.

---

## 2. Demo vs. Production Comparison

| Subsystem | Demo Prototype (Current POC) | Commercial / Production Unit |
| :--- | :--- | :--- |
| **Form Factor & Enclosure** | Exposed solderless breadboard + Arduino Uno R3 board. | Custom SMD PCB enclosed inside a standard **British/UK 86×86mm flush in-wall box** behind a decorative faceplate. |
| **Microcontroller / Core** | Microchip ATmega328P (8-bit, 16 MHz, 32KB Flash). | Espressif **ESP32-S3** or **RP2040** (32-bit dual-core, native Wi-Fi/Bluetooth, hardware cryptographic engine). |
| **Power Supply** | USB 5V tether or external 9V alkaline battery into barrel jack. | Integrated miniaturized **isolated 240V AC to 5V DC step-down module** (e.g., Hi-Link HLK-PM01) directly tapping line voltage. |
| **Load Switching (Actuators)**| 5mm LEDs driven directly via ATmega328P GPIO (20 mA). | **Dual 16A / 250V AC Magnetic Latching Relays** or Solid-State Relays (SSRs) with zero-crossing triacs and snubber circuits. |
| **Physical User Interface** | 6mm micro-tactile momentary buttons on breadboard. | Standard architectural momentary rocker/paddle wall switches with micro-travel tactile feel. |
| **Visual Indicator** | 4-digit 0.56" 7-segment display (5641AS). | Flush-mounted **low-power monochrome OLED / E-Paper display** or subtle RGB halo lightguides behind frosted acrylic. |
| **Clock Source** | Software millis() counter + serial host synchronization. | Dedicated ultra-precise **I2C RTC (e.g., DS3231 with CR1220 battery backup)** or automated NTP network time sync. |
| **Clock Acceleration Button**| Dedicated Button 2 for evaluator speedup demonstrations. | **Omitted in production.** (System follows true real-time clock; fast-forward only exists in test/commissioning firmware). |
| **Connectivity & Networking**| Full-duplex USB Serial (`/dev/ttyACM0` @ 9600 baud). | **Wi-Fi 802.11 b/g/n, Zigbee 3.0, or RS-485 Modbus**, integrating into campus BACnet/MQTT BMS infrastructure. |
| **Manufacturing Unit Cost** | ~$25–$35 (off-the-shelf development boards & breakout modules). | **~$8–$14 at production volumes (1,000+ units)** on custom 2-layer FR-4 PCB. |

---

## 3. The Web Stack & Dashboard

The web management system acts as an **Edge Gateway** (simulating a local Raspberry Pi building controller).

```
                      [ Browser Client (Desktop / Smartphone) ]
                                      │
                     HTTP REST / JSON │ WebSocket (10 Hz Live Telemetry)
                                      ▼
                      ┌───────────────────────────────────────┐
                      │        FastAPI Edge Gateway           │
                      │            (Port 8000)                │
                      │                                       │
                      │  ├── server.py (Endpoints & WS Hub)   │
                      │  ├── serial_bridge.py (Serial Worker) │
                      │  └── database.py (SQLite Storage)     │
                      └───────────────────┬───────────────────┘
                                          │ USB Serial (/dev/ttyACM0)
                                          ▼
                             [ Arduino In-Wall Switch ]
```

### 3.1 Core Dashboard Features
1. **Live Glowing Digital Twin:**
   * Real-time visual representation of the classroom's active state (`STANDBY`, `PRECOOL`, `CLASS`, `GRACE`, `FORCE_ON`, `FORCE_OFF`, `PRESENTATION`).
   * Glowing Yellow (Lights), Blue (AC), and Red (Standby) indicators matching physical hardware LEDs.
   * Real-time computed electrical load: **Watts** (0 W – 2680 W) and **Amperes** (0 A – 11.17 A @ 240V).
2. **Interactive 7-Day Timetable Matrix:**
   * Full weekly schedule grid (Monday through Sunday) divided into official IIUM course blocks:
     * **P1:** 08:30 – 10:00
     * **P2:** 10:00 – 11:30
     * **P3:** 11:30 – 13:00
     * **P4:** 14:00 – 15:30
     * **P5:** 15:30 – 17:00
   * **Click-to-Toggle Slots:** Direct interactive matrix where clicking any slot toggles between Vacant and Occupied.
   * **Quick Presets:** Instant loading of Standard Weekday, Full Academic, or Clear schedules.
   * **i-Ma'luum Import Simulation:** Simulates importing live course schedule data for campus rooms across KOE and KICT (e.g. `E1-2-14` and `A-1-02`).
   * **`FLASH EEPROM` Action:** Automatically compiles morning and afternoon operating windows and burns them permanently into the Arduino Uno's EEPROM via serial.
3. **Hardware Control Console:**
   * **4-Mode Arbitration Grid:**
     * `[AUTO SCHEDULE]` — Returns microcontroller to strict timetable adherence.
     * `[FORCE ON (+60M)]` — Forces appliances on with 60-minute countdown timer.
     * `[FORCE OFF]` — Early class dismissal; keeps room off until scheduled session finishes.
     * `[PRESENTATION]` — Slides mode (Lights OFF, AC ON).
   * **Sync Host Time:** Syncs the microcontroller clock to laptop/server system time in 1 click.
   * **Test Beeper [Pin 3]:** Dispatches a test acoustic tone to verify physical transducer function.
   * **Demo Speed Multipliers:** Instant software acceleration buttons (`1X Realtime`, `60X`, `600X`).
   * **Live Diagnostics Feed:** Monospace scrolling terminal showing raw incoming serial telemetry frames.

---

## 4. What Was Done in This Chat Session

### 4.1 Timetable Matrix Synchronization Fix
* **Issue:** Clicking slots in the web timetable matrix occasionally reverted them back to unoccupied before the user had a chance to flash the EEPROM.
* **Root Cause & Resolution:** The frontend polling loop was periodically overwriting local pending edits with stale database snapshots. Decoupled the interactive UI matrix state from background telemetry polling and added instant optimistic updates backed by immediate SQLite synchronization.

### 4.2 Physical Day Switch UX Overhaul
* **Issue:** Button 3 was auto-repeating like the clock acceleration button, causing days to run away on accidental holds.
* **Resolution:** 
  * Implemented **Tap-to-Peek (`< 600ms`)**: Displays current day (`dAY1`–`dAY7`) for 1.5s with a soft chirp (`2400 Hz, 25ms`) without changing the day index.
  * Implemented **Hold-to-Advance-Once (`>= 600ms`)**: Advances the day by `+1` with a loud chime (`3000 Hz, 60ms`) and **latches immediately**, requiring the user to physically release the button before it can step again.

### 4.3 Reversion to Clean `dAY1`–`dAY7` Display Format
* Restored the clean `dAY1` through `dAY7` 7-segment display font mappings (`dAY1`, `dAY2`, `dAY3`, `dAY4`, `dAY5`, `dAY6`, `dAY7`) instead of attempting awkward 4-letter weekday abbreviations on 7-segment digits.

### 4.4 Intelligent Manual Override & Schedule Arbitration Engine
* Replaced naive toggle flags with a robust 4-state engine:
  * **Symmetrical Two-Stroke Toggle:**
    * During Standby: Tap $\rightarrow$ `FORCE_ON` (+60m timer). Tap again $\rightarrow$ `AUTO` (cancels timer, turns off).
    * During Class: Tap $\rightarrow$ `FORCE_OFF` (early dismissal). Tap again $\rightarrow$ `AUTO` (class re-energizes).
  * **Boundary Re-Synchronization:**
    * When an early-dismissed class reaches its scheduled end (+ grace period), the system automatically resets `FORCE_OFF` back to `AUTO` (`STANDBY`), guaranteeing subsequent classes turn on / pre-cool on time.
    * When an ad-hoc `FORCE_ON` runs into a scheduled class, it seamlessly absorbs into the class schedule without interrupting power.
  * **Presentation Mode:** Added slide projector mode (Lights OFF, AC ON) on Button 1 hold (`>= 1.2s`) or web button click.
  * **Countdown Auditory Warnings:** Final 5 minutes emit acoustic beeps at each minute mark and rapid beeps during the final 10 seconds before auto-off.
  * **Midnight Failsafe:** Automatic sweep at `00:00:00` clears all active overrides.

### 4.5 Web UI Active Button Highlighting Fix
* **Issue:** Clicking "Return to Auto" left the manual button highlighted in the web console.
* **Resolution:** Upgraded `setControlModeUI(mode)` in `app.js` to manage a 4-state button group (`btnModeAuto`, `btnModeForceOn`, `btnModeForceOff`, `btnModePres`), ensuring `btn-primary` dynamically and exclusively tracks the active hardware mode.

### 4.6 Verification & Test Suites
* Created and passed **`scratch/test_override_and_day_ux.py` (6/6 tests passed, 100%)**:
  * Standby $\rightarrow$ Force ON $\rightarrow$ Presentation $\rightarrow$ Return to Auto $\rightarrow$ Early Dismissal boundary auto-clearing $\rightarrow$ Ad-hoc timer auto-off.
* Passed **`scratch/test_demo_e2e.py` (9/9 tests passed, 100%)**:
  * Hardware serial telemetry, EEPROM flashing, day jumps, state simulation jumps, buzzer test, timetable CRUD idempotency, and audit logging.
