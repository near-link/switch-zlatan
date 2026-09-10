"""
web/hardware_agent.py
Persistent background daemon running on Near's laptop.
Monitors USB serial connection to Arduino Uno R3 (/dev/ttyACM0),
connects to the VPS edge ingress (switchtunnel.imankh.me),
and dynamically binds/releases the physical hardware on command from dash.imankh.me.
"""

import os
import sys
import time
import json
import glob
import logging
import asyncio
from typing import Optional

try:
    import websockets
except ImportError:
    websockets = None

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("hardware_agent")

# Configuration
EDGE_URL = os.getenv("EDGE_INGRESS_URL", "wss://switchtunnel.imankh.me/ws/hardware-edge")
FALLBACK_EDGE_URL = os.getenv("FALLBACK_EDGE_URL", "wss://switch.imankh.me/ws/hardware-edge")
SECRET_TOKEN = os.getenv("AGENT_SECRET_TOKEN", "smart-switch-secure-salt-2026-evangelion")
DEFAULT_BAUD = int(os.getenv("SERIAL_BAUD", "9600"))

def find_arduino_port() -> Optional[str]:
    """Scans system for Arduino USB serial port."""
    if not serial:
        return None
    try:
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for p in ports:
            if "ACM" in p or "USB" in p or "Arduino" in p:
                return p
        acm_list = glob.glob("/dev/ttyACM*")
        if acm_list:
            return acm_list[0]
    except Exception as e:
        logger.debug(f"Error scanning ports: {e}")
    return None

class HardwareNodeAgent:
    def __init__(self):
        self.ser: Optional[serial.Serial] = None
        self.serial_open = False
        self.ws = None
        self.running = True
        self.current_port: Optional[str] = None
        self.engaged = False

    def open_serial(self, port: Optional[str] = None) -> bool:
        if not serial:
            logger.error("pyserial not installed")
            return False
        if self.ser and self.ser.is_open:
            return True
        target_port = port or find_arduino_port() or "/dev/ttyACM0"
        try:
            self.ser = serial.Serial(target_port, DEFAULT_BAUD, timeout=0.2)
            time.sleep(1.8)  # Allow Arduino bootloader to initialize
            self.serial_open = True
            self.current_port = target_port
            logger.info(f"Physical Arduino locked on {target_port} @ {DEFAULT_BAUD} baud")
            return True
        except Exception as e:
            logger.warning(f"Failed to open serial port {target_port}: {e}")
            self.ser = None
            self.serial_open = False
            return False

    def close_serial(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.serial_open = False
        logger.info("Physical serial port released")

    async def run(self):
        logger.info(f"Starting Hardware Node Agent. Ingress target: {EDGE_URL}")
        while self.running:
            target = EDGE_URL
            try:
                url_with_token = f"{target}?token={SECRET_TOKEN}"
                logger.info(f"Connecting to VPS Edge: {target}...")
                async with websockets.connect(url_with_token, ping_interval=15, ping_timeout=10) as ws:
                    self.ws = ws
                    logger.info("Connected to VPS Edge Gateway!")
                    await self._handle_connection(ws)
            except Exception as e:
                logger.warning(f"VPS connection error: {e}. Retrying in 3 seconds...")
                await asyncio.sleep(3.0)

    async def _handle_connection(self, ws):
        # Tasks: reader from serial -> ws, heartbeat loop, ws listener -> serial
        reader_task = asyncio.create_task(self._serial_reader_loop(ws))
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))

        try:
            async for msg in ws:
                data = json.loads(msg)
                action = data.get("action")

                if action == "CONNECT_HARDWARE":
                    req_port = data.get("port")
                    ok = self.open_serial(req_port)
                    self.engaged = ok
                    await ws.send(json.dumps({
                        "type": "ack",
                        "action": "CONNECT_HARDWARE",
                        "success": ok,
                        "port": self.current_port
                    }))

                elif action == "DISCONNECT_HARDWARE":
                    self.close_serial()
                    self.engaged = False
                    await ws.send(json.dumps({
                        "type": "ack",
                        "action": "DISCONNECT_HARDWARE",
                        "success": True
                    }))

                elif action == "COMMAND":
                    cmd = data.get("cmd", "")
                    if self.ser and self.ser.is_open and cmd:
                        try:
                            self.ser.write((cmd.strip() + "\n").encode('utf-8'))
                            self.ser.flush()
                            logger.info(f"Forwarded serial command to Arduino: {cmd.strip()}")
                        except Exception as e:
                            logger.error(f"Serial write error: {e}")

        finally:
            reader_task.cancel()
            heartbeat_task.cancel()
            self.close_serial()

    async def _serial_reader_loop(self, ws):
        loop = asyncio.get_running_loop()
        while True:
            if self.ser and self.ser.is_open:
                try:
                    # Non-blocking line read in thread
                    raw_line = await loop.run_in_executor(None, self.ser.readline)
                    if raw_line:
                        line = raw_line.decode('utf-8', errors='ignore').strip()
                        if line:
                            await ws.send(json.dumps({
                                "type": "telemetry",
                                "line": line,
                                "timestamp": time.time()
                            }))
                except Exception as e:
                    logger.debug(f"Serial read loop idle/err: {e}")
                    await asyncio.sleep(0.1)
            else:
                await asyncio.sleep(0.1)

    async def _heartbeat_loop(self, ws):
        while True:
            usb_port = find_arduino_port()
            payload = {
                "type": "heartbeat",
                "timestamp": time.time(),
                "usb_detected": (usb_port is not None),
                "port": usb_port or "NONE",
                "engaged": self.engaged and self.serial_open
            }
            try:
                await ws.send(json.dumps(payload))
            except Exception:
                break
            await asyncio.sleep(3.0)

if __name__ == "__main__":
    agent = HardwareNodeAgent()
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        logger.info("Agent terminated by user.")
