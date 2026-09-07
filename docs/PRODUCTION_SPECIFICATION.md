# Automated Low-Cost In-Wall Microcontroller Switch
## Specification Document: Commercial Production & Campus-Scale Deployment
**Project Team:** ZLATANFC (KICT & KOE, International Islamic University Malaysia)  
**Target SDGs:** SDG 7 (Affordable and Clean Energy) & SDG 9 (Industry, Innovation & Infrastructure)  
**Target Infrastructure:** Institutional Academic Buildings & Lecture Halls (KICT & KOE Pilot Rollout)  
**Document Classification:** Commercial Engineering Specification & Rollout Reference  

---

## 1. Executive Summary & Production Vision

While the bench prototype demonstrates the core firmware logic on an educational Arduino Uno, the **Commercial Production System** is engineered as a scalable, industrial-grade building automation solution. Designed to replace standard mechanical wall switches across hundreds of university lecture halls, it achieves:
1. **Drop-in Wall Box Retrofit:** Fits into standard British/UK 86×86mm flush in-wall steel conduit backboxes with no invasive structural masonry alterations.
2. **True Zero-Quiescent Actuation:** Employs bistable magnetic latching relays that consume zero electrical power to remain in the ON or OFF position.
3. **Decentralized Edge Resilience (SDG 9):** A multi-tier architecture where each classroom switch operates autonomously even during campus-wide network blackouts or fiber cuts.
4. **Campus-Wide Multi-Room Fleet Management:** A centralized web platform controlling hundreds of classroom smart switches simultaneously, with automatic synchronization to university student portal course schedules (i-Ma'luum ERP).

---

## 2. Production In-Wall Hardware Design

```
                     ┌──────────────────────────────────────────────────┐
                     │          Standard 86×86mm Wall Faceplate         │
                     │  ┌────────────────────┐  ┌────────────────────┐  │
                     │  │   LIGHTS ROCKER    │  │     HVAC ROCKER    │  │
                     │  │ (Momentary Tactile)│  │ (Momentary Tactile)│  │
                     │  └────────────────────┘  └────────────────────┘  │
                     │         [ Low-Power OLED / Status Halo ]         │
                     └──────────────────────────┬───────────────────────┘
                                                │
                     ┌──────────────────────────▼───────────────────────┐
                     │               Custom 2-Layer SMD PCB             │
                     │  ├── ESP32-S3 SoC (Wi-Fi 802.11 b/g/n, BLE 5.0)  │
                     │  ├── Hi-Link HLK-PM01 (240V AC -> 5V DC Isolated)│
                     │  ├── Dual 16A / 250V AC Magnetic Latching Relays │
                     │  ├── Zero-Crossing Triac Snubber Networks        │
                     │  └── DS3231 High-Precision I2C RTC + CR1220 Batt │
                     └──────────────────────────┬───────────────────────┘
                                                │
                     ┌──────────────────────────▼───────────────────────┐
                     │       Standard BS 4662 In-Wall Flush Box         │
                     │       (86mm × 86mm × 47mm depth steel box)       │
                     └──────────────────────────────────────────────────┘
```

### 2.1 Mechanical & Electrical Enclosure
* **Enclosure Standards:** Fully compliant with British Standard **BS 4662:2006+A1:2009** for 86×86×47mm in-wall steel backboxes commonly installed across Commonwealth and Malaysian institutional facilities.
* **PCB Fabrication:** 2-layer FR-4 glass epoxy board (1.6mm thickness, 2oz copper on high-voltage AC traces). Creepage and clearance distances exceed **6.3 mm** between mains AC tracks and low-voltage DC logic, adhering strictly to **IEC 60669-2-1** and **UL 60730-1** safety standards.
* **Terminal Block Interface:** Heavy-duty rising-cage screw terminals accommodating up to 4.0 mm² solid or stranded copper building wire (Live In, Neutral, Switched Light Out, Switched HVAC Out).

### 2.2 Microcontroller & Timekeeping
* **SoC Processor:** **Espressif ESP32-S3** (Dual-core Xtensa 32-bit LX7 @ 240 MHz, 512KB SRAM, 8MB Flash).
  * Native 2.4 GHz Wi-Fi (802.11 b/g/n) and Bluetooth Low Energy 5.0.
  * Hardware cryptographic acceleration (AES-XTS-256, RSA-3072, ECC, and Secure Boot).
* **Hardware Timekeeping:**
  * Primary: High-precision **Maxim DS3231 I2C Real-Time Clock (RTC)** with temperature-compensated crystal oscillator (TCXO), accurate to $\pm 2\text{ ppm}$ (< 1 minute drift per year).
  * Backup Battery: On-board **CR1220 coin cell battery** maintains accurate calendar time for up to 10 years without external power.
  * Secondary / Network: Automated Network Time Protocol (NTP) background synchronization whenever network connectivity is active.
* **Omission of Fast-Forward Demo Button:** The artificial fast-forward button present on the demo kit is omitted in production; production firmware runs strictly in real time, with simulated testing accessible exclusively via authorized commissioning API tokens.

### 2.3 Power Supply & Actuation Electronics
* **Integrated Isolated Step-Down PSU:** **Hi-Link HLK-PM01** (or equivalent Mean Well module).
  * Converts 100–240V AC (50/60 Hz) directly to regulated 5V DC @ 600 mA (3W).
  * 3,000V AC isolation barrier between high-voltage grid input and DC logic.
  * Standby power consumption $\le 0.1\text{ W}$.
* **Magnetic Latching Relays:**
  * **Relay Type:** Dual **16A / 250V AC Bi-stable Magnetic Latching Relays** (e.g., Omron G5RL-K or Panasonic ADW11).
  * **Energy Advantage:** Standard electromagnetic relays consume 0.4–0.8W continuously just to hold their contacts closed. Magnetic latching relays use a permanent magnet to latch contacts into place mechanically, requiring only a single **15ms 5V pulse** to toggle. Quiescent coil power consumption is **zero Watts**.
  * **Safety & Brownout Immunity:** If building power fails or dips, the relay contacts do not drop out or flutter.
* **Arc Suppression & Snubber Network:**
  * MOV (Metal Oxide Varistor, 14D471K) transient surge clamp across Line and Neutral.
  * RC snubber circuit ($100\,\Omega + 0.1\,\mu\text{F}$ X2-rated film capacitor) across the HVAC relay contacts to quench high-voltage inductive kickback arcs when air conditioner compressors disconnect.

---

## 3. Scalable Network & Gateway Topologies

To scale across a university campus containing dozens of faculties and hundreds of classrooms, the production system utilizes a **Hierarchical Edge-to-Cloud Topology**:

```
                              ┌────────────────────────────────────────────────────────┐
                              │            Central University Server / VM              │
                              │       (Campus IT Datacenter / AWS / On-Premise)        │
                              │  ├── Centralized Building Management System (BMS)      │
                              │  ├── Campus-Wide Multi-Room Fleet Web Portal           │
                              │  └── i-Ma'luum Student Portal ERP API Integrator       │
                              └───────────────────────────┬────────────────────────────┘
                                                          │ Campus Backbone LAN
                                                          │ (Gigabit Ethernet / Wi-Fi)
                                                          ▼
                              ┌────────────────────────────────────────────────────────┐
                              │    Dedicated Edge Gateway (Raspberry Pi 4 / 5)         │
                              │             (1 per Building Wing / Floor)              │
                              │  ├── Local MQTT Broker (Eclipse Mosquitto)             │
                              │  ├── Local SQLite Timetable Cache (Zero-Downtime)      │
                              │  └── Fallback Web Gateway Daemon                       │
                              └───────────────────────────┬────────────────────────────┘
                                                          │ Local Secure Wi-Fi / Zigbee Mesh /
                                                          │ RS-485 Modbus RTU Bus
                                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                             Floor 2 Classroom Smart Switches                                           │
│                                                                                                                        │
│   ┌──────────────────────────┐     ┌──────────────────────────┐                 ┌──────────────────────────┐           │
│   │ Room E1-2-14 SmartSwitch │     │ Room E1-2-15 SmartSwitch │                 │ Room E1-2-16 SmartSwitch │           │
│   │  Topic: .../e1-2-14      │     │  Topic: .../e1-2-15      │    · · · · ·    │  Topic: .../e1-2-16      │           │
│   │  (ESP32 + Latching Relays│     │  (ESP32 + Latching Relays│                 │  (ESP32 + Latching Relays│           │
│   └──────────────────────────┘     └──────────────────────────┘                 └──────────────────────────┘           │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Edge Gateway Architecture (Raspberry Pi per Floor/Wing)
* **Role:** A single compact Raspberry Pi 4 or 5 is mounted inside the electrical distribution box on each floor or wing.
* **Autonomous Offline Caching (Zero-Downtime Guarantee):**
  * The edge gateway caches the entire 7-day timetable for its assigned classrooms locally in SQLite.
  * If the central university IT network, fiber backbone, or internet goes down, the edge gateway continues broadcasting schedule ticks, and every classroom switch continues operating its local schedule from internal flash memory.
* **Network Protocol:** Communication runs over lightweight **MQTT over TLS (MQTTS)** on standard campus Wi-Fi or private VLAN, using structured topic paths:
  ```
  iium/<kulliyyah>/<building>/<level>/<room>/telemetry
  iium/<kulliyyah>/<building>/<level>/<room>/command
  ```

### 3.2 Industrial Wired Fallback (RS-485 Modbus RTU)
For subterranean lecture halls or heavy reinforced concrete blocks where 2.4 GHz RF penetration is unreliable, the production PCB includes an optional **isolated RS-485 transceiver** (MAX13487E), allowing up to 128 in-wall switches to be daisy-chained along existing electrical conduit using a single twisted pair cable up to 1,200 meters.

---

## 4. Multi-Room Fleet Web Management

In production, the web portal transforms from a single-switch controller into a **Multi-Room Campus Fleet Operations Hub**.

### 4.1 Campus Fleet Overview Grid
* **Visual Fleet Status:** A comprehensive dashboard grid showing all classrooms across the campus simultaneously.
* **Live Color-Coded Room Cards:**
  * 🟢 **Green (Class Active):** Lecture in session, lights and HVAC running, active enrollment displayed.
  * 🔵 **Blue (Pre-Cooling):** 10-minute pre-cooling underway prior to class arrival.
  * ⚪ **Gray (Standby):** Classroom unoccupied, utilities disconnected, 0 W load.
  * 🟡 **Yellow (Grace Period):** Class ended, 10-minute vacation countdown in progress.
  * 🟠 **Orange (Manual Override):** Ad-hoc usage or presentation mode engaged, displaying remaining countdown minutes.
* **Aggregate Metrics Banner:** Real-time summary across the selected scope:
  * Total Rooms Active vs. Total Standby.
  * Total Instantaneous Electrical Demand (e.g., $184.2\text{ kW}$ active).
  * Real-Time Campus Energy Cost (e.g., $\text{RM } 67.23\text{ / hour}$).

### 4.2 Multi-Level Scope Broadcasting
Administrators can execute operations at 4 hierarchical levels:
1. **Campus-Wide:** Applies emergency mass shutdowns, semester holiday schedules, or global energy policies across all 250+ rooms in a single click.
2. **Kulliyyah Scope:** Configures faculty-specific course timings (e.g., engineering lab schedules vs. law seminar blocks).
3. **Level / Floor Scope:** Updates all rooms on a specific floor.
4. **Individual Room Scope:** Fine-tunes timetable slots or inspects live telemetry for a single classroom.

### 4.3 Role-Based Access Control (RBAC) & Mobile QR Code Access
* **Lecturer Quick Access:** Each physical switch faceplate features a laser-etched QR code. Lecturers scan the QR code with their smartphone to open an authenticated mobile web controller for that specific room, allowing them to engage Presentation mode or request an ad-hoc 60-minute extension without physical contact.
* **Facility Management (Admin):** Full access to timetable editing, policy configuration, EEPROM/Flash batch deployment, and historical CSV audit log exports.
* **Campus Security:** View-only access to room occupancy states and mass emergency power-down controls during building closures.

---

## 5. University-Scale Energy Economics

To quantify the commercial return on investment (ROI) for a full campus deployment, the model scales from a single prototype classroom to a 250-room university deployment (representative of the IIUM Gombak campus).

### 5.1 Single Room Baseline vs. Automated Operation

| Parameter | Traditional Manual Operation | Automated Smart Switch System | Difference |
| :--- | :--- | :--- | :--- |
| **Connected Lighting Load** | 480 W (12 troffers) | 480 W | — |
| **Connected HVAC Load** | 2,200 W (2.5 HP split inverter) | 2,200 W | — |
| **Average Operating Hours/Day**| 12.5 hours (frequently left ON) | 6.2 hours (strictly scheduled) | **-6.3 hours/day** |
| **Daily Energy Consumption** | 33.5 kWh / day | 16.6 kWh / day | **-16.9 kWh / day (-50.4%)** |
| **Daily Electricity Cost** | RM 12.23 / day | RM 6.06 / day | **Save RM 6.17 / day** |
| **Annual Electricity Cost** | RM 3,669 / year | RM 1,818 / year | **Save RM 1,851 / room / year** |

*(Calculated at commercial tariff of RM 0.365 / kWh over 300 academic operating days per year).*

### 5.2 Campus-Wide Deployment (250 Classrooms)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        CAMPUS-WIDE FINANCIAL & ENVIRONMENTAL IMPACT                     │
├──────────────────────────────────────┬─────────────────────────────────────────────────┤
│ Number of Automated Rooms            │ 250 Lecture Halls & Labs                        │
│ Annual Electrical Energy Saved       │ 1,267,500 kWh (1.27 GWh / year)                 │
│ Annual Utility Bill Reduction        │ RM 462,750 / year                               │
│ Annual Carbon Footprint Reduction    │ 823.8 Metric Tonnes CO₂ Equivalent / year       │
├──────────────────────────────────────┼─────────────────────────────────────────────────┤
│ Capital Hardware Cost (250 Units)    │ RM 35,000 (@ RM 140 / in-wall unit)             │
│ Installation & Gateway Hardware Cost │ RM 25,000 (15 Raspberry Pi gateways + cabling)  │
│ Total Initial Investment             │ RM 60,000                                       │
├──────────────────────────────────────┼─────────────────────────────────────────────────┤
│ FINANCIAL PAYBACK PERIOD             │ 1.56 MONTHS (< 48 DAYS!)                        │
│ 5-YEAR NET SAVINGS                   │ RM 2,253,750                                    │
└──────────────────────────────────────┴─────────────────────────────────────────────────┘
```

---

## 6. Manufacturing, Compliance, & Rollout Roadmap

### 6.1 Target Bill of Materials Cost @ 1,000 Units

| Component | Supplier / Model | Unit Cost (USD) | Unit Cost (MYR) |
| :--- | :--- | :---: | :---: |
| **ESP32-S3-WROOM-1** | Espressif Systems | $2.40 | RM 10.80 |
| **HLK-PM01 AC-DC PSU** | Hi-Link Electronics | $1.80 | RM 8.10 |
| **Dual 16A Latching Relays** | Panasonic / Omron | $3.20 | RM 14.40 |
| **DS3231 RTC + Crystal** | Maxim Integrated | $0.85 | RM 3.80 |
| **SMD Passive Components** | Yageo / Murata (Capacitors, MOV, Resistors) | $0.90 | RM 4.05 |
| **2-Layer FR-4 PCB** | JLCPCB / PCBWay (Panelized SMD) | $1.10 | RM 4.95 |
| **Injection Molded Faceplate** | ABS-PC Flame Retardant (UL94 V-0) | $1.75 | RM 7.85 |
| **Assembly & SMT Testing** | Automated SMT Pick-and-Place | $1.50 | RM 6.75 |
| **TOTAL ESTIMATED UNIT COST** | — | **$13.50** | **~RM 60.70** |

### 6.2 Regulatory Compliance & Safety Certifications
1. **Electrical Safety:** **IEC 60669-2-1** (Switches for household and similar fixed electrical installations — Particular requirements for electronic switches).
2. **Flammability Rating:** Enclosure plastics certified to **UL94 V-0** (self-extinguishing within 10 seconds).
3. **Electromagnetic Compatibility (EMC):** **CISPR 32 / EN 55032 Class B** (emission limits for commercial/residential IT equipment).
4. **Local Malaysian Approval:** **SIRIM QAS International** electrical safety certification and **MCMC** radio frequency certification for the 2.4 GHz wireless module.
