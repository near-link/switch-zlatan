#!/usr/bin/env python3
"""
Automated Low-Cost In-Wall Microcontroller Switch
Desktop GUI Control & Timetable Manager
Group: ZLATANFC | IIUM Energy Automation Project
"""

import sys
import time
import threading
from datetime import datetime
import customtkinter as ctk
import serial
import serial.tools.list_ports

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SmartSwitchApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Automated In-Wall Microcontroller Switch | ZLATANFC")
        self.geometry("980x740")
        self.minsize(880, 680)

        self.ser = None
        self.serial_thread = None
        self.running = True

        # Telemetry State
        self.arduino_time = "--:--:--"
        self.arduino_state = "DISCONNECTED"
        self.yellow_on = False
        self.blue_on = False
        self.red_on = False
        self.override_active = False
        self.speed_factor = 1

        self.build_ui()
        self.start_telemetry_loop()

    def build_ui(self):
        # Grid layout: 2 columns
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header Banner
        header = ctk.CTkFrame(self, corner_radius=10, fg_color="#1a1c23")
        header.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="ew")

        title = ctk.CTkLabel(
            header,
            text="⚡ AUTOMATED IN-WALL SWITCH MANAGEMENT SYSTEM",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#38bdf8"
        )
        title.pack(anchor="w", padx=20, pady=(12, 2))

        subtitle = ctk.CTkLabel(
            header,
            text="KICT & KOE Joint Project | Group ZLATANFC | IIUM Energy Automation",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8"
        )
        subtitle.pack(anchor="w", padx=20, pady=(0, 12))

        # LEFT COLUMN: Connection & Timetable Scheduler
        left_col = ctk.CTkFrame(self, fg_color="transparent")
        left_col.grid(row=1, column=0, padx=(15, 8), pady=5, sticky="nsew")

        # Serial Connection Card
        conn_card = ctk.CTkFrame(left_col, corner_radius=10)
        conn_card.pack(fill="x", pady=(0, 10))

        conn_title = ctk.CTkLabel(conn_card, text="🔌 Serial Connection (/dev/ttyACM0)", font=ctk.CTkFont(size=14, weight="bold"))
        conn_title.pack(anchor="w", padx=15, pady=(10, 5))

        port_row = ctk.CTkFrame(conn_card, fg_color="transparent")
        port_row.pack(fill="x", padx=15, pady=(0, 10))

        self.port_var = ctk.StringVar(value="/dev/ttyACM0")
        self.port_menu = ctk.CTkComboBox(port_row, values=self.get_serial_ports(), variable=self.port_var, width=180)
        self.port_menu.pack(side="left", padx=(0, 10))

        self.btn_connect = ctk.CTkButton(port_row, text="Connect", width=100, command=self.toggle_connection, fg_color="#0284c7")
        self.btn_connect.pack(side="left", padx=5)

        self.lbl_status_pill = ctk.CTkLabel(port_row, text="● Disconnected", text_color="#ef4444", font=ctk.CTkFont(weight="bold"))
        self.lbl_status_pill.pack(side="left", padx=15)

        # Timetable Scheduler Card
        sched_card = ctk.CTkFrame(left_col, corner_radius=10)
        sched_card.pack(fill="both", expand=True, pady=(0, 10))

        sched_title = ctk.CTkLabel(sched_card, text="📅 Classroom Timetable & Policy (EEPROM)", font=ctk.CTkFont(size=14, weight="bold"))
        sched_title.pack(anchor="w", padx=15, pady=(10, 8))

        # Class 1 Settings
        c1_frame = ctk.CTkFrame(sched_card, fg_color="#1e293b", corner_radius=8)
        c1_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(c1_frame, text="Morning Session (Class 1):", font=ctk.CTkFont(weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=10, pady=(6, 2))

        c1_row = ctk.CTkFrame(c1_frame, fg_color="transparent")
        c1_row.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkLabel(c1_row, text="Start:").pack(side="left", padx=(0, 4))
        self.c1_start_h = ctk.CTkEntry(c1_row, width=42); self.c1_start_h.insert(0, "08"); self.c1_start_h.pack(side="left")
        ctk.CTkLabel(c1_row, text=":").pack(side="left", padx=2)
        self.c1_start_m = ctk.CTkEntry(c1_row, width=42); self.c1_start_m.insert(0, "00"); self.c1_start_m.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(c1_row, text="End:").pack(side="left", padx=(0, 4))
        self.c1_end_h = ctk.CTkEntry(c1_row, width=42); self.c1_end_h.insert(0, "12"); self.c1_end_h.pack(side="left")
        ctk.CTkLabel(c1_row, text=":").pack(side="left", padx=2)
        self.c1_end_m = ctk.CTkEntry(c1_row, width=42); self.c1_end_m.insert(0, "00"); self.c1_end_m.pack(side="left")

        # Class 2 Settings
        c2_frame = ctk.CTkFrame(sched_card, fg_color="#1e293b", corner_radius=8)
        c2_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(c2_frame, text="Afternoon Session (Class 2):", font=ctk.CTkFont(weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=10, pady=(6, 2))

        c2_row = ctk.CTkFrame(c2_frame, fg_color="transparent")
        c2_row.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkLabel(c2_row, text="Start:").pack(side="left", padx=(0, 4))
        self.c2_start_h = ctk.CTkEntry(c2_row, width=42); self.c2_start_h.insert(0, "14"); self.c2_start_h.pack(side="left")
        ctk.CTkLabel(c2_row, text=":").pack(side="left", padx=2)
        self.c2_start_m = ctk.CTkEntry(c2_row, width=42); self.c2_start_m.insert(0, "00"); self.c2_start_m.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(c2_row, text="End:").pack(side="left", padx=(0, 4))
        self.c2_end_h = ctk.CTkEntry(c2_row, width=42); self.c2_end_h.insert(0, "19"); self.c2_end_h.pack(side="left")
        ctk.CTkLabel(c2_row, text=":").pack(side="left", padx=2)
        self.c2_end_m = ctk.CTkEntry(c2_row, width=42); self.c2_end_m.insert(0, "00"); self.c2_end_m.pack(side="left")

        # Automation Policy: Pre-cooling & Grace Period
        pol_frame = ctk.CTkFrame(sched_card, fg_color="#1e293b", corner_radius=8)
        pol_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(pol_frame, text="Smart Energy Saving Policies:", font=ctk.CTkFont(weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=10, pady=(6, 2))

        pol_row = ctk.CTkFrame(pol_frame, fg_color="transparent")
        pol_row.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkLabel(pol_row, text="Pre-Cool AC Lead:").pack(side="left", padx=(0, 4))
        self.precool_entry = ctk.CTkEntry(pol_row, width=40); self.precool_entry.insert(0, "10"); self.precool_entry.pack(side="left")
        ctk.CTkLabel(pol_row, text="mins").pack(side="left", padx=(2, 15))

        ctk.CTkLabel(pol_row, text="Auto-Off Grace:").pack(side="left", padx=(0, 4))
        self.grace_entry = ctk.CTkEntry(pol_row, width=40); self.grace_entry.insert(0, "10"); self.grace_entry.pack(side="left")
        ctk.CTkLabel(pol_row, text="mins").pack(side="left", padx=2)

        # Preset & Save Buttons
        btn_box = ctk.CTkFrame(sched_card, fg_color="transparent")
        btn_box.pack(fill="x", padx=15, pady=8)

        btn_save = ctk.CTkButton(btn_box, text="💾 Save to Switch (EEPROM)", command=self.save_schedule_to_switch, fg_color="#10b981", hover_color="#059669")
        btn_save.pack(fill="x", pady=3)

        preset_row = ctk.CTkFrame(btn_box, fg_color="transparent")
        preset_row.pack(fill="x", pady=3)
        ctk.CTkButton(preset_row, text="⚡ Quick 1-Min Demo Preset", command=self.load_quick_demo_preset, fg_color="#6366f1", width=190).pack(side="left", padx=(0, 5), expand=True)
        ctk.CTkButton(preset_row, text="🏫 IIUM Standard", command=self.load_iium_preset, fg_color="#475569", width=190).pack(side="right", padx=(5, 0), expand=True)

        # RIGHT COLUMN: Live Dashboard & Controls
        right_col = ctk.CTkFrame(self, fg_color="transparent")
        right_col.grid(row=1, column=1, padx=(8, 15), pady=5, sticky="nsew")

        # Live Virtual Switch Status Card
        dash_card = ctk.CTkFrame(right_col, corner_radius=10)
        dash_card.pack(fill="x", pady=(0, 10))

        dash_title = ctk.CTkLabel(dash_card, text="📊 Live In-Wall Switch Telemetry", font=ctk.CTkFont(size=14, weight="bold"))
        dash_title.pack(anchor="w", padx=15, pady=(10, 5))

        # Big Digital Clock Display
        clock_box = ctk.CTkFrame(dash_card, fg_color="#0f172a", corner_radius=8)
        clock_box.pack(fill="x", padx=15, pady=6)

        self.lbl_clock = ctk.CTkLabel(clock_box, text="--:--:--", font=ctk.CTkFont(size=38, weight="bold"), text_color="#38bdf8")
        self.lbl_clock.pack(pady=(8, 2))

        self.lbl_state = ctk.CTkLabel(clock_box, text="[STANDBY]", font=ctk.CTkFont(size=15, weight="bold"), text_color="#ef4444")
        self.lbl_state.pack(pady=(0, 8))

        # Virtual LED Indicators
        led_frame = ctk.CTkFrame(dash_card, fg_color="#1e293b", corner_radius=8)
        led_frame.pack(fill="x", padx=15, pady=6)

        ctk.CTkLabel(led_frame, text="Physical In-Wall Outputs (LED Mirror):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(6, 4))

        led_row = ctk.CTkFrame(led_frame, fg_color="transparent")
        led_row.pack(fill="x", padx=10, pady=(0, 8))

        self.led_yellow = ctk.CTkLabel(led_row, text="🟡 Lights (Pin 13): OFF", font=ctk.CTkFont(weight="bold"), text_color="#64748b")
        self.led_yellow.pack(side="left", expand=True)

        self.led_blue = ctk.CTkLabel(led_row, text="🔵 AC (Pin 12): OFF", font=ctk.CTkFont(weight="bold"), text_color="#64748b")
        self.led_blue.pack(side="left", expand=True)

        self.led_red = ctk.CTkLabel(led_row, text="🔴 Standby (Pin 11): OFF", font=ctk.CTkFont(weight="bold"), text_color="#64748b")
        self.led_red.pack(side="left", expand=True)

        # Clock Sync & Speed Controls Card
        ctrl_card = ctk.CTkFrame(right_col, corner_radius=10)
        ctrl_card.pack(fill="x", pady=(0, 10))

        ctrl_title = ctk.CTkLabel(ctrl_card, text="⏱️ Time Synchronization & Speed", font=ctk.CTkFont(size=14, weight="bold"))
        ctrl_title.pack(anchor="w", padx=15, pady=(10, 5))

        btn_sync = ctk.CTkButton(ctrl_card, text="🔄 Sync Switch Clock with Laptop Time", command=self.sync_laptop_time, fg_color="#0284c7")
        btn_sync.pack(fill="x", padx=15, pady=4)

        speed_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        speed_row.pack(fill="x", padx=15, pady=(6, 10))

        ctk.CTkLabel(speed_row, text="Speed:").pack(side="left", padx=(0, 6))
        self.btn_spd1 = ctk.CTkButton(speed_row, text="1x (Real)", width=75, command=lambda: self.set_speed(1), fg_color="#334155")
        self.btn_spd1.pack(side="left", padx=3)
        self.btn_spd60 = ctk.CTkButton(speed_row, text="60x (1s=1m)", width=95, command=lambda: self.set_speed(60), fg_color="#334155")
        self.btn_spd60.pack(side="left", padx=3)
        self.btn_spd600 = ctk.CTkButton(speed_row, text="600x (Fast)", width=85, command=lambda: self.set_speed(600), fg_color="#334155")
        self.btn_spd600.pack(side="left", padx=3)

        # Manual Override Card
        ovr_card = ctk.CTkFrame(right_col, corner_radius=10)
        ovr_card.pack(fill="x", pady=(0, 10))

        ovr_title = ctk.CTkLabel(ovr_card, text="🔘 Manual Wall Switch & Fail-Safe Test", font=ctk.CTkFont(size=14, weight="bold"))
        ovr_title.pack(anchor="w", padx=15, pady=(10, 5))

        ovr_row = ctk.CTkFrame(ovr_card, fg_color="transparent")
        ovr_row.pack(fill="x", padx=15, pady=(0, 10))

        btn_ovr = ctk.CTkButton(ovr_row, text="Toggle Manual Override (Button 1 (Pin 10))", command=self.toggle_manual_override, fg_color="#d97706")
        btn_ovr.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_auto = ctk.CTkButton(ovr_row, text="Resume Automated Mode", command=self.resume_auto_mode, fg_color="#475569")
        btn_auto.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Bottom Untethering Instructions Banner
        bottom_note = ctk.CTkLabel(
            self,
            text="🔋 UNTETHERED DEMO GUIDE: 1. Configure schedule & Sync Time  ➜  2. Plug 9V battery into barrel jack  ➜  3. Unplug USB & present untethered!",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8"
        )
        bottom_note.grid(row=2, column=0, columnspan=2, padx=15, pady=(0, 12))

    def get_serial_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if "/dev/ttyACM0" not in ports:
            ports.insert(0, "/dev/ttyACM0")
        return ports

    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        port = self.port_var.get()
        try:
            self.ser = serial.Serial(port, 9600, timeout=0.1)
            time.sleep(2.0)  # Wait for Arduino bootloader
            self.lbl_status_pill.configure(text="● Connected", text_color="#10b981")
            self.btn_connect.configure(text="Disconnect", fg_color="#ef4444")
            self.sync_laptop_time()
        except Exception as e:
            self.lbl_status_pill.configure(text=f"● Error: {str(e)[:18]}", text_color="#ef4444")

    def disconnect_serial(self):
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
            self.ser = None
        self.lbl_status_pill.configure(text="● Disconnected", text_color="#ef4444")
        self.btn_connect.configure(text="Connect", fg_color="#0284c7")

    def send_command(self, cmd):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((cmd + "\n").encode())
            except Exception as e:
                print("Serial send error:", e)

    def sync_laptop_time(self):
        now = datetime.now()
        cmd = f"SYNC:{now.hour:02d}:{now.minute:02d}:{now.second:02d}"
        self.send_command(cmd)

    def set_speed(self, factor):
        self.speed_factor = factor
        self.send_command(f"SET_SPEED:{factor}")

    def save_schedule_to_switch(self):
        try:
            s1h = int(self.c1_start_h.get())
            s1m = int(self.c1_start_m.get())
            e1h = int(self.c1_end_h.get())
            e1m = int(self.c1_end_m.get())

            s2h = int(self.c2_start_h.get())
            s2m = int(self.c2_start_m.get())
            e2h = int(self.c2_end_h.get())
            e2m = int(self.c2_end_m.get())

            pre = int(self.precool_entry.get())
            grc = int(self.grace_entry.get())

            cmd = f"SET_SCHED:{s1h}:{s1m}:{e1h}:{e1m}:{s2h}:{s2m}:{e2h}:{e2m}:{pre}:{grc}"
            self.send_command(cmd)
        except ValueError:
            pass

    def load_quick_demo_preset(self):
        # Starts 1 minute from now, lasts 2 minutes
        now = datetime.now()
        start_m = (now.minute + 1) % 60
        end_m = (now.minute + 3) % 60

        self.c1_start_h.delete(0, "end"); self.c1_start_h.insert(0, f"{now.hour:02d}")
        self.c1_start_m.delete(0, "end"); self.c1_start_m.insert(0, f"{start_m:02d}")
        self.c1_end_h.delete(0, "end"); self.c1_end_h.insert(0, f"{now.hour:02d}")
        self.c1_end_m.delete(0, "end"); self.c1_end_m.insert(0, f"{end_m:02d}")
        self.precool_entry.delete(0, "end"); self.precool_entry.insert(0, "1")
        self.grace_entry.delete(0, "end"); self.grace_entry.insert(0, "1")

        self.save_schedule_to_switch()
        self.set_speed(60)

    def load_iium_preset(self):
        self.c1_start_h.delete(0, "end"); self.c1_start_h.insert(0, "08")
        self.c1_start_m.delete(0, "end"); self.c1_start_m.insert(0, "00")
        self.c1_end_h.delete(0, "end"); self.c1_end_h.insert(0, "12")
        self.c1_end_m.delete(0, "end"); self.c1_end_m.insert(0, "00")

        self.c2_start_h.delete(0, "end"); self.c2_start_h.insert(0, "14")
        self.c2_start_m.delete(0, "end"); self.c2_start_m.insert(0, "00")
        self.c2_end_h.delete(0, "end"); self.c2_end_h.insert(0, "19")
        self.c2_end_m.delete(0, "end"); self.c2_end_m.insert(0, "00")

        self.precool_entry.delete(0, "end"); self.precool_entry.insert(0, "10")
        self.grace_entry.delete(0, "end"); self.grace_entry.insert(0, "10")
        self.save_schedule_to_switch()

    def toggle_manual_override(self):
        self.send_command("MANUAL_TOGGLE")

    def resume_auto_mode(self):
        self.send_command("AUTO_MODE")

    def start_telemetry_loop(self):
        def reader():
            while self.running:
                if self.ser and self.ser.is_open:
                    try:
                        line = self.ser.readline().decode(errors="ignore").strip()
                        if line.startswith("TLM:"):
                            # TLM:HH:MM:SS,STATE,YELLOW,BLUE,RED,OVERRIDE,SPEED
                            parts = line[4:].split(",")
                            if len(parts) >= 7:
                                self.arduino_time = parts[0]
                                self.arduino_state = parts[1]
                                self.yellow_on = (parts[2] == "1")
                                self.blue_on = (parts[3] == "1")
                                self.red_on = (parts[4] == "1")
                                self.override_active = (parts[5] == "1")
                                self.speed_factor = int(parts[6])
                                self.after(0, self.update_dashboard)
                    except Exception as e:
                        pass
                time.sleep(0.05)

        self.serial_thread = threading.Thread(target=reader, daemon=True)
        self.serial_thread.start()

    def update_dashboard(self):
        self.lbl_clock.configure(text=self.arduino_time)

        # State text & color
        state_colors = {
            "STANDBY": ("🔴 STANDBY (Off-Hours)", "#ef4444"),
            "PRECOOL": ("🔵 PRE-COOLING AC ACTIVE", "#38bdf8"),
            "CLASS_ACTIVE": ("🟡 CLASS IN SESSION (Lights+AC)", "#10b981"),
            "GRACE_PERIOD": ("⏳ AUTO-SHUTDOWN COUNTDOWN", "#f59e0b"),
            "MANUAL_OVERRIDE": ("⚠️ MANUAL WALL SWITCH OVERRIDE", "#f97316")
        }

        txt, color = state_colors.get(self.arduino_state, (f"[{self.arduino_state}]", "#94a3b8"))
        self.lbl_state.configure(text=txt, text_color=color)

        # LEDs
        self.led_yellow.configure(
            text=f"🟡 Lights (Pin 13): {'ON' if self.yellow_on else 'OFF'}",
            text_color="#facc15" if self.yellow_on else "#64748b"
        )
        self.led_blue.configure(
            text=f"🔵 AC (Pin 12): {'ON' if self.blue_on else 'OFF'}",
            text_color="#38bdf8" if self.blue_on else "#64748b"
        )
        self.led_red.configure(
            text=f"🔴 Standby (Pin 11): {'ON' if self.red_on else 'OFF'}",
            text_color="#ef4444" if self.red_on else "#64748b"
        )

        # Speed buttons highlights
        self.btn_spd1.configure(fg_color="#0284c7" if self.speed_factor == 1 else "#334155")
        self.btn_spd60.configure(fg_color="#0284c7" if self.speed_factor == 60 else "#334155")
        self.btn_spd600.configure(fg_color="#0284c7" if self.speed_factor == 600 else "#334155")

if __name__ == "__main__":
    app = SmartSwitchApp()
    app.mainloop()
