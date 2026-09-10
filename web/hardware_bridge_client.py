"""
web/hardware_bridge_client.py
Lightweight workstation bridge connecting the physical Arduino Uno to the 24/7 cloud switch gateway.
Pipes physical serial telemetry (TLM) up to the cloud and routes cloud web commands down to the Arduino.
"""

import os
import sys
import time
import argparse
import asyncio
import signal
import glob
import logging
from typing import Optional

import serial
import serial.tools.list_ports
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("hardware_bridge")

def find_arduino_port(preferred: str = "/dev/ttyACM0") -> str:
    if os.path.exists(preferred):
        return preferred
    ports = [p.device for p in serial.tools.list_ports.comports()]
    for p in ports:
        if "ACM" in p or "USB" in p or "Arduino" in p:
            return p
    matches = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
    if matches:
        return matches[0]
    return preferred

class HardwareBridgeClient:
    def __init__(self, port: str, baud: int, url: str, token: str):
        self.port = port
        self.baud = baud
        self.url = url
        self.token = token
        self.running = True
        self.ser: Optional[serial.Serial] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None

    def connect_serial(self) -> bool:
        target = find_arduino_port(self.port)
        try:
            logger.info(f"Opening serial port {target} @ {self.baud} baud...")
            self.ser = serial.Serial(target, self.baud, timeout=0.2)
            time.sleep(1.8)  # Bootloader initialization delay
            self.port = target
            logger.info(f"[+] Physical Arduino Uno locked on {target}")
            return True
        except Exception as e:
            logger.error(f"[-] Failed to open serial port {target}: {e}")
            self.ser = None
            return False

    async def serial_reader_loop(self):
        loop = asyncio.get_event_loop()
        while self.running:
            if not self.ser or not self.ser.is_open:
                await asyncio.sleep(1.0)
                continue
            try:
                # Read line from serial in thread executor
                raw_line = await loop.run_in_executor(None, self.ser.readline)
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                # Forward physical line to cloud WebSocket
                if self.ws:
                    await self.ws.send(line)
                    if line.startswith("TLM:"):
                        # Log heartbeat at concise cadence
                        parts = line[4:].split(",")
                        if len(parts) >= 5:
                            logger.info(f"Physical TLM -> Time: {parts[0]}, State: {parts[1]}, Relays(Y/B/R): {parts[2]}/{parts[3]}/{parts[4]}")
                    else:
                        logger.info(f"Arduino Event -> {line}")
            except Exception as e:
                logger.warning(f"Serial read error: {e}")
                await asyncio.sleep(1.0)

    async def ws_receiver_loop(self):
        while self.running and self.ws:
            try:
                cmd = await self.ws.recv()
                clean_cmd = cmd.strip()
                if not clean_cmd:
                    continue
                logger.info(f"[Cloud Actuation] Received Command -> {clean_cmd}")
                if self.ser and self.ser.is_open:
                    self.ser.write((clean_cmd + "\n").encode("utf-8"))
                    self.ser.flush()
                    logger.info(f"[+] Written to Arduino -> {clean_cmd}")
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Cloud WebSocket closed connection.")
                break
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                break

    async def run(self):
        # 1. Connect physical Arduino
        while self.running and not self.ser:
            if not self.connect_serial():
                logger.info("Retrying serial discovery in 2 seconds...")
                await asyncio.sleep(2.0)

        connect_url = f"{self.url}?token={self.token}"
        logger.info(f"Connecting to Cloud Switch: {self.url}...")

        while self.running:
            try:
                async with websockets.connect(connect_url, ping_interval=20, ping_timeout=10) as ws:
                    self.ws = ws
                    logger.info("=================================================")
                    logger.info("   Physical Hardware Bridge LINK ACTIVE")
                    logger.info(f"   Device:  {self.port} (Arduino Uno R3)")
                    logger.info(f"   Gateway: {self.url}")
                    logger.info("=================================================")
                    logger.info("[*] Physical relays and buttons are now live on https://switch.imankh.me")

                    reader_task = asyncio.create_task(self.serial_reader_loop())
                    receiver_task = asyncio.create_task(self.ws_receiver_loop())

                    done, pending = await asyncio.wait(
                        [reader_task, receiver_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for t in pending:
                        t.cancel()
            except (websockets.exceptions.WebSocketException, OSError) as e:
                logger.warning(f"Cloud connection dropped ({e}). Reconnecting in 3s...")
                self.ws = None
                await asyncio.sleep(3.0)
            except asyncio.CancelledError:
                break

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                logger.info("Serial port closed cleanly.")
            except Exception:
                pass
            self.ser = None

def main():
    parser = argparse.ArgumentParser(description="Automated In-Wall Switch Laptop Hardware Bridge")
    parser.add_argument("--port", default=os.getenv("SERIAL_PORT", "/dev/ttyACM0"), help="Serial port")
    parser.add_argument("--baud", type=int, default=int(os.getenv("SERIAL_BAUD", "9600")), help="Baud rate")
    parser.add_argument("--url", default=os.getenv("GATEWAY_URL", "wss://switch.imankh.me/ws/hardware-bridge"), help="WebSocket URL")
    parser.add_argument("--token", default=os.getenv("WEB_PASSWORD", "123"), help="Security Token")
    args = parser.parse_args()

    client = HardwareBridgeClient(args.port, args.baud, args.url, args.token)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def sig_handler():
        logger.info("\n[*] Disconnecting hardware bridge...")
        client.stop()
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, sig_handler)

    try:
        loop.run_until_complete(client.run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        client.stop()
        loop.close()
        logger.info("[*] Hardware Bridge disconnected. Cloud switch returned to virtual mode.")

if __name__ == "__main__":
    main()
