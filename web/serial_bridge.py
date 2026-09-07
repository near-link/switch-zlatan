"""
web/serial_bridge.py
Thread-safe background serial communication worker for Arduino Uno R3.
Handles telemetry parsing, command transmission, and auto-reconnection on /dev/ttyACM0.
"""

import os
import time
import threading
import logging
import glob
from typing import Optional, Callable, Dict, Any
import serial
import serial.tools.list_ports

logger = logging.getLogger("serial_bridge")
logging.basicConfig(level=logging.INFO)

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
        self.lock = threading.Lock()

        # Telemetry State Cache
        self.state: Dict[str, Any] = {
            "connected": False,
            "port": port,
            "time": "--:--:--",
            "state": "DISCONNECTED",
            "lights_on": False,
            "ac_on": False,
            "standby_on": False,
            "manual_override": False,
            "override_mode": 0,
            "timer_remaining_min": 0,
            "speed_factor": 1,
            "day": "MON",
            "last_ack": None,
            "last_updated": 0
        }

        self.telemetry_callbacks = []
        self._override_lock_until = 0

    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Registers a callback function triggered on each parsed telemetry packet."""
        if callback not in self.telemetry_callbacks:
            self.telemetry_callbacks.append(callback)

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
        """Starts the background serial communication thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="SerialBridgeWorker")
        self.thread.start()
        logger.info(f"ArduinoSerialBridge thread started for {self.port}")

    def stop(self):
        """Stops the worker thread and closes the serial port cleanly."""
        self.running = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
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
                self.state["port"] = target_port
            logger.info(f"Connected to Arduino Uno on {target_port} @ {self.baudrate} baud")
            return True
        except Exception as e:
            with self.lock:
                self.state["connected"] = False
                self.state["state"] = "PORT_ERROR"
            self.ser = None
            return False

    def _worker_loop(self):
        while self.running:
            if not self.ser or not self.ser.is_open:
                if not self._connect():
                    time.sleep(2.0)
                    continue

            try:
                raw_line = self.ser.readline()
                if not raw_line:
                    continue

                line = raw_line.decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                self._process_incoming_line(line)

            except (serial.SerialException, OSError) as e:
                logger.warning(f"Serial connection lost: {e}")
                if self.ser:
                    try:
                        self.ser.close()
                    except Exception:
                        pass
                    self.ser = None
                with self.lock:
                    self.state["connected"] = False
                    self.state["state"] = "DISCONNECTED"
                time.sleep(2.0)
            except Exception as e:
                logger.error(f"Unexpected error in serial worker: {e}")
                time.sleep(0.5)

    def _process_incoming_line(self, line: str):
        # Telemetry packet: TLM:08:44:11,STATE,YELLOW,BLUE,RED,OVERRIDE,SPEED
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

                # Fire registered callbacks
                state_copy = dict(self.state)
                for cb in self.telemetry_callbacks:
                    try:
                        cb(state_copy)
                    except Exception as e:
                        logger.error(f"Error in telemetry callback: {e}")

        elif line.startswith("OK:") or line.startswith("ERR:") or line.startswith("PONG:"):
            with self.lock:
                self.state["last_ack"] = line
            logger.info(f"Arduino ACK: {line}")

    def send_command(self, cmd: str) -> bool:
        """Sends an ASCII command line to the Arduino."""
        if not self.ser or not self.ser.is_open:
            logger.warning(f"Cannot send command '{cmd}': Serial disconnected")
            return False

        try:
            with self.lock:
                self.ser.write((cmd.strip() + "\n").encode('utf-8'))
                self.ser.flush()
            logger.info(f"Sent Command -> {cmd}")
            return True
        except Exception as e:
            logger.error(f"Failed to send command '{cmd}': {e}")
            return False

    def sync_time(self, hour: int, minute: int, second: int) -> bool:
        cmd = f"SYNC:{hour:02d}:{minute:02d}:{second:02d}"
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
        res = self.send_command(f"FORCE_ON:{minutes}")
        if res:
            state_copy = self.get_state()
            for cb in self.telemetry_callbacks:
                try:
                    cb(state_copy)
                except Exception as e:
                    logger.error(f"Error in telemetry callback: {e}")
        return res

    def force_off(self) -> bool:
        with self.lock:
            self.state["manual_override"] = True
            self.state["override_mode"] = 2
            self.state["timer_remaining_min"] = 0
            self.state["lights_on"] = False
            self.state["ac_on"] = False
            self._override_lock_until = time.time() + 0.6
        res = self.send_command("FORCE_OFF")
        if res:
            state_copy = self.get_state()
            for cb in self.telemetry_callbacks:
                try:
                    cb(state_copy)
                except Exception as e:
                    logger.error(f"Error in telemetry callback: {e}")
        return res

    def presentation_mode(self) -> bool:
        with self.lock:
            self.state["manual_override"] = True
            self.state["override_mode"] = 3
            self.state["timer_remaining_min"] = 0
            self.state["lights_on"] = False
            self.state["ac_on"] = True
            self._override_lock_until = time.time() + 0.6
        res = self.send_command("PRESENTATION")
        if res:
            state_copy = self.get_state()
            for cb in self.telemetry_callbacks:
                try:
                    cb(state_copy)
                except Exception as e:
                    logger.error(f"Error in telemetry callback: {e}")
        return res

    def manual_toggle(self) -> bool:
        with self.lock:
            next_state = not self.state.get("manual_override", False)
            self.state["manual_override"] = next_state
            if next_state:
                self.state["override_mode"] = 1
                self.state["timer_remaining_min"] = 60
                self.state["lights_on"] = True
                self.state["ac_on"] = True
            else:
                self.state["override_mode"] = 0
                self.state["timer_remaining_min"] = 0
            self._override_lock_until = time.time() + 0.6
        res = self.send_command("MANUAL_TOGGLE")
        if res:
            state_copy = self.get_state()
            for cb in self.telemetry_callbacks:
                try:
                    cb(state_copy)
                except Exception as e:
                    logger.error(f"Error in telemetry callback: {e}")
        return res

    def auto_mode(self) -> bool:
        with self.lock:
            self.state["manual_override"] = False
            self.state["override_mode"] = 0
            self.state["timer_remaining_min"] = 0
            self._override_lock_until = time.time() + 0.6
        res = self.send_command("AUTO_MODE")
        if res:
            state_copy = self.get_state()
            for cb in self.telemetry_callbacks:
                try:
                    cb(state_copy)
                except Exception as e:
                    logger.error(f"Error in telemetry callback: {e}")
        return res

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
            time.sleep(0.04)  # Ensure Arduino UART buffer absorbs each command cleanly
        return all_ok

    def ping(self) -> bool:
        return self.send_command("PING")

    def get_state(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.state)

