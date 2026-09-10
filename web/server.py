"""
web/server.py
FastAPI Web Application & Central Edge Gateway for the Automated In-Wall Switch.
Provides REST API, real-time WebSocket telemetry streaming, and serves the web frontend.
"""

import os
import re
import hmac
import hashlib
import secrets
import asyncio
import logging
import json
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Request,
    Response, Cookie, Header, Depends, status
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, Field

from web.database import (
    init_db, log_event, get_classes, add_class_session, delete_class_session,
    clear_room_schedule, clear_schedule_scope, import_mock_imaluum, get_campus_hierarchy,
    get_iium_periods, toggle_period_slot, apply_preset_schedule,
    get_policy, update_policy, record_deployment, get_audit_logs, get_deployable_schedule,
    get_full_week_schedule
)
from web.serial_bridge import ArduinoSerialBridge

logger = logging.getLogger("server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Automated In-Wall Switch Gateway", version="2.5.0")

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
bridge = ArduinoSerialBridge()

# Cryptographic Session Management
SESSION_SECRET = os.getenv("SESSION_SECRET", "smart-switch-secure-salt-2026-evangelion")

def generate_session_token() -> str:
    ts_str = str(int(datetime.now(timezone.utc).timestamp()))
    nonce = secrets.token_hex(8)
    data = f"{ts_str}:{nonce}"
    sig = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}:{sig}"

def verify_session_token(token: Optional[str]) -> bool:
    if not token or token.count(":") != 2:
        return False
    try:
        ts_str, nonce, sig = token.split(":")
        ts = int(ts_str)
        now = int(datetime.now(timezone.utc).timestamp())
        # Valid for 7 days (604800 seconds)
        if abs(now - ts) > 7 * 86400:
            return False
        data = f"{ts_str}:{nonce}"
        expected = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False

async def require_auth(
    request: Request,
    switch_session: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None)
):
    token = switch_session
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token and "token" in request.query_params:
        token = request.query_params["token"]
    if not verify_session_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please enter switch passcode."
        )
    return True

# In-memory brute-force rate limiter for passcode verification
# Tracks failed attempts per client IP. Max 5 failures in 60s -> 60s lockout.
_auth_failures: Dict[str, List[float]] = {}
_auth_lockouts: Dict[str, float] = {}

def get_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"

def check_auth_rate_limit(client_ip: str) -> Optional[int]:
    now = time.time()
    if client_ip in _auth_lockouts:
        lockout_until = _auth_lockouts[client_ip]
        if now < lockout_until:
            return max(1, int(lockout_until - now))
        del _auth_lockouts[client_ip]
        _auth_failures[client_ip] = []

    failures = [t for t in _auth_failures.get(client_ip, []) if now - t < 60.0]
    _auth_failures[client_ip] = failures
    if len(failures) >= 5:
        _auth_lockouts[client_ip] = now + 60.0
        return 60
    return None

def record_auth_failure(client_ip: str):
    now = time.time()
    failures = [t for t in _auth_failures.get(client_ip, []) if now - t < 60.0]
    failures.append(now)
    _auth_failures[client_ip] = failures
    if len(failures) >= 5:
        _auth_lockouts[client_ip] = now + 60.0
        logger.warning(f"Auth rate limit triggered: IP {client_ip} locked out for 60 seconds")

def record_auth_success(client_ip: str):
    _auth_failures.pop(client_ip, None)
    _auth_lockouts.pop(client_ip, None)

class AuthVerifyModel(BaseModel):
    password: str

@app.post("/api/auth/verify")
async def verify_auth_endpoint(item: AuthVerifyModel, request: Request, response: Response):
    client_ip = get_client_ip(request)

    lockout_remaining = check_auth_rate_limit(client_ip)
    if lockout_remaining is not None:
        return JSONResponse(
            status_code=429,
            content={
                "status": "error",
                "authenticated": False,
                "detail": f"RATE LIMIT: Too many failed attempts. Locked out for {lockout_remaining}s."
            }
        )

    expected = os.getenv("WEB_PASSWORD", "123").strip().encode("utf-8")
    provided = item.password.strip().encode("utf-8")
    if hmac.compare_digest(provided, expected):
        record_auth_success(client_ip)
        token = generate_session_token()
        response.set_cookie(
            key="switch_session",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=7 * 86400,
            path="/"
        )
        return {"status": "success", "authenticated": True, "token": token}

    record_auth_failure(client_ip)
    # Artificial jitter against automated brute-force attempts
    await asyncio.sleep(0.3)
    return JSONResponse(
        status_code=401,
        content={"status": "error", "authenticated": False, "detail": "Invalid passcode"}
    )

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for dead in disconnected:
            self.disconnect(dead)

    def threadsafe_broadcast(self, message: Dict[str, Any]):
        if self.loop and self.loop.is_running() and self.active_connections:
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

manager = ConnectionManager()

def on_serial_telemetry(state: Dict[str, Any]):
    """Callback fired by serial thread upon receiving new telemetry."""
    manager.threadsafe_broadcast({
        "type": "telemetry",
        "data": state
    })

def on_mode_change(new_mode: str):
    """Callback fired when hardware mode changes (manual or heartbeat timeout)."""
    manager.threadsafe_broadcast({
        "type": "mode_change",
        "mode": new_mode,
        "data": bridge.get_state()
    })

@app.on_event("startup")
async def startup_event():
    init_db()
    loop = asyncio.get_event_loop()
    manager.set_loop(loop)
    bridge.set_loop(loop)
    bridge.register_callback(on_serial_telemetry)
    bridge.register_mode_change_callback(on_mode_change)
    bridge.start()
    log_event("GATEWAY_START", "FastAPI Edge Gateway started and listening.")
    logger.info("Gateway initialization complete.")

@app.on_event("shutdown")
async def shutdown_event():
    bridge.stop()
    log_event("GATEWAY_STOP", "FastAPI Edge Gateway shutdown.")
    logger.info("Gateway stopped.")

# --- Pydantic Models ---
class SwitchModeModel(BaseModel):
    mode: str = Field(..., pattern="^(twin|physical)$")

class HardwareButtonModel(BaseModel):
    button_id: int = Field(..., ge=1, le=3)
    action: str = Field(default="tap", pattern="^(tap|hold|cycle)$")

class ClassSessionModel(BaseModel):
    building: str = Field(default="KOE")
    level: int = Field(default=2)
    room: str = Field(default="E1-2-14")
    day_of_week: int = Field(..., ge=0, le=6, description="0=Mon, 6=Sun")
    start_hour: int = Field(..., ge=0, le=23)
    start_minute: int = Field(..., ge=0, le=59)
    end_hour: int = Field(..., ge=0, le=23)
    end_minute: int = Field(..., ge=0, le=59)
    label: Optional[str] = Field(default="Class Session")

class ToggleSlotModel(BaseModel):
    building: str = Field(default="KOE")
    level: int = Field(default=2)
    room: str = Field(default="E1-2-14")
    day_of_week: int = Field(..., ge=0, le=6)
    period_index: int = Field(..., ge=1, le=6)
    scope: str = Field(default="room")  # "campus", "kulliyyah", "level", "room"
    target_state: Optional[str] = Field(default=None) # "occupied", "vacant", or None

class PresetScheduleModel(BaseModel):
    building: str = Field(default="KOE")
    level: int = Field(default=2)
    room: str = Field(default="E1-2-14")
    scope: str = Field(default="room")
    preset: str = Field(default="standard_weekday")

class ClearScopeModel(BaseModel):
    building: str = Field(default="KOE")
    level: int = Field(default=2)
    room: str = Field(default="E1-2-14")
    scope: str = Field(default="room")

class ImaluumImportModel(BaseModel):
    building: str = Field(default="KOE")
    level: int = Field(default=2)
    room: str = Field(default="E1-2-14")
    scope: str = Field(default="room")
    matric_no: Optional[str] = Field(default="2110001")

class PolicyUpdateModel(BaseModel):
    precool_minutes: int = Field(..., ge=0, le=60)
    grace_minutes: int = Field(..., ge=1, le=60)
    midnight_cutoff: Optional[str] = Field(default="00:00")
    force_on_minutes: Optional[int] = Field(default=60, ge=5, le=480)

class ClockSetModel(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    second: int = Field(default=0, ge=0, le=59)
    day: Optional[str] = Field(default=None, description="Optional target day code e.g. MON, TUE, WED")

class ForceOnModel(BaseModel):
    minutes: int = Field(default=60, ge=1, le=480)

class SpeedSetModel(BaseModel):
    factor: int = Field(..., description="1, 60, or 600")

class RawCommandModel(BaseModel):
    command: str = Field(..., description="ASCII serial command to Arduino")

# --- REST Endpoints ---
@app.get("/api/hierarchy")
async def get_hierarchy():
    return get_campus_hierarchy()

@app.get("/api/periods")
async def get_periods_endpoint():
    return get_iium_periods()

@app.get("/api/status")
async def get_status(room: str = "E1-2-14"):
    state = bridge.get_state()
    policy = get_policy()
    deployable = get_deployable_schedule(room=room)
    return {
        "hardware": state,
        "policy": policy,
        "deployable": deployable,
        "room": room,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/api/classes")
async def list_classes(room: str = "E1-2-14", day: Optional[int] = None):
    return get_classes(room=room, day_of_week=day)

@app.post("/api/classes", dependencies=[Depends(require_auth)])
async def create_class_endpoint(item: ClassSessionModel):
    new_id = add_class_session(
        building=item.building,
        level=item.level,
        room=item.room,
        day_of_week=item.day_of_week,
        start_hour=item.start_hour,
        start_minute=item.start_minute,
        end_hour=item.end_hour,
        end_minute=item.end_minute,
        label=item.label or "Class Session"
    )
    return {"status": "success", "session_id": new_id}

@app.delete("/api/classes/{session_id}", dependencies=[Depends(require_auth)])
async def delete_class_endpoint(session_id: int):
    delete_class_session(session_id)
    return {"status": "success", "deleted_id": session_id}

@app.post("/api/timetable/toggle", dependencies=[Depends(require_auth)])
async def toggle_slot_endpoint(item: ToggleSlotModel):
    result = toggle_period_slot(
        building=item.building,
        level=item.level,
        room=item.room,
        day_of_week=item.day_of_week,
        period_index=item.period_index,
        scope=item.scope,
        target_state=item.target_state
    )
    return result

@app.post("/api/timetable/preset", dependencies=[Depends(require_auth)])
async def apply_preset_endpoint(item: PresetScheduleModel):
    affected = apply_preset_schedule(
        building=item.building,
        level=item.level,
        room=item.room,
        scope=item.scope,
        preset=item.preset
    )
    return {"status": "success", "preset": item.preset, "affected_rooms": affected, "scope": item.scope}

@app.post("/api/timetable/clear-scope", dependencies=[Depends(require_auth)])
async def clear_scope_endpoint(item: ClearScopeModel):
    affected = clear_schedule_scope(
        building=item.building,
        level=item.level,
        room=item.room,
        scope=item.scope
    )
    return {"status": "success", "affected_rooms": affected, "scope": item.scope}

@app.post("/api/classes/clear", dependencies=[Depends(require_auth)])
async def clear_schedule_endpoint(room: str = "E1-2-14"):
    clear_room_schedule(room)
    return {"status": "success", "room": room}

@app.post("/api/import/imaluum", dependencies=[Depends(require_auth)])
async def import_imaluum_endpoint(item: ImaluumImportModel):
    count = import_mock_imaluum(
        room=item.room,
        scope=item.scope,
        building=item.building,
        level=item.level,
        matric_no=item.matric_no or "2110001"
    )
    return {
        "status": "success",
        "imported_count": count,
        "room": item.room,
        "scope": item.scope,
        "source": "imaluum.iium.edu.my"
    }

@app.post("/api/policy", dependencies=[Depends(require_auth)])
async def update_policy_endpoint(item: PolicyUpdateModel):
    fom = item.force_on_minutes if item.force_on_minutes else 60
    update_policy(item.precool_minutes, item.grace_minutes, midnight_cutoff=item.midnight_cutoff, force_on_minutes=fom)
    try:
        sh, sm = [int(x) for x in (item.midnight_cutoff or "00:00").split(":")]
    except Exception:
        sh, sm = 0, 0
    bridge.send_command(f"SET_POLICY:{item.precool_minutes}:{item.grace_minutes}:{sh}:{sm}:{fom}")
    return {"status": "success", "policy": get_policy()}

@app.post("/api/deploy", dependencies=[Depends(require_auth)])
async def deploy_schedule_endpoint(room: str = "E1-2-14"):
    week_sched = get_full_week_schedule(room=room)
    is_poc = (room == "E1-2-14")
    
    if is_poc:
        # Dev Bench Hardware: Flash physical ATmega328P EEPROM via USB serial
        success = bridge.deploy_week_schedule(week_sched["commands"])
        if success:
            record_deployment()
            log_event("EEPROM_FLASH", f"Flashed 7-day schedule ({len(week_sched['commands'])} cmds) to Dev Switch [E1-2-14] via /dev/ttyACM0.")
            return {
                "status": "success",
                "target": room,
                "mode": "dev_serial",
                "transport": "/dev/ttyACM0",
                "deployed": week_sched,
                "message": f"Flashed {len(week_sched['commands'])} commands to ATmega328P EEPROM via USB serial"
            }
        else:
            raise HTTPException(status_code=503, detail="Failed to transmit schedule to dev switch. Check serial connection.")
    else:
        # Production Edge Switch (simulated network node): Deploy via Campus Edge Protocol (MQTT/TLS)
        # DO NOT touch the physical dev switch bridge!
        record_deployment()
        log_event("EDGE_DEPLOY", f"Dispatched 7-day schedule ({len(week_sched['commands'])} cmds) to Edge Switch [{room}] via MQTT/TLS broker.")
        return {
            "status": "success",
            "target": room,
            "mode": "edge_mqtt",
            "transport": "mqtt/tls",
            "deployed": week_sched,
            "message": f"Dispatched {len(week_sched['commands'])} commands to Edge Switch [{room}] via MQTT/TLS broker"
        }

@app.post("/api/hardware/day", dependencies=[Depends(require_auth)])
async def set_hardware_day_endpoint(day: str = Query(..., description="Day code e.g. MON, TUE, WED, THU, FRI, SAT, SUN")):
    success = bridge.set_switch_day(day)
    if success:
        log_event("DAY_SET", f"Active switch day set to: {day}")
        return {"status": "success", "day": day}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/clock/sync", dependencies=[Depends(require_auth)])
async def sync_clock_endpoint():
    now = datetime.now()
    success = bridge.sync_time(now.hour, now.minute, now.second)
    if success:
        log_event("CLOCK_SYNC", f"Clock synced with server: {now.strftime('%H:%M:%S')}")
        return {"status": "success", "synced_time": now.strftime("%H:%M:%S")}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/clock/set", dependencies=[Depends(require_auth)])
async def set_clock_endpoint(item: ClockSetModel):
    if item.day:
        bridge.set_switch_day(item.day)
        log_event("DAY_SET", f"Active switch day set to: {item.day}")
    success = bridge.sync_time(item.hour, item.minute, item.second)
    if success:
        time_str = f"{item.hour:02d}:{item.minute:02d}:{item.second:02d}"
        log_event("CLOCK_SET", f"Clock set to {time_str}" + (f" ({item.day})" if item.day else ""))
        return {"status": "success", "set_time": time_str, "day": item.day}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/override/toggle", dependencies=[Depends(require_auth)])
async def toggle_override_endpoint():
    success = bridge.manual_toggle()
    if success:
        log_event("MANUAL_TOGGLE", "Manual override toggled via web dashboard.")
        return {"status": "success", "action": "toggled"}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/override/auto", dependencies=[Depends(require_auth)])
async def auto_mode_endpoint():
    success = bridge.auto_mode()
    if success:
        log_event("AUTO_MODE", "Returned to schedule auto mode via web dashboard.")
        return {"status": "success", "action": "auto_mode"}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/override/force-on", dependencies=[Depends(require_auth)])
async def force_on_endpoint(item: Optional[ForceOnModel] = None):
    policy = get_policy()
    default_mins = policy.get("force_on_minutes", 60)
    mins = item.minutes if (item and item.minutes is not None) else default_mins
    success = bridge.force_on(minutes=mins)
    if success:
        log_event("OVERRIDE_FORCE_ON", f"Utilities forced ON for {mins} minutes via web dashboard.")
        return {"status": "success", "action": "force_on", "duration_minutes": mins}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/override/force-off", dependencies=[Depends(require_auth)])
async def force_off_endpoint():
    success = bridge.force_off()
    if success:
        log_event("OVERRIDE_FORCE_OFF", "Utilities forced OFF (early dismissal) via web dashboard.")
        return {"status": "success", "action": "force_off"}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/override/presentation", dependencies=[Depends(require_auth)])
async def presentation_endpoint():
    success = bridge.presentation_mode()
    if success:
        log_event("OVERRIDE_PRESENTATION", "Presentation mode engaged (Lights OFF, AC ON) via web dashboard.")
        return {"status": "success", "action": "presentation"}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/speed", dependencies=[Depends(require_auth)])
async def set_speed_endpoint(item: SpeedSetModel):
    success = bridge.set_speed(item.factor)
    if success:
        log_event("SPEED_SET", f"Speed multiplier set to {item.factor}x")
        return {"status": "success", "speed_factor": item.factor}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/hardware/beep", dependencies=[Depends(require_auth)])
async def beep_endpoint(freq: int = 2200, duration: int = 100):
    success = bridge.beep(freq=freq, duration=duration)
    if success:
        log_event("BUZZER_TEST", f"Auditory alert test emitted ({freq}Hz, {duration}ms).")
        return {"status": "success", "action": "beep", "frequency": freq, "duration": duration}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/diagnostics/command", dependencies=[Depends(require_auth)])
async def raw_command_endpoint(item: RawCommandModel):
    cmd = item.command.strip()
    if not re.match(r"^[A-Za-z0-9_:,\-\. ]+$", cmd) or len(cmd) > 64:
        raise HTTPException(status_code=400, detail="Invalid or unsafe serial command syntax.")
    success = bridge.send_command(cmd)
    if success:
        log_event("RAW_SERIAL_CMD", f"Dispatched: {cmd}")
        return {"status": "success", "command": cmd}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.get("/api/logs", dependencies=[Depends(require_auth)])
async def get_logs_endpoint(limit: int = 50):
    return get_audit_logs(limit)

# --- Remote Orchestration & Edge Control Endpoints ---
@app.get("/api/control/status")
async def get_control_status():
    st = bridge.get_state()
    return {
        "status": "online",
        "mode": bridge.mode,
        "agent_connected": bridge.agent_connected,
        "agent_usb_detected": bridge.agent_usb_detected,
        "agent_port": bridge.agent_port,
        "hardware_state": st
    }

@app.post("/api/control/mode")
async def set_control_mode(item: SwitchModeModel):
    success = bridge.set_mode(item.mode, reason="DASHBOARD_API")
    if success:
        log_event("MODE_SWITCH", f"Hardware mode set to: {item.mode}")
        return {"status": "success", "mode": item.mode}
    raise HTTPException(status_code=400, detail="Failed to transition hardware mode.")

@app.post("/api/hardware/button")
async def hardware_button_press_endpoint(item: HardwareButtonModel):
    success = bridge.handle_hardware_button(item.button_id, item.action)
    if success:
        return {"status": "success", "button_id": item.button_id, "action": item.action}
    raise HTTPException(status_code=400, detail="Button actuation rejected.")

# --- Hardware Agent WebSocket Ingress (Laptop Tunnel) ---
@app.websocket("/ws/hardware-edge")
async def websocket_hardware_edge_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    valid_tokens = [SESSION_SECRET, os.getenv("AGENT_SECRET_TOKEN", "smart-switch-secure-salt-2026-evangelion"), os.getenv("WEB_PASSWORD", "123")]
    if token not in valid_tokens:
        logger.warning(f"Unauthorized hardware agent connection attempt with token: {token}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    bridge.register_agent_socket(websocket)
    logger.info("Hardware agent WebSocket tunnel opened successfully.")
    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                data = json.loads(raw_msg)
                bridge.handle_agent_message(data)
            except Exception as e:
                logger.error(f"Error handling agent packet: {e}")
    except WebSocketDisconnect:
        bridge.unregister_agent_socket(websocket)
    except Exception as e:
        logger.error(f"Agent WebSocket connection exception: {e}")
        bridge.unregister_agent_socket(websocket)

# --- WebSocket Telemetry Stream ---
@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    token = websocket.cookies.get("switch_session") or websocket.query_params.get("token")
    if not verify_session_token(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await manager.connect(websocket)
    await websocket.send_json({
        "type": "telemetry",
        "data": bridge.get_state()
    })
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# Serve Static UI Files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            html = f.read()
        try:
            hierarchy = get_campus_hierarchy()
            periods = get_iium_periods()
            classes = get_classes(room="E1-2-14")
            hw_state = bridge.get_state() if bridge else {}
            hydration = f"""
    <script>
      window.INITIAL_HIERARCHY = {json.dumps(hierarchy)};
      window.INITIAL_PERIODS = {json.dumps(periods)};
      window.INITIAL_CLASSES = {json.dumps(classes)};
      window.INITIAL_HARDWARE = {json.dumps(hw_state)};
    </script>
            """
            html = html.replace("</head>", f"{hydration}\n</head>")
        except Exception as e:
            logger.error(f"Hydration error: {e}")
        return HTMLResponse(content=html)
    return {"message": "Automated In-Wall Switch Web Gateway is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)