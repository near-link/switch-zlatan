# Automated Low-Cost In-Wall Microcontroller Switch
## Specification Document: Evaluation Demo Prototype (Proof of Concept)
**Project Team:** ZLATANFC (KICT & KOE, International Islamic University Malaysia)  
**Target SDGs:** SDG 7 (Affordable and Clean Energy) & SDG 9 (Industry, Innovation & Infrastructure)  
**Hardware Target:** Arduino Uno R3 (Microchip ATmega328P, 5V Logic)  
**Reference Room:** E1-2-14 (Kulliyyah of Engineering, IIUM) — KICT & KOE Smart Campus Pilot  
**Document Classification:** Bench Prototype & Evaluation Runbook  

---

## 1. Executive Summary & Demo Objectives

The **Evaluation Demo Prototype** is a portable, fully functional proof-of-concept (POC) designed to demonstrate the feasibility of an automated, low-cost in-wall smart switch for university lecture halls. Built on an Arduino Uno R3 and an educational breadboard, it allows professors, evaluators, and judges to experience:
1. **Automated Timetable Adherence (SDG 7):** Zero-waste off-hours operation with 10-minute air conditioning pre-cooling and post-class grace periods.
2. **Offline Hardware Autonomy (SDG 9):** 100% standalone operation running on internal EEPROM memory with dual-power capability (USB tethered or untethered on a 9V battery).
3. **Progressive Acceleration Engine:** Evaluators can observe hours of scheduled academic operations in seconds via a digital-watch-style fast-forward button.
4. **Intelligent Wall Switch UX:** A physical wall switch interface with symmetrical two-stroke toggling, automatic schedule boundary re-synchronization, and projector presentation mode.

---

## 2. Hardware Architecture & Bill of Materials (BOM)

```
                            ┌───────────────────────────┐
                            │      Arduino Uno R3       │
                            │       (ATmega328P)        │
                            └─────────────┬─────────────┘
                                          │
        ┌─────────────────────────────────┼────────────────────────────────┐
        ▼                                 ▼                                ▼
  [ Physical Inputs ]             [ Display Engine ]             [ Actuators & Audio ]
  🔘 Btn 1 (Pin 10): Override     📟 4-Digit Clock (5641AS)      🟡 Pin 13: Lights LED
  🔘 Btn 2 (Pin 9):  Fast-Fwd     ├── 74HC595 (Pins 6, 7, 8)     🔵 Pin 12: AC Unit LED
  🔘 Btn 3 (Pin 2):  Day Select   └── Cathodes (Pins A0-A3)      🔴 Pin 11: Standby LED
                                                                 🔊 Pin 3:  Piezo Buzzer
```

### 2.1 Complete Bill of Materials

| Component | Specification | Quantity | Role in Demo Prototype |
| :--- | :--- | :---: | :--- |
| **Microcontroller** | Arduino Uno R3 (ATmega328P @ 16 MHz, 5V) | 1 | Executes state machine, schedule evaluation, and serial telemetry |
| **Shift Register** | 74HC595 (8-Bit SIPO DIP-16) | 1 | Drives 7-segment display segments A–G and DP using only 3 MCU pins |
| **Display Module** | 5641AS / 5643AS (0.56" 4-Digit Common Cathode) | 1 | Displays real-time clock `HH:MM`, day banners, and mode splashes |
| **Lighting Actuator**| 5mm Diffused Yellow LED | 1 | Models classroom fluorescent / LED lighting circuit (480 W equivalent) |
| **HVAC Actuator** | 5mm Diffused Blue LED | 1 | Models split-unit air conditioner contactor (2200 W equivalent) |
| **Standby Actuator** | 5mm Diffused Red LED | 1 | Indicates off-hours standby mode and flashes during grace period |
| **Acoustic Transducer**| 5V Passive Piezo Buzzer | 1 | Synthesizes acoustic chirps, gear-shift tones, and shutdown warnings |
| **Tactile Buttons** | 6×6×5mm Momentary Push Switches | 3 | Button 1 (Override), Button 2 (Fast-Forward), Button 3 (Day Switch) |
| **Current Limiters** | 220 $\Omega$ 1/4W Carbon Film Resistors | 11 | Limits current to display segments and LEDs to ~15 mA |
| **Pull-Up Resistors**| ATmega328P Internal Pull-Ups (20k–50k $\Omega$)| 3 | Software-enabled `INPUT_PULLUP` on Pins 2, 9, 10 (eliminates external resistors) |
| **Dual Power Kit** | 9V PP3 Battery + 2.1mm DC Barrel Jack Clip | 1 | Enables seamless untethered mobile demonstrations to evaluators |

### 2.2 Complete Arduino Pinout Table

| Arduino Pin | Breadboard Row | Component / Connection | Hardware Role & Signal Specification |
| :--- | :--- | :--- | :--- |
| **GND** | Blue `(-)` Rail | Common Ground | System signal & power ground return |
| **5V** | Red `(+)` Rail | 5V Power Supply Rail | VCC for 74HC595 (Pin 16) and breadboard power |
| **Pin 2** | Row `16j` | 🔘 **Button 3 (Day Switch)** | Active-LOW (`INPUT_PULLUP`). Tap to Peek active day, Hold 600ms to advance day once. |
| **Pin 3** | Row `21j` | 🔊 **Piezo Buzzer** | PWM output driven by `tone()`. Frequencies: 800 Hz – 3800 Hz. |
| **Pin 6** | Row `38j` | 74HC595 Pin 11 (`SH_CP`) | Shift Clock. Shifts serial bits on rising clock edge. |
| **Pin 7** | Row `37j` | 74HC595 Pin 12 (`ST_CP`) | Latch Clock. Updates parallel output registers on rising edge. |
| **Pin 8** | Row `35j` | 74HC595 Pin 14 (`DS`) | Serial Data Input. Transmits active-HIGH 8-bit segment bitmasks. |
| **Pin 9** | Row `24a` | 🔘 **Button 2 (Clock Accel)** | Active-LOW (`INPUT_PULLUP`). Progressive digital watch style fast-forward. |
| **Pin 10** | Row `19a` | 🔘 **Button 1 (Manual Switch)**| Active-LOW (`INPUT_PULLUP`). Wall toggle: Tap switches modes; Hold 1.2s toggles Presentation. |
| **Pin 11** | Row `13a` | 🔴 **Red LED (Standby/Status)**| Output via 220 $\Omega$ resistor. Solid ON in Standby; 2 Hz flashing during Grace Period. |
| **Pin 12** | Row `8a` | 🔵 **Blue LED (Air Conditioner)**| Output via 220 $\Omega$ resistor. ON during Pre-cooling, Class Active, and Presentation modes. |
| **Pin 13** | Row `3a` | 🟡 **Yellow LED (Lights)** | Output via 220 $\Omega$ resistor. ON during Class Active mode; forced OFF in Presentation mode. |
| **Pin A0** | Row `55c` | Display Digit 1 (`DIG1`) | Active-LOW Common Cathode driver for Tens of Hours digit. |
| **Pin A1** | Row `52c` | Display Digit 2 (`DIG2`) | Active-LOW Common Cathode driver for Hours digit + Center Colon. |
| **Pin A2** | Row `51c` | Display Digit 3 (`DIG3`) | Active-LOW Common Cathode driver for Tens of Minutes digit. |
| **Pin A3** | Row `50i` | Display Digit 4 (`DIG4`) | Active-LOW Common Cathode driver for Minutes digit. |

---

## 3. Firmware Architecture & State Machine (`smart_switch.ino`)

The firmware operates on a **100% non-blocking cooperative execution loop** without any `delay()` calls, ensuring multiplexing stability, debounced button responsiveness, and real-time serial telemetry processing.

### 3.1 250 Hz Display Multiplexing & Alphanumeric Splash Engine
* **POV Multiplexing:** Every 1 ms, the display driver shifts to the next digit cathode (`A0`–`A3`), giving a refresh rate of **250 Hz**, completely eliminating perceptible flicker.
* **Synchronized Colon:** The Decimal Point (DP) of Digit 2 is pulsed at exactly 1 Hz (`currentSecond % 2 == 0`).
* **Alphanumeric Splash Banners:** When modes change, the display temporarily splashes a 4-letter banner for 1.5 seconds before returning to the clock display:
  * `AUto`: Returned to automatic schedule mode.
  * `F-On`: Ad-hoc manual force ON engaged (+60 min auto-off timer).
  * `F-OF`: Early dismissal manual force OFF engaged.
  * `PrES`: Slide presentation projector mode engaged.
  * `dAY1` to `dAY7`: Current day banner when peeking, advancing, or rolling over past midnight.

### 3.2 Progressive Acceleration Engine (Button 2)
To allow evaluators to test complete daily schedules without waiting hours, holding Button 2 accelerates simulated time like a luxury digital sports watch:
* **Short Tap:** Immediate `+1 minute` bump with a 2800 Hz tap pip.
* **Tier 1 (0 – 1.5s hold):** `+1 minute` every 160 ms (~6 min/sec).
* **Tier 2 (1.5s – 3.2s hold):** `+2 minutes` every 100 ms (~20 min/sec) with a 2800 Hz transition chime.
* **Tier 3 (3.2s – 5.5s hold):** `+5 minutes` every 75 ms (~66 min/sec) with a 3300 Hz transition chime.
* **Tier 4 (> 5.5s hold):** `+15 minutes` every 50 ms (~300 min/sec / 5 hours per sec!) with a 3800 Hz warp chime.
* **Smooth Release:** Upon release, regular 1-second ticking seamlessly resumes from the exact reached time with a 2200 Hz confirmation tone.

### 3.3 Physical Day Selector UX (Button 3)
* **Tap-to-Peek (`< 600 ms`):** Displays active day (`dAY1`–`dAY7`) for 1.5s with a soft chirp (`2400 Hz, 25ms`). **Does NOT advance the day.**
* **Hold-to-Advance Once (`>= 600 ms`):** Advances the day by `+1` with a loud chime (`3000 Hz, 60ms`) and **latches immediately**. The user must physically release the button before it can step again, eliminating accidental runaway days.

### 3.4 Intelligent Manual Override (Button 1)
* **Two-Stroke Symmetrical Toggle:**
  * In **Standby:** Tap 1 $\rightarrow$ `FORCE_ON` (+60 min countdown). Tap 2 $\rightarrow$ `AUTO` (timer cancels, returns to Standby).
  * In **Class:** Tap 1 $\rightarrow$ `FORCE_OFF` (early dismissal). Tap 2 $\rightarrow$ `AUTO` (class re-energizes).
* **Boundary Re-Synchronization:** When an early-dismissed class reaches its scheduled end (+ grace period), the system automatically resets `FORCE_OFF` back to `AUTO` (`STANDBY`), ensuring subsequent classes turn on on time.
* **Presentation Mode:** Holding Button 1 for `>= 1.2s` toggles Presentation Mode (`PrES` banner, Lights OFF, AC ON).
* **Pre-Shutdown Warning Beeps:** Emits acoustic beeps at each minute mark during the final 5 minutes of ad-hoc `FORCE_ON`, with rapid beeps during the final 10 seconds.

---

## 4. Step-by-Step Bench Demonstration Script

Follow this protocol when demonstrating the prototype to professors, examiners, or judges:

### Phase 1: Tethered Web Digital Twin Demo (Laptop / Raspberry Pi)
1. Start the edge gateway server:
   ```bash
   ./run_web.sh
   ```
2. Open browser to `http://localhost:8000`.
3. **Show Real-Time Synchronization:**
   * Point out the **Digital Twin**: The virtual LEDs and 7-segment clock mirror the physical breadboard at 10 Hz.
   * Click **`SYNC HOST TIME`** $\rightarrow$ Hardware clock aligns instantly to current local time.
   * Click **`TEST BEEPER [PIN 3]`** $\rightarrow$ Evaluators hear the physical 2200 Hz tone.
4. **Demonstrate Control Modes:**
   * Click **`FORCE ON [+60M]`** $\rightarrow$ Physical Yellow & Blue LEDs ignite, display splashes `F-On`, load indicator reads **2680 W (11.17 A)**.
   * Click **`PRESENTATION`** $\rightarrow$ Yellow LED extinguishes (projector mode) while Blue LED (AC) stays on; display splashes `PrES`.
   * Click **`AUTO SCHEDULE`** $\rightarrow$ Microcontroller immediately returns to schedule; display splashes `AUto`.

### Phase 2: Autonomous Untethered Hand-Off (SDG 9 Proof)
1. Plug the **9V Battery clip** into the round black **DC Barrel Jack** on the Arduino Uno.
   *(The Uno's onboard comparator switches to battery power seamlessly without any reboot).*
2. **Unplug the USB cable from your laptop.**
   *(The 4-digit clock continues ticking and the LEDs maintain their exact state).*
3. Hand the breadboard directly to the evaluators:
   * **Test Day Switch (Button 3):**
     * **Tap:** Observe display splash `dAY1` (peeks without changing day).
     * **Hold 600ms:** Hear confirmation chime and observe display step to `dAY2` (advances once and latches).
   * **Test Fast-Forward (Button 2):**
     * Hold Button 2 to race time forward into a class period:
       * **10 mins before class:** 🔵 Blue LED ignites automatically (`PRECOOL`).
       * **At class start time:** 🟡 Yellow LED ignites (`CLASS ACTIVE`).
       * **At class finish:** 🔴 Red LED blinks (`GRACE PERIOD`).
       * **At grace finish:** 🌙 Complete auto-shutdown into `STANDBY` (0 W load).
   * **Test Manual Override (Button 1):**
     * Tap during class: Early dismissal `FORCE_OFF` activates.
     * Tap again: Instantly restores `AUTO` class operation.
     * Hold 1.2s: Engages Presentation projector mode (`PrES`).

---

## 5. Automated Verification Results

The demo prototype has been verified against two automated test suites:

* **`scratch/test_override_and_day_ux.py`:** **6/6 tests passed (100%)**
  * Monday Standby initialization: **PASS**
  * Ad-hoc `FORCE_ON` (+60m timer): **PASS**
  * `PRESENTATION` Mode (Lights OFF, AC ON): **PASS**
  * Return to `AUTO` Schedule: **PASS**
  * Early dismissal boundary auto-clearing & subsequent class `PRECOOL` trigger: **PASS**
  * Ad-hoc countdown auto-off to `STANDBY`: **PASS**

* **`scratch/test_demo_e2e.py`:** **9/9 tests passed (100%)**
  * Hardware serial connection on `/dev/ttyACM0`: **PASS**
  * EEPROM multi-day schedule flashing: **PASS**
  * Hardware day jumps: **PASS**
  * State simulation transitions (`PRECOOL`, `CLASS`, `GRACE`, `STANDBY`): **PASS**
  * Piezo sounder dispatch: **PASS**
  * Timetable matrix slot toggle idempotency: **PASS**
  * SQLite audit log recording: **PASS**
