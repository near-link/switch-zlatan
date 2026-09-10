"""
web/serial_bridge.py
Unified Hardware Dispatcher & Telemetry Bridge.
Dynamically routes between the software Digital Twin simulator and the laptop hardware agent.
Implements 10-second heartbeat failsafe auto-reversion, hotplug detection, and unified state caching.
"""

import os
import time
import json
import logging
import threading
import glob
from typing import Optional, Callable, Dict, Any, List
import asyncio

from web.digital_twin import DigitalSwitchSimulator

logger = logging.getLogger("serial_bridge")
logging.basicConfig(level=logging.INFO)

class UnifiedHardwareDispatcher:
    def __init__(self):
        self.lock = threading.RLock()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.running = False
        self.mode = os.getenv("HARDWARE_MODE", "twin") # 'twin' or 'physical'
        
        # Subsystems
        self.simulator = DigitalSwitchSimulator()
        self.telemetry_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.mode_change_callbacks: List[Callable[[str], None]] = []

        # Physical Hardware Agent State (from laptop via WebSocket)
        self.agent_ws = None
        self.agent_connected = False
        self.agent_usb_detected = False
        self.agent_port = "NONE"
        self.agent_engaged = False
        self.last_agent_heartbeat = 0.0

        # Physical Direct Serial Fallback (if running locally on laptop with USB directly)
        self.direct_ser = None
        self.direct_port = os.getenv("SERIAL_PORT", "/dev/ttyACM0")
        self.direct_baud = int(os.getenv("SERIAL_BAUD", "9600"))

        # Physical Telemetry State Cache
        self.physical_state: Dict[str, Any] = {
            "connected": False,
            "hardware_type": "PHYSICAL_BENCH",
            "port": "/dev/ttyACM0",
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
            "day_num": 1,
            "display_digits": "--:--",
            "display_colon": True,
            "buzzer_active": False,
            "buzzer_freq": 0,
            "last_buzzer": {"freq": 0, "duration_ms": 0, "timestamp": 0.0},
            "last_updated": 0
        }

        # Watchdog Thread for 10s Heartbeat Timeout
        self.watchdog_thread: Optional[threading.Thread] = None

    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        if callback not in self.telemetry_callbacks:
            self.telemetry_callbacks.append(callback)

    def register_mode_change_callback(self, callback: Callable[[str], None]):
        if callback not in self.mode_change_callbacks:
            self.mode_change_callbacks.append(callback)

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def _send_agent_json(self, payload: Dict[str, Any]):
        if self.agent_ws:
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.agent_ws.send_json(payload), self.loop)
            else:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.agent_ws.send_json(payload))
                except Exception as e:
                    logger.debug(f"Failed to schedule agent packet: {e}")

    def start(self):
        with self.lock:
            if self.running:
                return
            self.running = True

            # Register simulator internal callback to route through dispatcher
            self.simulator.register_callback(self._on_simulator_telemetry)
            self.simulator.start()

            # Start background watchdog for heartbeat & direct serial check
            self.watchdog_thread = threading.Thread(
                target=self._watchdog_loop, daemon=True, name="HardwareWatchdog"
            )
            self.watchdog_thread.start()
            logger.info(f"UnifiedHardwareDispatcher started. Initial Mode: {self.mode}")

    def stop(self):
        with self.lock:
            self.running = False
            self.simulator.stop()
            if self.direct_ser:
                try:
                    self.direct_ser.close()
                except Exception:
                    pass
                self.direct_ser = None

    def _on_simulator_telemetry(self, sim_state: Dict[str, Any]):
        if self.mode == "twin":
            enriched = dict(sim_state)
            enriched["mode"] = "twin"
            enriched["agent_connected"] = self.agent_connected
            enriched["agent_usb_detected"] = self.agent_usb_detected
            enriched["agent_port"] = self.agent_port
            for cb in self.telemetry_callbacks:
                try:
                    cb(enriched)
                except Exception as e:
                    logger.error(f"Error in telemetry callback: {e}")

    def _watchdog_loop(self):
        while self.running:
            time.sleep(1.0)
            now = time.time()
            with self.lock:
                # 10s Heartbeat Check in Physical Mode
                if self.mode == "physical":
                    if self.agent_connected and (now - self.last_agent_heartbeat > 10.0):
                        logger.warning("Laptop agent heartbeat lost (>10s). Auto-reverting to Digital Twin Mode!")
                        self._internal_set_mode("twin", reason="HEARTBEAT_TIMEOUT")
                    elif not self.agent_connected and not (self.direct_ser and self.direct_ser.is_open):
                        # No physical bridge active at all
                        pass

    def _internal_set_mode(self, new_mode: str, reason: str = "MANUAL") -> bool:
        if new_mode not in ("twin", "physical"):
            return False
        old_mode = self.mode
        self.mode = new_mode
        logger.info(f"Hardware Mode Transition: {old_mode} -> {new_mode} (Reason: {reason})")

        # Notify Agent if connected
        if self.agent_ws:
            action = "CONNECT_HARDWARE" if new_mode == "physical" else "DISCONNECT_HARDWARE"
            self._send_agent_json({"action": action, "port": "/dev/ttyACM0"})

        # Fire mode change callbacks to broadcast to UI
        for cb in self.mode_change_callbacks:
            try:
                cb(new_mode)
            except Exception as e:
                logger.error(f"Error in mode change callback: {e}")

        return True

    def set_mode(self, new_mode: str, reason: str = "MANUAL") -> bool:
        with self.lock:
            return self._internal_set_mode(new_mode, reason)

    # =========================================================================
    # LAPPOINT AGENT WEBSOCKET INTERACTION (/ws/hardware-edge)
    # =========================================================================
    def register_agent_socket(self, ws):
        with self.lock:
            self.agent_ws = ws
            self.agent_connected = True
            self.last_agent_heartbeat = time.time()
            logger.info("Laptop hardware agent registered!")
            # If current mode is physical, immediately instruct it to lock serial
            if self.mode == "physical":
                self._send_agent_json({"action": "CONNECT_HARDWARE", "port": "/dev/ttyACM0"})

    def unregister_agent_socket(self, ws):
        with self.lock:
            if self.agent_ws == ws:
                self.agent_ws = None
                self.agent_connected = False
                self.agent_usb_detected = False
                self.agent_engaged = False
                logger.info("Laptop hardware agent disconnected.")
                if self.mode == "physical":
                    self._internal_set_mode("twin", reason="AGENT_DISCONNECT")

    def handle_agent_message(self, data: Dict[str, Any]):
        msg_type = data.get("type")
        now = time.time()

        if msg_type == "heartbeat":
            with self.lock:
                self.last_agent_heartbeat = now
                self.agent_connected = True
                self.agent_usb_detected = data.get("usb_detected", False)
                self.agent_port = data.get("port", "NONE")
                self.agent_engaged = data.get("engaged", False)

        elif msg_type == "telemetry":
            raw_line = data.get("line", "")
            self._process_physical_telemetry_line(raw_line)

        elif msg_type == "ack":
            logger.info(f"Agent ACK: {data}")

    def _process_physical_telemetry_line(self, line: str):
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
                    self.physical_state.update({
                        "connected": True,
                        "hardware_type": "PHYSICAL_BENCH",
                        "port": self.agent_port,
                        "time": clock_time,
                        "state": sys_state,
                        "lights_on": yellow,
                        "ac_on": blue,
                        "standby_on": red,
                        "manual_override": (override_code != 0),
                        "override_mode": override_code,
                        "timer_remaining_min": timer_remaining,
                        "speed_factor": speed,
                        "day": day,
                        "display_digits": clock_time[:5],
                        "display_colon": True,
                        "last_updated": time.time()
                    })

                if self.mode == "physical":
                    enriched = dict(self.physical_state)
                    enriched["mode"] = "physical"
                    enriched["agent_connected"] = self.agent_connected
                    enriched["agent_usb_detected"] = self.agent_usb_detected
                    enriched["agent_port"] = self.agent_port
                    for cb in self.telemetry_callbacks:
                        try:
                            cb(enriched)
                        except Exception as e:
                            logger.error(f"Error in physical telemetry callback: {e}")

    # =========================================================================
    # UNIFIED COMMAND DISPATCH
    # =========================================================================
    def send_command(self, cmd: str) -> bool:
        cmd = cmd.strip()
        if not cmd:
            return False

        if self.mode == "twin":
            res = self.simulator.handle_command(cmd)
            return not res.startswith("ERR:")
        else: # physical mode
            if self.agent_ws:
                self._send_agent_json({"action": "COMMAND", "cmd": cmd})
                return True
            return False

    def handle_hardware_button(self, btn_id: int, action: str = "tap") -> bool:
        """Interactive button actions for Buttons 1, 2, 3."""
        if self.mode == "twin":
            if btn_id == 1:
                if action == "hold":
                    self.simulator.btn1_hold()
                else:
                    self.simulator.btn1_tap()
            elif btn_id == 2:
                if action == "cycle":
                    self.simulator.btn2_cycle_speed()
                else:
                    self.simulator.btn2_tap()
            elif btn_id == 3:
                if action == "hold":
                    self.simulator.btn3_hold()
                else:
                    self.simulator.btn3_tap()
            return True
        else:
            if btn_id == 1:
                return self.send_command("PRESENTATION" if action == "hold" else "MANUAL_TOGGLE")
            elif btn_id == 2:
                return self.send_command("SET_SPEED:60")
            elif btn_id == 3:
                return self.send_command("SET_DAY:TUE")
            return False

    # Wrappers for existing server endpoints
    def force_on(self, minutes: int = 60) -> bool:
        return self.send_command(f"FORCE_ON:{minutes}")

    def force_off(self) -> bool:
        return self.send_command("FORCE_OFF")

    def presentation_mode(self) -> bool:
        return self.send_command("PRESENTATION")

    def manual_toggle(self) -> bool:
        return self.send_command("MANUAL_TOGGLE")

    def auto_mode(self) -> bool:
        return self.send_command("AUTO_MODE")

    def set_speed(self, factor: int) -> bool:
        return self.send_command(f"SET_SPEED:{factor}")

    def beep(self, freq: int = 2200, duration: int = 100) -> bool:
        return self.send_command(f"BEEP:{freq}:{duration}")

    def set_switch_day(self, day: str) -> bool:
        return self.send_command(f"SET_DAY:{day}")

    def sync_time(self, hour: int, minute: int, second: int) -> bool:
        return self.send_command(f"SYNC:{hour:02d}:{minute:02d}:{second:02d}")

    def set_schedule(self, sH1: int, sM1: int, eH1: int, eM1: int,
                     sH2: int, sM2: int, eH2: int, eM2: int,
                     precool: int, grace: int) -> bool:
        return self.send_command(f"SET_SCHED:{sH1}:{sM1}:{eH1}:{eM1}:{sH2}:{sM2}:{eH2}:{eM2}:{precool}:{grace}")

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
            if self.mode == "twin":
                st = self.simulator.get_state()
            else:
                st = dict(self.physical_state)
            st["mode"] = self.mode
            st["agent_connected"] = self.agent_connected
            st["agent_usb_detected"] = self.agent_usb_detected
            st["agent_port"] = self.agent_port
            st["agent_engaged"] = self.agent_engaged
            return st

# Backwards compatibility alias for server.py import
ArduinoSerialBridge = UnifiedHardwareDispatcher
