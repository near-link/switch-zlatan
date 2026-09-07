# Smart Switch: Demo Presets & Manual Override Guide
**Automated In-Wall Classroom Switch | KICT & KOE Joint Project (Group ZLATANFC)**

---

## Part 1: State Simulation Presets (Demo Jumps)

One-click time jumps on the web console for evaluating system behaviors without waiting for real time. Calibrated to Room **E1-2-14** (Class: `08:30–11:30`, Pre-cool: 10m, Grace: 10m).

| Preset Button | Target Time | Lights (Yellow) | AC (Blue) | Red LED | Audio Alert | Purpose / Talking Point |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **08:25 PRECOOL** | `08:25:00` | **OFF** | **ACTIVE** | **OFF** | 1800 Hz chime (80ms) | Cools room before class; zero lighting waste. |
| **08:45 CLASS** | `08:45:00` | **ACTIVE** | **ACTIVE** | **OFF** | 2400 Hz chime (100ms) | Normal lecture hours; full automated power. |
| **11:35 GRACE** | `11:35:00` | **ACTIVE** | **ACTIVE** | **Fast Blink (2Hz)** | 1600 Hz ping every 15s | Safety pack-up window; prevents dark cutoffs. |
| **11:39:50 URGENT** | `11:39:50` | **ACTIVE** | **ACTIVE** | **Fast Blink (2Hz)** | 2800 Hz pulses at 1 Hz | 10s emergency countdown before power cut. |
| **12:00 STANDBY** | `12:00:00` | **OFF** | **OFF** | **Solid ON** | Descending tone (800Hz) | Zero-waste idle cutoff between class slots. |
| **23:59:50 SWEEP** | *Dynamic* (10s pre-curfew) | **ACTIVE** $\rightarrow$ **OFF** | **ACTIVE** $\rightarrow$ **OFF** | **Blink** $\rightarrow$ **Solid ON** | 1100 Hz curfew pulses | Automated night sweep kills forgotten overrides. |

### Key Preset Details:
* **08:25 PRECOOL:** AC runs early to ensure thermal comfort. Lights stay off because room is unoccupied.
* **08:45 CLASS:** Normal operating mode with full autonomous utility power.
* **11:35 GRACE:** Class ended at 11:30. Lights remain on for safe departure while the blinking red pilot LED and 15s pings warn of shutdown.
* **11:39:50 URGENT:** Final 10 seconds of Grace. Rapid 1 Hz emergency beeps lead directly into the 11:40:00 cutoff.
* **12:00 STANDBY:** Proves the core thesis: 100% elimination of phantom / vampire energy in vacant rooms.
* **23:59:50 SWEEP (Dynamic):** Dynamically tracks the policy curfew time (e.g., `23:59:50` for `00:00` cutoff, or `22:59:50` for `23:00`). Plays distinctive **1100 Hz** caution pulses and terminates any active load at zero seconds.

---

## Part 2: Intelligent Manual Override System

The switch integrates a context-aware manual override architecture engineered to balance user autonomy with guaranteed energy conservation.

### 1. The 4 Operating Modes
1. **`AUTO` (Strict Schedule):** System strictly follows the timetable database with pre-cooling and grace periods.
2. **`FORCE ON` (Configurable Ad-hoc Extension):** Manually energizes both Lights & AC during off-hours with an automatic safety countdown timer (policy-configurable in EEPROM: default 60 min, adjustable 5–240 min).
3. **`FORCE OFF` (Early Dismissal):** Manually shuts off all room utilities if a class ends early.
4. **`PRESENTATION` (Projector Mode):** Keeps AC running for thermal comfort while turning off lights for screen readability.

### 2. Dual Control Interfaces

#### A. Physical Switch (Tactile Button 1 / Pin 4)
* **Short Tap (`< 1.2s`):** Context-sensitive smart toggle:
  * In **Standby** $\rightarrow$ Engages `FORCE ON` (using policy duration, e.g. 60m countdown).
  * In **Class** $\rightarrow$ Engages `FORCE OFF` (early dismissal).
  * In any override $\rightarrow$ Immediately cancels and returns to `AUTO`.
* **Long Press (`>= 1.2s`):** Toggles `PRESENTATION` mode (Lights OFF, AC ON).

#### B. Web Management Console
* **4-Way Mode Selector:** Instant remote switching (`AUTO`, `FORCE ON`, `FORCE OFF`, `PRESENTATION`).
* **Real-time Synchronization:** Bidirectional sync over WebSocket/Serial. Physical button presses immediately reflect on the web dashboard, and web clicks immediately actuate the hardware.

---

### 3. Failsafe Self-Healing & Boundary Re-Sync
Manual switches in traditional buildings lead to human error (forgetting to turn off lights). Our system solves this with three automated self-healing mechanisms:

1. **Early Dismissal Boundary Auto-Clear:**
   If a lecturer uses `FORCE OFF` to leave early, the system does **not** stay permanently off. Once the scheduled lecture window concludes, the override automatically resets to `AUTO` (`STANDBY`), guaranteeing the *next* class turns on and pre-cools on time.
2. **Class Schedule Absorption:**
   If an ad-hoc `FORCE ON` is active and runs into a scheduled class, it seamlessly merges into the class timetable without power interruption.
3. **Night Curfew Sweep (Failsafe):**
   At the policy curfew (default `00:00`), any active manual override or forgotten timer is forcefully purged, ensuring zero overnight power waste.

---

### 4. Visual Pilot Indicator (Red LED) Summary
* **Solid ON:** System in Standby (utilities off, armed for next session).
* **Fast Blink (2 Hz):** Grace Period countdown or `FORCE ON` overtime warning.
* **Slow Pulse (1 Hz heartbeat):** Early Dismissal (`FORCE OFF`) active.
* **OFF:** Normal scheduled Class, Pre-cooling, or Presentation mode.
