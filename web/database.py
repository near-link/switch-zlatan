"""
web/database.py
SQLite persistence layer for the Automated In-Wall Switch Timetable Maker & Edge Gateway.
Stores campus room hierarchies, weekly academic schedules, energy policies, and audit logs.
"""

import sqlite3
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

MALAYSIA_TZ = timezone(timedelta(hours=8))

DB_PATH = os.path.join(os.path.dirname(__file__), "timetable.db")

# Standard IIUM Academic Class Periods
IIUM_PERIODS = [
    {"index": 1, "code": "P1", "start_h": 8, "start_m": 30, "end_h": 10, "end_m": 0, "time_str": "08:30 - 10:00"},
    {"index": 2, "code": "P2", "start_h": 10, "start_m": 0, "end_h": 11, "end_m": 30, "time_str": "10:00 - 11:30"},
    {"index": 3, "code": "P3", "start_h": 11, "start_m": 30, "end_h": 13, "end_m": 0, "time_str": "11:30 - 13:00"},
    {"index": 4, "code": "P4", "start_h": 14, "start_m": 0, "end_h": 15, "end_m": 30, "time_str": "14:00 - 15:30"},
    {"index": 5, "code": "P5", "start_h": 15, "start_m": 30, "end_h": 17, "end_m": 0, "time_str": "15:30 - 17:00"},
    {"index": 6, "code": "P6", "start_h": 17, "start_m": 0, "end_h": 18, "end_m": 30, "time_str": "17:00 - 18:30"}
]

def get_iium_periods() -> List[Dict[str, Any]]:
    return IIUM_PERIODS

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema and seeds default campus hierarchy & timetable."""
    conn = get_db()
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 20000;")
    except Exception:
        pass
    cursor = conn.cursor()

    # Classes / Occupied Sessions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building TEXT NOT NULL DEFAULT 'KOE',
            level INTEGER NOT NULL DEFAULT 2,
            room TEXT NOT NULL DEFAULT 'E1-2-14',
            label TEXT DEFAULT 'Class Session',
            day_of_week INTEGER NOT NULL, -- 0=Monday, 6=Sunday
            start_hour INTEGER NOT NULL,
            start_minute INTEGER NOT NULL,
            end_hour INTEGER NOT NULL,
            end_minute INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Policy Configuration Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY,
            precool_minutes INTEGER DEFAULT 10,
            grace_minutes INTEGER DEFAULT 10,
            speed_factor INTEGER DEFAULT 1,
            midnight_cutoff TEXT DEFAULT '00:00',
            force_on_minutes INTEGER DEFAULT 60,
            last_deployed_at TIMESTAMP
        )
    """)

    # Migration: Ensure columns exist if table already existed
    try:
        cursor.execute("ALTER TABLE policies ADD COLUMN midnight_cutoff TEXT DEFAULT '00:00'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE policies ADD COLUMN force_on_minutes INTEGER DEFAULT 60")
    except sqlite3.OperationalError:
        pass

    # Audit & Energy Log Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            state TEXT
        )
    """)

    # Seed Default Policies
    cursor.execute("SELECT COUNT(*) FROM policies")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO policies (id, precool_minutes, grace_minutes, speed_factor)
            VALUES (1, 10, 10, 1)
        """)

    # Seed Default Schedule for E1-2-14 if table is empty
    cursor.execute("SELECT COUNT(*) FROM classes")
    if cursor.fetchone()[0] == 0:
        seed_default_classes(cursor)

    conn.commit()
    conn.close()

def seed_default_classes(cursor):
    default_sessions = [
        ("KOE", 2, "E1-2-14", "Class Session", 0, 8, 30, 10, 0),   # Mon P1
        ("KOE", 2, "E1-2-14", "Class Session", 0, 14, 0, 16, 30),  # Mon P4-P5
        ("KOE", 2, "E1-2-14", "Class Session", 1, 10, 0, 11, 30),  # Tue P2
        ("KOE", 2, "E1-2-14", "Class Session", 2, 8, 30, 10, 0),   # Wed P1
        ("KOE", 2, "E1-2-14", "Class Session", 2, 14, 0, 16, 0),   # Wed P4
        ("KOE", 2, "E1-2-14", "Class Session", 3, 11, 30, 13, 0),  # Thu P3
        ("KOE", 2, "E1-2-14", "Class Session", 4, 9, 0, 11, 30)    # Fri
    ]
    cursor.executemany("""
        INSERT INTO classes (building, level, room, label, day_of_week, start_hour, start_minute, end_hour, end_minute)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, default_sessions)

def get_campus_hierarchy() -> Dict[str, Any]:
    """Returns the campus building, level, and room structure with real IIUM Kulliyyahs."""
    kulliyyahs = [
        {
            "id": "KOE",
            "name": "KOE // Kulliyyah of Engineering",
            "levels": [
                {
                    "level": 1,
                    "rooms": [
                        {"id": "E1-1-01", "name": "E1-1-01 Lecture Hall", "has_hardware": False},
                        {"id": "E1-1-08", "name": "E1-1-08 Computing Lab", "has_hardware": False}
                    ]
                },
                {
                    "level": 2,
                    "rooms": [
                        {"id": "E1-2-14", "name": "E1-2-14 Embedded Systems Lab [POC HARDWARE]", "has_hardware": True},
                        {"id": "E1-2-15", "name": "E1-2-15 Electronics Lab", "has_hardware": False},
                        {"id": "E1-2-16", "name": "E1-2-16 Seminar Room", "has_hardware": False}
                    ]
                },
                {
                    "level": 3,
                    "rooms": [
                        {"id": "E1-3-02", "name": "E1-3-02 Postgraduate Lab", "has_hardware": False},
                        {"id": "E1-3-05", "name": "E1-3-05 Department Meeting", "has_hardware": False}
                    ]
                }
            ]
        },
        {
            "id": "KICT",
            "name": "KICT // Information & Communication Tech",
            "levels": [
                {
                    "level": 1,
                    "rooms": [
                        {"id": "A-1-02", "name": "A-1-02 Networking Lab", "has_hardware": False},
                        {"id": "A-1-05", "name": "A-1-05 Software Studio", "has_hardware": False}
                    ]
                },
                {
                    "level": 2,
                    "rooms": [
                        {"id": "B-2-04", "name": "B-2-04 Cybersecurity Lab", "has_hardware": False}
                    ]
                }
            ]
        },
        {
            "id": "KENMS",
            "name": "KENMS // Economics & Management Sciences",
            "levels": [
                {
                    "level": 1,
                    "rooms": [
                        {"id": "KENMS-1-01", "name": "KENMS-1-01 Main Auditorium", "has_hardware": False},
                        {"id": "KENMS-1-04", "name": "KENMS-1-04 Finance Lab", "has_hardware": False}
                    ]
                }
            ]
        },
        {
            "id": "AIKOL",
            "name": "AIKOL // Ahmad Ibrahim Kulliyyah of Laws",
            "levels": [
                {
                    "level": 1,
                    "rooms": [
                        {"id": "AIKOL-1-01", "name": "AIKOL-1-01 Moot Court Alpha", "has_hardware": False},
                        {"id": "AIKOL-1-05", "name": "AIKOL-1-05 Law Seminar Hall", "has_hardware": False}
                    ]
                }
            ]
        },
        {
            "id": "KIRKHS",
            "name": "KIRKHS // Islamic Revealed Knowledge & Human Sciences",
            "levels": [
                {
                    "level": 1,
                    "rooms": [
                        {"id": "HS-1-03", "name": "HS-1-03 Lecture Hall 1", "has_hardware": False},
                        {"id": "HS-2-08", "name": "HS-2-08 Audio Visual Theatre", "has_hardware": False}
                    ]
                }
            ]
        },
        {
            "id": "KAED",
            "name": "KAED // Architecture & Environmental Design",
            "levels": [
                {
                    "level": 1,
                    "rooms": [
                        {"id": "KAED-1-01", "name": "KAED-1-01 Architecture Studio", "has_hardware": False}
                    ]
                }
            ]
        }
    ]
    return {
        "kulliyyahs": kulliyyahs,
        "buildings": kulliyyahs  # backward-compatible alias
    }

def get_rooms_for_scope(scope: str = "room", building: str = "KOE", level: int = 2, room: str = "E1-2-14") -> List[Dict[str, Any]]:
    """Resolves which rooms belong to a specified broadcast scope."""
    hierarchy = get_campus_hierarchy()
    matched = []
    for k in hierarchy["kulliyyahs"]:
        if scope in ("kulliyyah", "level", "room") and k["id"] != building:
            continue
        for lvl in k["levels"]:
            if scope in ("level", "room") and lvl["level"] != level:
                continue
            for rm in lvl["rooms"]:
                if scope == "room" and rm["id"] != room:
                    continue
                matched.append({
                    "building": k["id"],
                    "level": lvl["level"],
                    "room": rm["id"]
                })
    return matched if matched else [{"building": building, "level": level, "room": room}]

def log_event(event_type: str, message: str, state: Optional[str] = None):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO audit_logs (event_type, message, state) VALUES (?, ?, ?)",
            (event_type, message, state)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging event: {e}")

def get_classes(room: str = "E1-2-14", day_of_week: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    if day_of_week is not None:
        cursor.execute(
            "SELECT * FROM classes WHERE room = ? AND day_of_week = ? AND is_active = 1 ORDER BY start_hour ASC, start_minute ASC",
            (room, day_of_week)
        )
    else:
        cursor.execute(
            "SELECT * FROM classes WHERE room = ? AND is_active = 1 ORDER BY day_of_week ASC, start_hour ASC, start_minute ASC",
            (room,)
        )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def add_class_session(building: str, level: int, room: str, day_of_week: int,
                      start_hour: int, start_minute: int, end_hour: int, end_minute: int,
                      label: str = "Class Session") -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO classes (building, level, room, label, day_of_week, start_hour, start_minute, end_hour, end_minute)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (building, level, room, label, day_of_week, start_hour, start_minute, end_hour, end_minute))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    log_event("TIMETABLE_ADD", f"Added session in {room} on Day {day_of_week} ({start_hour:02d}:{start_minute:02d} - {end_hour:02d}:{end_minute:02d})")
    return new_id

def delete_class_session(class_id: int):
    conn = get_db()
    conn.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    conn.commit()
    conn.close()
    log_event("TIMETABLE_DELETE", f"Deleted session ID {class_id}")

def toggle_period_slot(building: str, level: int, room: str, day_of_week: int, period_index: int,
                       scope: str = "room", target_state: Optional[str] = None) -> Dict[str, Any]:
    """
    Toggles or explicitly sets an IIUM period slot on or off across the specified scope.
    If target_state is 'occupied', ensures slot is occupied.
    If target_state is 'vacant', ensures slot is vacant.
    If target_state is None, toggles between states.
    """
    period = next((p for p in IIUM_PERIODS if p["index"] == period_index), None)
    if not period:
        return {"status": "error", "message": f"Invalid period index {period_index}"}

    target_rooms = get_rooms_for_scope(scope, building, level, room)
    conn = get_db()
    cursor = conn.cursor()

    # Check if primary room currently has this slot
    cursor.execute("""
        SELECT id FROM classes
        WHERE room = ? AND day_of_week = ? AND start_hour = ? AND start_minute = ?
    """, (room, day_of_week, period["start_h"], period["start_m"]))
    existing = cursor.fetchone()

    # Determine desired action:
    if target_state == "occupied":
        should_occupy = True
    elif target_state == "vacant":
        should_occupy = False
    else:
        should_occupy = not bool(existing)

    log_msg = ""
    if not should_occupy:
        # Set to VACANT: remove slot from all rooms in scope
        for tr in target_rooms:
            cursor.execute("""
                DELETE FROM classes
                WHERE room = ? AND day_of_week = ? AND start_hour = ? AND start_minute = ?
            """, (tr["room"], day_of_week, period["start_h"], period["start_m"]))
        new_state = "vacant"
        log_msg = f"Set P{period_index} Day {day_of_week} to VACANT for {scope} ({len(target_rooms)} rooms)"
    else:
        # Set to OCCUPIED: ensure slot exists in all rooms in scope
        for tr in target_rooms:
            cursor.execute("""
                DELETE FROM classes
                WHERE room = ? AND day_of_week = ? AND start_hour = ? AND start_minute = ?
            """, (tr["room"], day_of_week, period["start_h"], period["start_m"]))
            cursor.execute("""
                INSERT INTO classes (building, level, room, label, day_of_week, start_hour, start_minute, end_hour, end_minute)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tr["building"], tr["level"], tr["room"], f"Period {period_index}", day_of_week,
                  period["start_h"], period["start_m"], period["end_h"], period["end_m"]))
        new_state = "occupied"
        log_msg = f"Set P{period_index} Day {day_of_week} to OCCUPIED for {scope} ({len(target_rooms)} rooms)"

    conn.commit()
    conn.close()

    if log_msg:
        log_event("SLOT_TOGGLE", log_msg)

    return {
        "status": "success",
        "period_index": period_index,
        "day_of_week": day_of_week,
        "new_state": new_state,
        "affected_rooms": len(target_rooms),
        "scope": scope
    }

def clear_schedule_scope(building: str = "KOE", level: int = 2, room: str = "E1-2-14", scope: str = "room"):
    """Clears timetable sessions across the specified scope."""
    target_rooms = get_rooms_for_scope(scope, building, level, room)
    conn = get_db()
    for tr in target_rooms:
        conn.execute("DELETE FROM classes WHERE room = ?", (tr["room"],))
    conn.commit()
    conn.close()
    log_event("TIMETABLE_CLEAR", f"Cleared timetable entries for scope: {scope} ({len(target_rooms)} rooms)")
    return len(target_rooms)

def clear_room_schedule(room: str = "E1-2-14"):
    clear_schedule_scope(room=room, scope="room")

def apply_preset_schedule(building: str = "KOE", level: int = 2, room: str = "E1-2-14",
                          scope: str = "room", preset: str = "standard_weekday"):
    """
    Applies preset schedules:
    - 'standard_weekday': Mon-Fri P1 (08:30-10:00), P2 (10:00-11:30), P4 (14:00-15:30), P5 (15:30-17:00).
    - 'full_academic': Mon-Fri P1 through P5.
    - 'clear': wipes schedule in scope.
    """
    target_rooms = get_rooms_for_scope(scope, building, level, room)
    conn = get_db()
    cursor = conn.cursor()

    for tr in target_rooms:
        cursor.execute("DELETE FROM classes WHERE room = ?", (tr["room"],))

    if preset == "standard_weekday":
        periods_to_add = [
            (8, 30, 10, 0, "Period 1"),
            (10, 0, 11, 30, "Period 2"),
            (14, 0, 15, 30, "Period 4"),
            (15, 30, 17, 0, "Period 5")
        ]
        entries = []
        for tr in target_rooms:
            for day in range(5):
                for (sH, sM, eH, eM, lbl) in periods_to_add:
                    entries.append((tr["building"], tr["level"], tr["room"], lbl, day, sH, sM, eH, eM))
        cursor.executemany("""
            INSERT INTO classes (building, level, room, label, day_of_week, start_hour, start_minute, end_hour, end_minute)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, entries)

    elif preset == "full_academic":
        entries = []
        for tr in target_rooms:
            for day in range(5):
                for p in IIUM_PERIODS:
                    entries.append((tr["building"], tr["level"], tr["room"], f"Period {p['index']}", day, p["start_h"], p["start_m"], p["end_h"], p["end_m"]))
        cursor.executemany("""
            INSERT INTO classes (building, level, room, label, day_of_week, start_hour, start_minute, end_hour, end_minute)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, entries)

    conn.commit()
    conn.close()
    log_event("PRESET_APPLIED", f"Applied preset '{preset}' to scope {scope} ({len(target_rooms)} rooms)")
    return len(target_rooms)

def import_mock_imaluum(room: str = "E1-2-14", scope: str = "room", building: str = "KOE", level: int = 2, matric_no: str = "2110001") -> int:
    """
    Simulates importing official academic timetable data from IIUM i-Ma'luum portal API.
    Populates room or scope with realistic academic schedule.
    """
    target_rooms = get_rooms_for_scope(scope, building, level, room)
    conn = get_db()
    cursor = conn.cursor()

    for tr in target_rooms:
        cursor.execute("DELETE FROM classes WHERE room = ?", (tr["room"],))

    imaluum_slots = [
        (0, 8, 30, 10, 0,  "Period 1"),
        (0, 14, 0, 16, 30, "Period 4"),
        (1, 10, 0, 11, 30, "Period 2"),
        (2, 8, 30, 10, 0,  "Period 1"),
        (2, 14, 0, 16, 0,  "Period 4"),
        (3, 11, 30, 13, 0, "Period 3"),
        (4, 9, 0, 11, 30,  "Period 1")
    ]

    entries = []
    for tr in target_rooms:
        for (day, sH, sM, eH, eM, lbl) in imaluum_slots:
            entries.append((tr["building"], tr["level"], tr["room"], lbl, day, sH, sM, eH, eM))

    cursor.executemany("""
        INSERT INTO classes (building, level, room, label, day_of_week, start_hour, start_minute, end_hour, end_minute)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, entries)

    conn.commit()
    conn.close()

    log_event("IMALUUM_IMPORT", f"Imported i-Ma'luum schedule for scope {scope} ({len(target_rooms)} rooms, Matric: {matric_no})")
    return len(entries)

def get_policy() -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM policies WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        if not d.get("midnight_cutoff"):
            d["midnight_cutoff"] = "00:00"
        if not d.get("force_on_minutes"):
            d["force_on_minutes"] = 60
        return d
    return {"precool_minutes": 10, "grace_minutes": 10, "speed_factor": 1, "midnight_cutoff": "00:00", "force_on_minutes": 60}

def update_policy(precool_minutes: int, grace_minutes: int, speed_factor: Optional[int] = None, midnight_cutoff: Optional[str] = "00:00", force_on_minutes: Optional[int] = 60):
    conn = get_db()
    mc = midnight_cutoff if midnight_cutoff else "00:00"
    fom = int(force_on_minutes) if force_on_minutes else 60
    if speed_factor is not None:
        conn.execute("""
            UPDATE policies
            SET precool_minutes = ?, grace_minutes = ?, speed_factor = ?, midnight_cutoff = ?, force_on_minutes = ?
            WHERE id = 1
        """, (precool_minutes, grace_minutes, speed_factor, mc, fom))
    else:
        conn.execute("""
            UPDATE policies
            SET precool_minutes = ?, grace_minutes = ?, midnight_cutoff = ?, force_on_minutes = ?
            WHERE id = 1
        """, (precool_minutes, grace_minutes, mc, fom))
    conn.commit()
    conn.close()
    log_event("POLICY_UPDATE", f"Policy updated: Pre-cool={precool_minutes}m, Grace={grace_minutes}m, Sweep={mc}, Force-On={fom}m")

def record_deployment():
    conn = get_db()
    conn.execute("UPDATE policies SET last_deployed_at = CURRENT_TIMESTAMP WHERE id = 1")
    conn.commit()
    conn.close()
    log_event("DEPLOYMENT", "Schedule successfully deployed to physical switch EEPROM.")

def get_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_deployable_schedule(room: str = "E1-2-14", day_of_week: Optional[int] = None) -> Dict[str, Any]:
    if day_of_week is None:
        day_of_week = datetime.now(MALAYSIA_TZ).weekday()

    classes = get_classes(room=room, day_of_week=day_of_week)
    policy = get_policy()

    morning_classes = [c for c in classes if c["start_hour"] < 13]
    afternoon_classes = [c for c in classes if c["start_hour"] >= 13]

    if morning_classes:
        sH1 = min(c["start_hour"] for c in morning_classes)
        earliest_m = min((c["start_hour"] * 60 + c["start_minute"]) for c in morning_classes)
        sM1 = earliest_m % 60

        latest_m = max((c["end_hour"] * 60 + c["end_minute"]) for c in morning_classes)
        eH1 = latest_m // 60
        eM1 = latest_m % 60
        c1_desc = f"Morning Operating Window ({sH1:02d}:{sM1:02d}-{eH1:02d}:{eM1:02d})"
    else:
        sH1, sM1, eH1, eM1 = 8, 30, 11, 30
        c1_desc = "Default Standby (08:30-11:30)"

    if afternoon_classes:
        earliest_m2 = min((c["start_hour"] * 60 + c["start_minute"]) for c in afternoon_classes)
        sH2 = earliest_m2 // 60
        sM2 = earliest_m2 % 60

        latest_m2 = max((c["end_hour"] * 60 + c["end_minute"]) for c in afternoon_classes)
        eH2 = latest_m2 // 60
        eM2 = latest_m2 % 60
        c2_desc = f"Afternoon Operating Window ({sH2:02d}:{sM2:02d}-{eH2:02d}:{eM2:02d})"
    else:
        sH2, sM2, eH2, eM2 = 14, 0, 17, 0
        c2_desc = "Default Standby (14:00-17:00)"

    precool = policy.get("precool_minutes", 10)
    grace = policy.get("grace_minutes", 10)

    cmd = f"SET_SCHED:{sH1}:{sM1}:{eH1}:{eM1}:{sH2}:{sM2}:{eH2}:{eM2}:{precool}:{grace}"

    return {
        "room": room,
        "day_of_week": day_of_week,
        "sH1": sH1, "sM1": sM1, "eH1": eH1, "eM1": eM1, "c1_desc": c1_desc,
        "sH2": sH2, "sM2": sM2, "eH2": eH2, "eM2": eM2, "c2_desc": c2_desc,
        "precool": precool, "grace": grace,
        "serial_command": cmd
    }

def get_two_day_schedule(room: str = "E1-2-14") -> Dict[str, Any]:
    """
    Extracts the 2-day alternating schedule (Monday & Tuesday) for room deployment.
    Constructs the SET_2DAY:... command string for the Arduino Uno.
    """
    policy = get_policy()
    precool = policy.get("precool_minutes", 10)
    grace = policy.get("grace_minutes", 10)

    def _resolve_day(day_idx: int):
        classes = get_classes(room=room, day_of_week=day_idx)
        morning = [c for c in classes if c["start_hour"] < 13]
        afternoon = [c for c in classes if c["start_hour"] >= 13]

        if morning:
            earliest_m1 = min((c["start_hour"] * 60 + c["start_minute"]) for c in morning)
            sH1 = earliest_m1 // 60
            sM1 = earliest_m1 % 60
            latest_m1 = max((c["end_hour"] * 60 + c["end_minute"]) for c in morning)
            eH1 = latest_m1 // 60
            eM1 = latest_m1 % 60
            c1_desc = f"{sH1:02d}:{sM1:02d} - {eH1:02d}:{eM1:02d}"
        else:
            sH1, sM1, eH1, eM1 = 0, 0, 0, 0
            c1_desc = "STANDBY"

        if afternoon:
            earliest_m2 = min((c["start_hour"] * 60 + c["start_minute"]) for c in afternoon)
            sH2 = earliest_m2 // 60
            sM2 = earliest_m2 % 60
            latest_m2 = max((c["end_hour"] * 60 + c["end_minute"]) for c in afternoon)
            eH2 = latest_m2 // 60
            eM2 = latest_m2 % 60
            c2_desc = f"{sH2:02d}:{sM2:02d} - {eH2:02d}:{eM2:02d}"
        else:
            sH2, sM2, eH2, eM2 = 0, 0, 0, 0
            c2_desc = "STANDBY"

        return {
            "sH1": sH1, "sM1": sM1, "eH1": eH1, "eM1": eM1, "c1_desc": c1_desc,
            "sH2": sH2, "sM2": sM2, "eH2": eH2, "eM2": eM2, "c2_desc": c2_desc,
        }

    mon = _resolve_day(0)
    tue = _resolve_day(1)

    cmd = (
        f"SET_2DAY:{mon['sH1']}:{mon['sM1']}:{mon['eH1']}:{mon['eM1']}:"
        f"{mon['sH2']}:{mon['sM2']}:{mon['eH2']}:{mon['eM2']}:"
        f"{tue['sH1']}:{tue['sM1']}:{tue['eH1']}:{tue['eM1']}:"
        f"{tue['sH2']}:{tue['sM2']}:{tue['eH2']}:{tue['eM2']}:"
        f"{precool}:{grace}"
    )

    return {
        "room": room,
        "monday": mon,
        "tuesday": tue,
        "precool": precool,
        "grace": grace,
        "serial_command": cmd
    }

def get_full_week_schedule(room: str = "E1-2-14") -> Dict[str, Any]:
    """
    Extracts all 7 daily schedules (Monday=0 to Sunday=6) for room deployment.
    Produces atomic SET_DAY_SCHED and SET_POLICY commands.
    """
    policy = get_policy()
    precool = policy.get("precool_minutes", 10)
    grace = policy.get("grace_minutes", 10)

    days_sched = []
    commands = []

    for day_idx in range(7):
        classes = get_classes(room=room, day_of_week=day_idx)
        morning = [c for c in classes if c["start_hour"] < 13]
        afternoon = [c for c in classes if c["start_hour"] >= 13]

        if morning:
            earliest_m1 = min((c["start_hour"] * 60 + c["start_minute"]) for c in morning)
            sH1 = earliest_m1 // 60
            sM1 = earliest_m1 % 60
            latest_m1 = max((c["end_hour"] * 60 + c["end_minute"]) for c in morning)
            eH1 = latest_m1 // 60
            eM1 = latest_m1 % 60
            c1_desc = f"{sH1:02d}:{sM1:02d} - {eH1:02d}:{eM1:02d}"
        else:
            sH1, sM1, eH1, eM1 = 0, 0, 0, 0
            c1_desc = "STANDBY"

        if afternoon:
            earliest_m2 = min((c["start_hour"] * 60 + c["start_minute"]) for c in afternoon)
            sH2 = earliest_m2 // 60
            sM2 = earliest_m2 % 60
            latest_m2 = max((c["end_hour"] * 60 + c["end_minute"]) for c in afternoon)
            eH2 = latest_m2 // 60
            eM2 = latest_m2 % 60
            c2_desc = f"{sH2:02d}:{sM2:02d} - {eH2:02d}:{eM2:02d}"
        else:
            sH2, sM2, eH2, eM2 = 0, 0, 0, 0
            c2_desc = "STANDBY"

        days_sched.append({
            "day": day_idx,
            "sH1": sH1, "sM1": sM1, "eH1": eH1, "eM1": eM1, "c1_desc": c1_desc,
            "sH2": sH2, "sM2": sM2, "eH2": eH2, "eM2": eM2, "c2_desc": c2_desc,
        })
        commands.append(f"SET_DAY_SCHED:{day_idx}:{sH1}:{sM1}:{eH1}:{eM1}:{sH2}:{sM2}:{eH2}:{eM2}")

    cutoff = policy.get("midnight_cutoff", "00:00")
    force_on = policy.get("force_on_minutes", 60)
    try:
        sh, sm = [int(x) for x in (cutoff or "00:00").split(":")]
    except Exception:
        sh, sm = 0, 0
    commands.append(f"SET_POLICY:{precool}:{grace}:{sh}:{sm}:{force_on}")

    return {
        "room": room,
        "days": days_sched,
        "precool": precool,
        "grace": grace,
        "commands": commands
    }


