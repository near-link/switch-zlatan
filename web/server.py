"""
web/server.py
FastAPI Web Application & Central Edge Gateway for the Automated In-Wall Switch.
Provides REST API, real-time WebSocket telemetry streaming, and serves the web frontend.
"""

import os
import re
import hmac
import asyncio
import logging
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Request
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

class AuthVerifyModel(BaseModel):
    password: str

@app.post("/api/auth/verify")
async def verify_auth_endpoint(item: AuthVerifyModel):
    expected = os.getenv("WEB_PASSWORD", "123").strip().encode("utf-8")
    provided = item.password.strip().encode("utf-8")
    if hmac.compare_digest(provided, expected):
        return {"status": "success", "authenticated": True}
    # Artificial delay against automated brute-force attempts
    await asyncio.sleep(0.3)
    return JSONResponse(status_code=401, content={"status": "error", "authenticated": False, "detail": "Invalid passcode"})

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

@app.on_event("startup")
async def startup_event():
    init_db()
    manager.set_loop(asyncio.get_event_loop())
    bridge.register_callback(on_serial_telemetry)
    bridge.start()
    log_event("GATEWAY_START", "FastAPI Edge Gateway started and listening.")
    logger.info("Gateway initialization complete.")

@app.on_event("shutdown")
async def shutdown_event():
    bridge.stop()
    log_event("GATEWAY_STOP", "FastAPI Edge Gateway shutdown.")
    logger.info("Gateway stopped.")

# --- Pydantic Models ---
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

@app.post("/api/classes")
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

@app.delete("/api/classes/{session_id}")
async def delete_class_endpoint(session_id: int):
    delete_class_session(session_id)
    return {"status": "success", "deleted_id": session_id}

@app.post("/api/timetable/toggle")
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

@app.post("/api/timetable/preset")
async def apply_preset_endpoint(item: PresetScheduleModel):
    affected = apply_preset_schedule(
        building=item.building,
        level=item.level,
        room=item.room,
        scope=item.scope,
        preset=item.preset
    )
    return {"status": "success", "preset": item.preset, "affected_rooms": affected, "scope": item.scope}

@app.post("/api/timetable/clear-scope")
async def clear_scope_endpoint(item: ClearScopeModel):
    affected = clear_schedule_scope(
        building=item.building,
        level=item.level,
        room=item.room,
        scope=item.scope
    )
    return {"status": "success", "affected_rooms": affected, "scope": item.scope}

@app.post("/api/classes/clear")
async def clear_schedule_endpoint(room: str = "E1-2-14"):
    clear_room_schedule(room)
    return {"status": "success", "room": room}

@app.post("/api/import/imaluum")
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

@app.post("/api/policy")
async def update_policy_endpoint(item: PolicyUpdateModel):
    fom = item.force_on_minutes if item.force_on_minutes else 60
    update_policy(item.precool_minutes, item.grace_minutes, midnight_cutoff=item.midnight_cutoff, force_on_minutes=fom)
    try:
        sh, sm = [int(x) for x in (item.midnight_cutoff or "00:00").split(":")]
    except Exception:
        sh, sm = 0, 0
    bridge.send_command(f"SET_POLICY:{item.precool_minutes}:{item.grace_minutes}:{sh}:{sm}:{fom}")
    return {"status": "success", "policy": get_policy()}

@app.post("/api/deploy")
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

@app.post("/api/hardware/day")
async def set_hardware_day_endpoint(day: str = Query(..., description="Day code e.g. MON, TUE, WED, THU, FRI, SAT, SUN")):
    success = bridge.set_switch_day(day)
    if success:
        log_event("DAY_SET", f"Active switch day set to: {day}")
        return {"status": "success", "day": day}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/clock/sync")
async def sync_clock_endpoint():
    now = datetime.now()
    success = bridge.sync_time(now.hour, now.minute, now.second)
    if success:
        log_event("CLOCK_SYNC", f"Clock synced with server: {now.strftime('%H:%M:%S')}")
        return {"status": "success", "synced_time": now.strftime("%H:%M:%S")}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/clock/set")
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

@app.post("/api/override/toggle")
async def toggle_override_endpoint():
    success = bridge.manual_toggle()
    if success:
        log_event("MANUAL_TOGGLE", "Manual override toggled via web dashboard.")
        return {"status": "success", "action": "toggled"}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/override/auto")
async def auto_mode_endpoint():
    success = bridge.auto_mode()
    if success:
        log_event("AUTO_MODE", "Returned to schedule auto mode via web dashboard.")
        return {"status": "success", "action": "auto_mode"}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/override/force-on")
async def force_on_endpoint(item: Optional[ForceOnModel] = None):
    policy = get_policy()
    default_mins = policy.get("force_on_minutes", 60)
    mins = item.minutes if (item and item.minutes is not None) else default_mins
    success = bridge.force_on(minutes=mins)
    if success:
        log_event("OVERRIDE_FORCE_ON", f"Utilities forced ON for {mins} minutes via web dashboard.")
        return {"status": "success", "action": "force_on", "duration_minutes": mins}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/override/force-off")
async def force_off_endpoint():
    success = bridge.force_off()
    if success:
        log_event("OVERRIDE_FORCE_OFF", "Utilities forced OFF (early dismissal) via web dashboard.")
        return {"status": "success", "action": "force_off"}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/override/presentation")
async def presentation_endpoint():
    success = bridge.presentation_mode()
    if success:
        log_event("OVERRIDE_PRESENTATION", "Presentation mode engaged (Lights OFF, AC ON) via web dashboard.")
        return {"status": "success", "action": "presentation"}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/speed")
async def set_speed_endpoint(item: SpeedSetModel):
    success = bridge.set_speed(item.factor)
    if success:
        log_event("SPEED_SET", f"Speed multiplier set to {item.factor}x")
        return {"status": "success", "speed_factor": item.factor}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/hardware/beep")
async def beep_endpoint(freq: int = 2200, duration: int = 100):
    success = bridge.beep(freq=freq, duration=duration)
    if success:
        log_event("BUZZER_TEST", f"Auditory alert test emitted ({freq}Hz, {duration}ms).")
        return {"status": "success", "action": "beep", "frequency": freq, "duration": duration}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.post("/api/diagnostics/command")
async def raw_command_endpoint(item: RawCommandModel):
    cmd = item.command.strip()
    if not re.match(r"^[A-Za-z0-9_:,\-\. ]+$", cmd) or len(cmd) > 64:
        raise HTTPException(status_code=400, detail="Invalid or unsafe serial command syntax.")
    success = bridge.send_command(cmd)
    if success:
        log_event("RAW_SERIAL_CMD", f"Dispatched: {cmd}")
        return {"status": "success", "command": cmd}
    raise HTTPException(status_code=503, detail="Serial connection unavailable.")

@app.get("/api/logs")
async def get_logs_endpoint(limit: int = 50):
    return get_audit_logs(limit)

# --- WebSocket Telemetry Stream ---
@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
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