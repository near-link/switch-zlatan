"""
web/serial_bridge.py
Hybrid background communication and simulation engine for the Automated In-Wall Switch.
Provides:
1. Physical USB serial communication when connected directly to an Arduino.
2. Remote WebSocket hardware passthrough when Near runs the laptop bridge script.
3. Autonomous 24/7 virtual timetable simulation and buzzer event synthesis when untethered.
"""

import os
import time
import threading
import logging
import glob
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable, Dict, Any, List

import serial
import serial.tools.list_ports

logger = logging.getLogger("serial_bridge")
logging.basicConfig(level=logging.INFO)

MALAYSIA_TZ = timezone(timedelta(hours=8))
DAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

class ArduinoSerialBridge:
    def __init__(self, port: Optional[str] = None, baudrate: Optional[int] = None):
        if port is None:
            port = os.getenv("SERIAL_PORT", "/dev/ttyACM0")
        if baudrate is None:
            try:
                baudrate = int(os.getenv("SERIAL_BAUD", "9600"))
            except ValueError:
                baudrate = 9600
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.RLock()

        # Remote Hardware Bridge State (from laptop script)
        self.hardware_ws: Optional[Any] = None
        self.hardware_loop: Optional[asyncio.AbstractEventLoop] = None
        self.hardware_linked = False

        # Virtual Simulation State Engine
        self.sim_speed = 1
        self.sim_override_mode = 0      # 0=AUTO, 1=FORCE ON, 2=FORCE OFF, 3=PRESENTATION
        self.sim_override_remaining = 0  # Minutes remaining
        self.sim_day_idx = datetime.now(MALAYSIA_TZ).weekday() # 0=Monday
        self.sim_sec_counter = None      # Total seconds since midnight (0..86399)
        self.sim_last_tick = time.time()
        self.sim_last_state = "STANDBY"

        # Telemetry State Cache
        self.state: Dict[str, Any] = {
            "connected": True,
            "hardware_linked": False,
            "port": "VIRTUAL:ATMEGA328P",
            "time": "--:--:--",
            "state": "STANDBY",
            "lights_on": False,
            "ac_on": False,
            "standby_on": True,
            "manual_override": False,
            "override_mode": 0,
            "timer_remaining_min": 0,
            "speed_factor": 1,
            "day": DAY_CODES[self.sim_day_idx],
            "buzzer_active": False,
            "buzzer_freq": 0,
            "last_buzzer": None,
            "last_ack": None,
            "last_updated": 0
        }

        self.telemetry_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._override_lock_until = 0

    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Registers a callback function triggered on each parsed telemetry packet."""
        if callback not in self.telemetry_callbacks:
            self.telemetry_callbacks.append(callback)

    def register_hardware_bridge(self, websocket: Any, loop: asyncio.AbstractEventLoop):
        """Called when Near's laptop bridge script connects over WebSocket."""
        with self.lock:
            self.hardware_ws = websocket
            self.hardware_loop = loop
            self.hardware_linked = True
            self.state["hardware_linked"] = True
            self.state["port"] = "PHYSICAL:/dev/ttyACM0"
            self.state["last_ack"] = "HARDWARE_BRIDGE_ESTABLISHED"
            logger.info("Physical hardware bridge attached from laptop!")
        self._broadcast_state()

    def unregister_hardware_bridge(self):
        """Called when the laptop bridge script disconnects."""
        with self.lock:
            self.hardware_ws = None
            self.hardware_loop = None
            self.hardware_linked = False
            self.state["hardware_linked"] = False
            self.state["port"] = "VIRTUAL:ATMEGA328P"
            self.state["last_ack"] = "HARDWARE_BRIDGE_DISCONNECTED"
            logger.info("Physical hardware bridge detached. Autonomous simulation resumed.")
        self._broadcast_state()

    def handle_bridge_line(self, line: str):
        """Ingests raw serial lines received from the physical Arduino via the laptop bridge."""
        self._process_incoming_line(line)

    def find_available_port(self) -> str:
        """Finds active Arduino port or defaults to configured port."""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for p in ports:
            if "ACM" in p or "USB" in p or "Arduino" in p:
                return p
        acm_list = glob.glob("/dev/ttyACM*")
        if acm_list:
            return acm_list[0]
        return self.port

    def start(self):
        """Starts the background worker thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="SerialBridgeWorker")
        self.thread.start()
        logger.info(f"ArduinoSerialBridge thread started (port target: {self.port})")

    def stop(self):
        """Stops the worker thread and closes serial port cleanly."""
        self.running = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        with self.lock:
            self.state["connected"] = False
            self.state["state"] = "DISCONNECTED"

    def _connect(self) -> bool:
        target_port = self.find_available_port()
        try:
            self.ser = serial.Serial(target_port, self.baudrate, timeout=0.2)
            time.sleep(1.8)  # Allow Arduino bootloader to initialize
            self.port = target_port
            with self.lock:
                self.state["connected"] = True
                self.state["hardware_linked"] = True
                self.state["port"] = target_port
            logger.info(f"Direct serial connected to Arduino Uno on {target_port} @ {self.baudrate} baud")
            return True
        except Exception:
            self.ser = None
            return False

    def trigger_virtual_beep(self, freq: int, duration_ms: int = 80):
        """Triggers a virtual buzzer sound event for web clients."""
        with self.lock:
            self.state["buzzer_active"] = True
            self.state["buzzer_freq"] = freq
            self.state["last_buzzer"] = {
                "freq": freq,
                "duration_ms": duration_ms,
                "timestamp": time.time()
            }
        self._broadcast_state()

        def _reset_beep():
            time.sleep(duration_ms / 1000.0)
            with self.lock:
                if self.state.get("buzzer_freq") == freq:
                    self.state["buzzer_active"] = False
            self._broadcast_state()

        threading.Thread(target=_reset_beep, daemon=True).start()

    def _worker_loop(self):
        """Main background loop handling physical serial or virtual simulation ticks."""
        while self.running:
            # 1. Direct Physical USB Serial (if running directly on laptop with Arduino)
            if self.ser and self.ser.is_open:
                try:
                    raw_line = self.ser.readline()
                    if raw_line:
                        line = raw_line.decode('utf-8', errors='ignore').strip()
                        if line:
                            self._process_incoming_line(line)
                    continue
                except (serial.SerialException, OSError, TypeError) as e:
                    logger.warning(f"Direct serial connection lost: {e}")
                    if self.ser:
                        try:
                            self.ser.close()
                        except Exception:
                            pass
                        self.ser = None
                    with self.lock:
                        if not self.hardware_linked:
                            self.state["hardware_linked"] = False
                            self.state["port"] = "VIRTUAL:ATMEGA328P"
                    time.sleep(1.0)
                    continue

            # 2. Remote Laptop Hardware Bridge Active
            if self.hardware_linked and self.hardware_ws:
                time.sleep(0.5)
                continue

            # 3. Check for local physical device periodically (e.g. if user plugs in local USB)
            if not self.hardware_linked and os.path.exists(self.port):
                if self._connect():
                    continue

            # 4. Autonomous 24/7 Virtual Simulation Loop
            self._run_virtual_tick()
            time.sleep(0.2)

    def _run_virtual_tick(self):
        """Advances virtual simulation clock and updates state machine based on timetable."""
        now = time.time()
        elapsed = now - self.sim_last_tick
        interval = 1.0 / max(1, self.sim_speed)

        if elapsed < interval:
            return

        self.sim_last_tick = now

        # Initialize virtual clock to current Malaysia time if first run
        if self.sim_sec_counter is None:
            now_my = datetime.now(MALAYSIA_TZ)
            self.sim_sec_counter = now_my.hour * 3600 + now_my.minute * 60 + now_my.second
            self.sim_day_idx = now_my.weekday()

        # Advance virtual clock by 1 second (or more if lagged)
        advance_sec = max(1, int(elapsed / interval))
        self.sim_sec_counter = (self.sim_sec_counter + advance_sec) % 86400
        cur_hour = self.sim_sec_counter // 3600
        cur_minute = (self.sim_sec_counter % 3600) // 60
        cur_second = self.sim_sec_counter % 60
        cur_time_str = f"{cur_hour:02d}:{cur_minute:02d}:{cur_second:02d}"
        cur_total_min = cur_hour * 60 + cur_minute

        # Query class schedule for current room and day
        from web.database import get_classes, get_policy
        policy = get_policy()
        precool_min = policy.get("precool_minutes", 10)
        grace_min = policy.get("grace_minutes", 10)

        classes = []
        try:
            classes = get_classes(room="E1-2-14", day_of_week=self.sim_day_idx)
        except Exception:
            pass

        # Check day rollover past midnight
        prev_sec = (self.sim_sec_counter - advance_sec) % 86400
        if prev_sec > self.sim_sec_counter:
            self.sim_day_idx = (self.sim_day_idx + 1) % 7
            self.trigger_virtual_beep(3200, 80) # Midnight day rollover chime

        # Evaluate class state
        in_class = False
        in_precool = False
        in_grace = False
        remaining_grace_sec = 0

        for c in classes:
            s_min = c["start_hour"] * 60 + c["start_minute"]
            e_min = c["end_hour"] * 60 + c["end_minute"]

            if s_min <= cur_total_min < e_min:
                in_class = True
                break
            elif (s_min - precool_min) <= cur_total_min < s_min:
                in_precool = True
            elif e_min <= cur_total_min < (e_min + grace_min):
                in_grace = True
                remaining_grace_sec = (e_min + grace_min - cur_total_min) * 60 - cur_second

        # Override Countdown decrements
        if self.sim_override_mode != 0 and self.sim_override_remaining > 0:
            if cur_second == 0:
                self.sim_override_remaining = max(0, self.sim_override_remaining - 1)
                if self.sim_override_remaining == 0:
                    self.sim_override_mode = 0  # Revert to AUTO
                    self.trigger_virtual_beep(800, 300) # Expiration mechanical cutoff tone

        # Determine Relays and System State
        yellow = False
        blue = False
        red = True
        sys_state = "STANDBY"

        if self.sim_override_mode == 1:
            sys_state = "ACTIVE"
            yellow = True
            blue = True
            red = (cur_second % 2 == 0) # Warning pulse blink on Red LED
        elif self.sim_override_mode == 2:
            sys_state = "FORCE_OFF"
            yellow = False
            blue = False
            red = (cur_second % 2 == 0) # Heartbeat pulse on Red LED
        elif self.sim_override_mode == 3:
            sys_state = "PRESENTATION"
            yellow = False
            blue = True
            red = False
        elif in_class:
            sys_state = "CLASS"
            yellow = True
            blue = True
            red = False
        elif in_precool:
            sys_state = "PRECOOL"
            yellow = False
            blue = True
            red = False
        elif in_grace:
            sys_state = "GRACE"
            yellow = True
            blue = True
            red = (cur_second % 2 == 0)  # Warning pulse blink on Red LED
        else:
            sys_state = "STANDBY"
            yellow = False
            blue = False
            red = True

        # State transition acoustic alerts (in AUTO mode)
        if self.sim_override_mode == 0 and sys_state != self.sim_last_state:
            if sys_state == "CLASS":
                self.trigger_virtual_beep(2400, 100) # Class session start chime
            elif sys_state == "PRECOOL":
                self.trigger_virtual_beep(1800, 80)  # Pre-cooling engaged
            elif sys_state == "GRACE":
                self.trigger_virtual_beep(1400, 150) # Grace countdown initiated
            elif sys_state == "STANDBY":
                self.trigger_virtual_beep(800, 250)  # Power cutoff tone
            self.sim_last_state = sys_state

        # Grace Period Countdown Warning Beeps (matching smart_switch.ino)
        if in_grace and self.sim_override_mode == 0:
            if 0 < remaining_grace_sec <= 10:
                self.trigger_virtual_beep(2800, 50) # Final 10s urgent 1Hz emergency countdown
            elif 10 < remaining_grace_sec <= 60:
                if cur_second % 5 == 0:
                    self.trigger_virtual_beep(2200, 45) # Final 1m warning beep every 5s
            elif remaining_grace_sec > 60:
                if cur_second % 15 == 0:
                    self.trigger_virtual_beep(1600, 35) # General grace acoustic ping every 15s

        # Force ON Countdown Warning Beeps
        if self.sim_override_mode == 1 and self.sim_override_remaining > 0:
            rem_sec = self.sim_override_remaining * 60 - cur_second
            if 0 < rem_sec <= 300:
                if rem_sec % 60 == 0:
                    self.trigger_virtual_beep(1500, 80) # 1 chirp per minute in final 5m
                elif rem_sec <= 10 and rem_sec % 2 == 0:
                    self.trigger_virtual_beep(2000, 40) # Urgent chirps every 2s in final 10s

        # Night sweep curfew cutoff check
        sweep_h = 0
        sweep_m = 0
        cur_sec_of_day = cur_hour * 3600 + cur_minute * 60 + cur_second
        sweep_sec_of_day = sweep_h * 3600 + sweep_m * 60
        sec_to_sweep = (sweep_sec_of_day - cur_sec_of_day + 86400) % 86400
        if 0 < sec_to_sweep <= 10:
            self.trigger_virtual_beep(1100, 75)
        elif sec_to_sweep == 0 and cur_second == 0 and self.sim_override_mode != 0:
            self.sim_override_mode = 0
            self.sim_override_remaining = 0
            self.trigger_virtual_beep(800, 300)

        day_str = DAY_CODES[self.sim_day_idx]
        override_flag = (self.sim_override_mode != 0)

        # Build simulated TLM packet matching Arduino ATmega328P firmware
        sim_tlm = f"TLM:{cur_time_str},{sys_state},{1 if yellow else 0},{1 if blue else 0},{1 if red else 0},{self.sim_override_mode},{self.sim_speed},{day_str},{self.sim_override_remaining}"
        self._process_incoming_line(sim_tlm)

    def _process_incoming_line(self, line: str):
        """Processes incoming ASCII serial telemetry line from physical Arduino or simulator."""
        if line.startswith("TLM:"):
            payload = line[4:]
            parts = payload.split(',')
            if len(parts) >= 7:
                clock_time = parts[0]
                sys_state = parts[1]
                yellow = (parts[2] == '1')
                blue = (parts[3] == '1')
                red = (parts[4] == '1')
                try:
                    override_code = int(parts[5])
                except ValueError:
                    override_code = 1 if parts[5] == '1' else 0
                override = (override_code != 0)

                try:
                    speed = int(parts[6])
                except ValueError:
                    speed = 1
                day = parts[7] if len(parts) >= 8 else "MON"
                try:
                    timer_remaining = int(parts[8]) if len(parts) >= 9 else 0
                except ValueError:
                    timer_remaining = 0

                with self.lock:
                    if time.time() < self._override_lock_until:
                        override = self.state.get("manual_override", override)
                        override_code = self.state.get("override_mode", override_code)
                        timer_remaining = self.state.get("timer_remaining_min", timer_remaining)

                    self.state.update({
                        "connected": True,
                        "hardware_linked": self.hardware_linked,
                        "port": "PHYSICAL:/dev/ttyACM0" if self.hardware_linked else "VIRTUAL:ATMEGA328P",
                        "time": clock_time,
                        "state": sys_state,
                        "lights_on": yellow,
                        "ac_on": blue,
                        "standby_on": red,
                        "manual_override": override,
                        "override_mode": override_code,
                        "timer_remaining_min": timer_remaining,
                        "speed_factor": speed,
                        "day": day,
                        "last_updated": time.time()
                    })

                self._broadcast_state()

        elif line.startswith("OK:") or line.startswith("ERR:") or line.startswith("PONG:"):
            with self.lock:
                self.state["last_ack"] = line
            logger.info(f"Arduino ACK: {line}")
            self._broadcast_state()

    def _broadcast_state(self):
        """Dispatches state dictionary to all registered callbacks."""
        state_copy = self.get_state()
        for cb in self.telemetry_callbacks:
            try:
                cb(state_copy)
            except Exception as e:
                logger.error(f"Error in telemetry callback: {e}")

    def send_command(self, cmd: str) -> bool:
        """Sends an ASCII command to physical Arduino if linked, or handles in virtual engine."""
        clean_cmd = cmd.strip()

        # 1. Forward to Remote Laptop Bridge if connected
        if self.hardware_linked and self.hardware_ws and self.hardware_loop:
            try:
                asyncio.run_coroutine_threadsafe(self.hardware_ws.send_text(clean_cmd), self.hardware_loop)
                logger.info(f"Forwarded Command to Laptop Bridge -> {clean_cmd}")
                # Play confirmation tone on web client matching firmware
                if clean_cmd.startswith("FORCE_ON"):
                    self.trigger_virtual_beep(2600, 60)
                elif clean_cmd == "FORCE_OFF":
                    self.trigger_virtual_beep(1600, 60)
                elif clean_cmd == "PRESENTATION":
                    self.trigger_virtual_beep(2700, 80)
                elif clean_cmd == "AUTO_MODE":
                    self.trigger_virtual_beep(2000, 50)
                elif clean_cmd.startswith("BEEP"):
                    parts = clean_cmd.split(":")
                    f = int(parts[1]) if len(parts) > 1 else 2200
                    d = int(parts[2]) if len(parts) > 2 else 100
                    self.trigger_virtual_beep(f, d)
                return True
            except Exception as e:
                logger.error(f"Failed to forward command to laptop bridge: {e}")

        # 2. Forward to Direct Physical USB Serial if open
        if self.ser and self.ser.is_open:
            try:
                with self.lock:
                    self.ser.write((clean_cmd + "\n").encode('utf-8'))
                    self.ser.flush()
                logger.info(f"Sent Command to Serial -> {clean_cmd}")
                return True
            except Exception as e:
                logger.error(f"Failed to write command to serial: {e}")

        # 3. Virtual Engine Command Processing (when physical hardware is absent)
        logger.info(f"Virtual Engine Executed -> {clean_cmd}")
        if clean_cmd.startswith("FORCE_ON"):
            minutes = int(clean_cmd.split(":")[1]) if ":" in clean_cmd else 60
            self.sim_override_mode = 1
            self.sim_override_remaining = minutes
            self.trigger_virtual_beep(2600, 60)
        elif clean_cmd == "FORCE_OFF":
            self.sim_override_mode = 2
            self.sim_override_remaining = 0
            self.trigger_virtual_beep(1600, 60)
        elif clean_cmd == "PRESENTATION":
            self.sim_override_mode = 3
            self.sim_override_remaining = 120
            self.trigger_virtual_beep(2700, 80)
        elif clean_cmd == "AUTO_MODE":
            self.sim_override_mode = 0
            self.sim_override_remaining = 0
            self.trigger_virtual_beep(2000, 50)
        elif clean_cmd == "MANUAL_TOGGLE":
            if self.sim_override_mode != 0:
                self.sim_override_mode = 0
                self.sim_override_remaining = 0
                self.trigger_virtual_beep(2000, 50)
            else:
                self.sim_override_mode = 1
                self.sim_override_remaining = 60
                self.trigger_virtual_beep(2600, 60)
        elif clean_cmd.startswith("SET_SPEED:"):
            try:
                factor = int(clean_cmd.split(":")[1])
                self.sim_speed = factor
                self.trigger_virtual_beep(2400, 25)
            except Exception:
                pass
        elif clean_cmd.startswith("SET_DAY:"):
            d_str = clean_cmd.split(":")[1].strip().upper()
            if d_str in DAY_CODES:
                self.sim_day_idx = DAY_CODES.index(d_str)
                self.trigger_virtual_beep(2800, 50)
        elif clean_cmd.startswith("SET_SCHED:") or clean_cmd.startswith("SET_POLICY:"):
            self.trigger_virtual_beep(2400, 80)
        elif clean_cmd.startswith("BEEP:"):
            parts = clean_cmd.split(":")
            f = int(parts[1]) if len(parts) > 1 else 2200
            d = int(parts[2]) if len(parts) > 2 else 100
            self.trigger_virtual_beep(f, d)
        elif clean_cmd == "PING":
            with self.lock:
                self.state["last_ack"] = "PONG:OK"

        return True

    def sync_time(self, hour: int, minute: int, second: int) -> bool:
        cmd = f"SYNC:{hour:02d}:{minute:02d}:{second:02d}"
        if not self.hardware_linked:
            self.sim_sec_counter = hour * 3600 + minute * 60 + second
        return self.send_command(cmd)

    def set_schedule(self, sH1: int, sM1: int, eH1: int, eM1: int,
                      sH2: int, sM2: int, eH2: int, eM2: int,
                      precool: int, grace: int) -> bool:
        cmd = f"SET_SCHED:{sH1}:{sM1}:{eH1}:{eM1}:{sH2}:{sM2}:{eH2}:{eM2}:{precool}:{grace}"
        return self.send_command(cmd)

    def force_on(self, minutes: int = 60) -> bool:
        with self.lock:
            self.state["manual_override"] = True
            self.state["override_mode"] = 1
            self.state["timer_remaining_min"] = minutes
            self.state["lights_on"] = True
            self.state["ac_on"] = True
            self._override_lock_until = time.time() + 0.6
        return self.send_command(f"FORCE_ON:{minutes}")

    def force_off(self) -> bool:
        with self.lock:
            self.state["manual_override"] = True
            self.state["override_mode"] = 2
            self.state["timer_remaining_min"] = 0
            self.state["lights_on"] = False
            self.state["ac_on"] = False
            self._override_lock_until = time.time() + 0.6
        return self.send_command("FORCE_OFF")

    def presentation_mode(self) -> bool:
        with self.lock:
            self.state["manual_override"] = True
            self.state["override_mode"] = 3
            self.state["timer_remaining_min"] = 120
            self.state["lights_on"] = False
            self.state["ac_on"] = True
            self._override_lock_until = time.time() + 0.6
        return self.send_command("PRESENTATION")

    def manual_toggle(self) -> bool:
        return self.send_command("MANUAL_TOGGLE")

    def auto_mode(self) -> bool:
        with self.lock:
            self.state["manual_override"] = False
            self.state["override_mode"] = 0
            self.state["timer_remaining_min"] = 0
            self._override_lock_until = time.time() + 0.6
        return self.send_command("AUTO_MODE")

    def set_speed(self, factor: int) -> bool:
        return self.send_command(f"SET_SPEED:{factor}")

    def beep(self, freq: int = 2200, duration: int = 100) -> bool:
        return self.send_command(f"BEEP:{freq}:{duration}")

    def set_switch_day(self, day: str) -> bool:
        return self.send_command(f"SET_DAY:{day}")

    def deploy_week_schedule(self, commands: list) -> bool:
        all_ok = True
        for cmd in commands:
            ok = self.send_command(cmd)
            if not ok:
                all_ok = False
            time.sleep(0.04)
        return all_ok

    def ping(self) -> bool:
        return self.send_command("PING")

    def get_state(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.state)

