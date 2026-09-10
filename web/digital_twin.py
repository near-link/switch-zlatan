"""
web/digital_twin.py
Full Software Digital Twin simulating the ATmega328P microcontroller firmware (smart_switch.ino).
Replicates state transitions, 7-day EEPROM schedule memory, progressive clock acceleration,
5641AS 4-digit 7-segment display buffer, LEDs (Yellow, Blue, Red), and piezo buzzer harmonics.
"""

import time
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("digital_twin")

# State Enumerations matching smart_switch.ino
STATE_STANDBY = "STANDBY"
STATE_PRECOOL = "PRECOOL"
STATE_CLASS_ACTIVE = "ACTIVE"
STATE_GRACE_PERIOD = "GRACE"

OVERRIDE_AUTO = 0
OVERRIDE_FORCE_ON = 1
OVERRIDE_FORCE_OFF = 2
OVERRIDE_PRESENTATION = 3

DAY_NAMES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

class DigitalSwitchSimulator:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None

        # Clock & Calendar State (Default Monday 07:45:00)
        self.hour = 7
        self.minute = 45
        self.second = 0
        self.day_idx = 0  # 0=MON, ..., 6=SUN
        self.speed_factor = 1

        # State Machine
        self.current_state = STATE_STANDBY
        self.scheduled_state = STATE_STANDBY
        self.override_mode = OVERRIDE_AUTO
        self.override_remaining_sec = 0
        self.force_off_until_min = 0
        self.presentation_until_min = 0

        # Physical Actuator Outputs
        self.lights_on = False     # Pin 13: Yellow LED
        self.ac_on = False         # Pin 12: Blue LED
        self.standby_on = True     # Pin 11: Red LED
        self.grace_blink_state = False

        # 4-Digit 7-Segment Display Buffer & Splash Engine
        # Digits: [D1, D2, D3, D4], colon: bool, splash_text: Optional[str]
        self.display_digits = "07:45"
        self.display_colon = True
        self.splash_text = ""
        self.splash_expire_time = 0.0

        # Piezo Buzzer State
        self.buzzer_active = False
        self.buzzer_freq = 0
        self.buzzer_stop_time = 0.0
        self.last_buzzer_event = {"freq": 0, "duration_ms": 0, "timestamp": 0.0}

        # Simulated EEPROM 7-Day Timetable Memory
        # Format: {day_idx: [(start_min, end_min), (start_min, end_min)]}
        self.schedule: Dict[int, List[Tuple[int, int]]] = {
            0: [(510, 700), (840, 1000)],  # Mon: 08:30-11:40, 14:00-16:40
            1: [(510, 700), (840, 1000)],  # Tue: 08:30-11:40, 14:00-16:40
            2: [(510, 700), (840, 1000)],  # Wed: 08:30-11:40, 14:00-16:40
            3: [(510, 700), (840, 1000)],  # Thu: 08:30-11:40, 14:00-16:40
            4: [(510, 720)],               # Fri: 08:30-12:00
            5: [],                         # Sat: Off
            6: []                          # Sun: Off
        }
        self.precool_min = 10
        self.grace_min = 15
        self.night_sweep_h = 0
        self.night_sweep_m = 0
        self.force_on_duration_min = 60

        # Timing loop anchors
        self.last_tick_time = time.time()
        self.last_blink_time = time.time()
        self.last_telemetry_time = 0.0
        self.telemetry_callbacks = []

    def start(self):
        """Starts the simulator background worker thread."""
        with self.lock:
            if self.running:
                return
            self.running = True
            self.last_tick_time = time.time()
            self.worker_thread = threading.Thread(
                target=self._run_loop, daemon=True, name="DigitalTwinWorker"
            )
            self.worker_thread.start()
            logger.info("DigitalSwitchSimulator engine started")

    def stop(self):
        """Stops the simulator background loop."""
        with self.lock:
            self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
            self.worker_thread = None
        logger.info("DigitalSwitchSimulator engine stopped")

    def register_callback(self, callback):
        if callback not in self.telemetry_callbacks:
            self.telemetry_callbacks.append(callback)

    def trigger_splash(self, text: str, duration_sec: float = 1.5):
        """Displays temporary alphanumeric banner (e.g. 'AUto', 'PrES', 'F-On', 'dAY1')."""
        self.splash_text = text[:4].upper()
        self.splash_expire_time = time.time() + duration_sec

    def trigger_beep(self, freq: int = 2000, duration_ms: int = 60):
        """Triggers acoustic piezo buzzer alert."""
        self.buzzer_active = True
        self.buzzer_freq = freq
        now = time.time()
        self.buzzer_stop_time = now + (duration_ms / 1000.0)
        self.last_buzzer_event = {
            "freq": freq,
            "duration_ms": duration_ms,
            "timestamp": now
        }

    # =========================================================================
    # CORE SIMULATION LOOP (Runs at 20 Hz / 50ms interval)
    # =========================================================================
    def _run_loop(self):
        while self.running:
            now = time.time()
            dt = now - self.last_tick_time

            with self.lock:
                # Update buzzer expiry
                if self.buzzer_active and now >= self.buzzer_stop_time:
                    self.buzzer_active = False

                # Handle clock advance with speed multiplier
                effective_dt = dt * self.speed_factor
                if effective_dt >= 1.0:
                    advance_seconds = int(effective_dt)
                    self.last_tick_time = now - (effective_dt - advance_seconds) / max(1, self.speed_factor)
                    self._advance_seconds(advance_seconds)
                elif effective_dt < 0:
                    self.last_tick_time = now

                # 2 Hz Red LED blink in GRACE mode
                if now - self.last_blink_time >= 0.25:
                    self.last_blink_time = now
                    self.grace_blink_state = not self.grace_blink_state

                # State Machine & Outputs
                self._evaluate_schedule()
                self._update_outputs()
                self._update_display_buffer()

                # Dispatch telemetry at 2 Hz
                if now - self.last_telemetry_time >= 0.5:
                    self.last_telemetry_time = now
                    state_snapshot = self.get_state()
                    for cb in self.telemetry_callbacks:
                        try:
                            cb(state_snapshot)
                        except Exception as e:
                            logger.error(f"Error in digital twin telemetry callback: {e}")

            time.sleep(0.05)

    def _advance_seconds(self, secs: int):
        self.second += secs
        if self.second >= 60:
            mins_to_add = self.second // 60
            self.second = self.second % 60
            self.advance_minutes(mins_to_add)

        # Force ON countdown deduction
        if self.override_mode == OVERRIDE_FORCE_ON and self.override_remaining_sec > 0:
            if self.override_remaining_sec > secs:
                self.override_remaining_sec -= secs
            else:
                self.override_remaining_sec = 0
                self.override_mode = OVERRIDE_AUTO
                self.trigger_splash("AUTO", 1.5)
                self.trigger_beep(800, 300)

    def advance_minutes(self, mins: int):
        self.minute += mins
        while self.minute >= 60:
            self.minute -= 60
            self.hour += 1
            while self.hour >= 24:
                self.hour -= 24
                # Midnight Day Rollover
                self.day_idx = (self.day_idx + 1) % 7
                self.override_mode = OVERRIDE_AUTO
                self.override_remaining_sec = 0
                self.force_off_until_min = 0
                self.presentation_until_min = 0
                self.trigger_beep(3200, 80)
                self.trigger_splash(f"DAY{self.day_idx + 1}", 1.5)

    def _evaluate_schedule(self):
        curr_min = self.hour * 60 + self.minute
        day_sched = self.schedule.get(self.day_idx, [])

        in_precool = False
        in_active = False
        in_grace = False

        for start_min, end_min in day_sched:
            precool_start = max(0, start_min - self.precool_min)
            grace_end = end_min + self.grace_min

            if precool_start <= curr_min < start_min:
                in_precool = True
            elif start_min <= curr_min < end_min:
                in_active = True
            elif end_min <= curr_min < grace_end:
                in_grace = True

        if in_active:
            self.scheduled_state = STATE_CLASS_ACTIVE
        elif in_precool:
            self.scheduled_state = STATE_PRECOOL
        elif in_grace:
            self.scheduled_state = STATE_GRACE_PERIOD
        else:
            self.scheduled_state = STATE_STANDBY

        # Resolve Overrides
        if self.override_mode == OVERRIDE_FORCE_ON:
            self.current_state = STATE_CLASS_ACTIVE
        elif self.override_mode == OVERRIDE_FORCE_OFF:
            self.current_state = STATE_STANDBY
        elif self.override_mode == OVERRIDE_PRESENTATION:
            self.current_state = STATE_CLASS_ACTIVE
        else:
            self.current_state = self.scheduled_state

    def _update_outputs(self):
        if self.override_mode == OVERRIDE_PRESENTATION:
            self.lights_on = False
            self.ac_on = True
            self.standby_on = False
        elif self.current_state == STATE_CLASS_ACTIVE:
            self.lights_on = True
            self.ac_on = True
            self.standby_on = False
        elif self.current_state == STATE_PRECOOL:
            self.lights_on = False
            self.ac_on = True
            self.standby_on = False
        elif self.current_state == STATE_GRACE_PERIOD:
            self.lights_on = True
            self.ac_on = True
            self.standby_on = self.grace_blink_state
        else: # STATE_STANDBY
            self.lights_on = False
            self.ac_on = False
            self.standby_on = True

    def _update_display_buffer(self):
        now = time.time()
        self.display_colon = (self.second % 2 == 0)
        if self.splash_text and now < self.splash_expire_time:
            self.display_digits = self.splash_text
        else:
            self.display_digits = f"{self.hour:02d}:{self.minute:02d}"

    # =========================================================================
    # PHYSICAL BUTTONS SIMULATION (Pins 10, 9, 2)
    # =========================================================================
    def btn1_tap(self):
        """Button 1 (Pin 10): Wall switch manual override toggle."""
        with self.lock:
            if self.override_mode == OVERRIDE_AUTO:
                if self.scheduled_state in (STATE_CLASS_ACTIVE, STATE_PRECOOL):
                    self.engage_force_off()
                else:
                    self.engage_force_on(self.force_on_duration_min)
            else:
                self.engage_auto()

    def btn1_hold(self):
        """Button 1 (Pin 10): Hold 1.2s toggles Presentation (Projector) Mode."""
        with self.lock:
            if self.override_mode == OVERRIDE_PRESENTATION:
                self.engage_auto()
            else:
                self.engage_presentation()

    def btn2_tap(self):
        """Button 2 (Pin 9): Clock acceleration tap (+1 minute)."""
        with self.lock:
            self.advance_minutes(1)
            self.trigger_beep(2800, 30)

    def btn2_cycle_speed(self):
        """Button 2: Cycle demo speed factor (1x -> 60x -> 600x -> 1x)."""
        with self.lock:
            if self.speed_factor == 1:
                self.speed_factor = 60
            elif self.speed_factor == 60:
                self.speed_factor = 600
            else:
                self.speed_factor = 1
            self.trigger_beep(2800, 60)
            return self.speed_factor

    def btn3_tap(self):
        """Button 3 (Pin 2): Peek current day splash."""
        with self.lock:
            day_num = self.day_idx + 1
            self.trigger_splash(f"DAY{day_num}", 1.5)
            self.trigger_beep(2400, 40)

    def btn3_hold(self):
        """Button 3 (Pin 2): Hold 600ms advances academic day once."""
        with self.lock:
            self.day_idx = (self.day_idx + 1) % 7
            day_num = self.day_idx + 1
            self.trigger_splash(f"DAY{day_num}", 1.5)
            self.trigger_beep(3200, 100)

    # =========================================================================
    # OVERRIDE COMMANDS
    # =========================================================================
    def engage_force_on(self, minutes: int = 60):
        self.override_mode = OVERRIDE_FORCE_ON
        self.override_remaining_sec = minutes * 60
        self.trigger_splash("F-ON", 1.5)
        self.trigger_beep(2000, 100)
        self._evaluate_schedule()
        self._update_outputs()

    def engage_force_off(self):
        self.override_mode = OVERRIDE_FORCE_OFF
        self.override_remaining_sec = 0
        self.trigger_splash("F-OF", 1.5)
        self.trigger_beep(1200, 150)
        self._evaluate_schedule()
        self._update_outputs()

    def engage_presentation(self):
        self.override_mode = OVERRIDE_PRESENTATION
        self.override_remaining_sec = 0
        self.trigger_splash("PRES", 1.5)
        self.trigger_beep(2400, 80)
        self._evaluate_schedule()
        self._update_outputs()

    def engage_auto(self):
        self.override_mode = OVERRIDE_AUTO
        self.override_remaining_sec = 0
        self.trigger_splash("AUTO", 1.5)
        self.trigger_beep(1800, 80)
        self._evaluate_schedule()
        self._update_outputs()

    # =========================================================================
    # SERIAL ASCII PROTOCOL DISPATCHER (100% Wire Compatible with smart_switch.ino)
    # =========================================================================
    def handle_command(self, cmd: str) -> str:
        cmd = cmd.strip()
        if not cmd:
            return "ERR:EMPTY"

        with self.lock:
            if cmd == "PING":
                return "PONG:OK"

            elif cmd == "AUTO_MODE":
                self.engage_auto()
                return "OK:AUTO"

            elif cmd == "FORCE_OFF":
                self.engage_force_off()
                return "OK:FORCE_OFF"

            elif cmd == "PRESENTATION":
                self.engage_presentation()
                return "OK:PRESENTATION"

            elif cmd == "MANUAL_TOGGLE":
                self.btn1_tap()
                return "OK:TOGGLED"

            elif cmd.startswith("FORCE_ON"):
                parts = cmd.split(":")
                mins = int(parts[1]) if len(parts) > 1 else 60
                self.engage_force_on(mins)
                return f"OK:FORCE_ON:{mins}"

            elif cmd.startswith("SET_SPEED"):
                parts = cmd.split(":")
                factor = int(parts[1]) if len(parts) > 1 else 1
                self.speed_factor = factor
                self.trigger_beep(2200, 40)
                return f"OK:SPEED:{factor}"

            elif cmd.startswith("SYNC:"):
                # SYNC:HH:MM:SS
                parts = cmd.split(":")
                if len(parts) >= 4:
                    self.hour = int(parts[1])
                    self.minute = int(parts[2])
                    self.second = int(parts[3])
                    self.trigger_beep(2400, 40)
                    return "OK:TIME_SYNCED"

            elif cmd.startswith("SET_DAY:"):
                day_str = cmd.split(":")[1].strip().upper()
                if day_str in DAY_NAMES:
                    self.day_idx = DAY_NAMES.index(day_str)
                    self.trigger_splash(f"DAY{self.day_idx + 1}", 1.5)
                    self.trigger_beep(3200, 80)
                    return f"OK:DAY_SET:{day_str}"

            elif cmd.startswith("BEEP:"):
                parts = cmd.split(":")
                freq = int(parts[1]) if len(parts) > 1 else 2000
                dur = int(parts[2]) if len(parts) > 2 else 60
                self.trigger_beep(freq, dur)
                return "OK:BEEP"

            elif cmd.startswith("SET_SCHED:"):
                # SET_SCHED:sH1:sM1:eH1:eM1:sH2:sM2:eH2:eM2:precool:grace
                p = [int(x) for x in cmd.split(":")[1:]]
                if len(p) >= 10:
                    slots = []
                    if p[0] != 0 or p[2] != 0:
                        slots.append((p[0]*60 + p[1], p[2]*60 + p[3]))
                    if p[4] != 0 or p[6] != 0:
                        slots.append((p[4]*60 + p[5], p[6]*60 + p[7]))
                    self.schedule[self.day_idx] = slots
                    self.precool_min = p[8]
                    self.grace_min = p[9]
                    return "OK:SCHED_SAVED"

            elif cmd.startswith("DEPLOY_DAY:"):
                # DEPLOY_DAY:dayIdx:sH1:sM1:eH1:eM1:sH2:sM2:eH2:eM2
                p = [int(x) for x in cmd.split(":")[1:]]
                if len(p) >= 9:
                    d_idx = p[0]
                    slots = []
                    if p[1] != 0 or p[3] != 0:
                        slots.append((p[1]*60 + p[2], p[3]*60 + p[4]))
                    if p[5] != 0 or p[7] != 0:
                        slots.append((p[5]*60 + p[6], p[7]*60 + p[8]))
                    self.schedule[d_idx] = slots
                    return "OK:DAY_SAVED"

            elif cmd.startswith("SET_POLICY:"):
                p = [int(x) for x in cmd.split(":")[1:]]
                if len(p) >= 5:
                    self.precool_min = p[0]
                    self.grace_min = p[1]
                    self.night_sweep_h = p[2]
                    self.night_sweep_m = p[3]
                    self.force_on_duration_min = p[4]
                    return "OK:POLICY_SAVED"

        return "OK:ACK"

    def get_telemetry_line(self) -> str:
        """Returns exact wire-format telemetry line TLM:HH:MM:SS,STATE,..."""
        rem_min = (self.override_remaining_sec + 59) // 60 if self.override_remaining_sec > 0 else 0
        day_str = DAY_NAMES[self.day_idx]
        return (
            f"TLM:{self.hour:02d}:{self.minute:02d}:{self.second:02d},"
            f"{self.current_state},"
            f"{1 if self.lights_on else 0},"
            f"{1 if self.ac_on else 0},"
            f"{1 if self.standby_on else 0},"
            f"{self.override_mode},"
            f"{self.speed_factor},"
            f"{day_str},"
            f"{rem_min}"
        )

    def get_state(self) -> Dict[str, Any]:
        """Provides rich state representation including display and buzzer for UI twin."""
        rem_min = (self.override_remaining_sec + 59) // 60 if self.override_remaining_sec > 0 else 0
        return {
            "connected": True,
            "hardware_type": "DIGITAL_TWIN",
            "port": "EMU:ATMEGA328P",
            "time": f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}",
            "state": self.current_state,
            "lights_on": self.lights_on,
            "ac_on": self.ac_on,
            "standby_on": self.standby_on,
            "manual_override": (self.override_mode != OVERRIDE_AUTO),
            "override_mode": self.override_mode,
            "timer_remaining_min": rem_min,
            "speed_factor": self.speed_factor,
            "day": DAY_NAMES[self.day_idx],
            "day_num": self.day_idx + 1,
            "display_digits": self.display_digits,
            "display_colon": self.display_colon,
            "buzzer_active": self.buzzer_active,
            "buzzer_freq": self.buzzer_freq,
            "last_buzzer": dict(self.last_buzzer_event),
            "last_updated": time.time()
        }
