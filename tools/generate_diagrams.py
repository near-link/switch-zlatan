#!/usr/bin/env python3
"""
generate_diagrams.py
Generates publication-quality circuit schematics:
- Diagram A: Original In-Wall Smart Switch Design (ESP32-C3, AC-DC, Relays)
- Diagram B: Current Physical Breadboard Demo (Arduino Uno, 74HC595, 5641AS, LEDs, Buttons)
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle
import numpy as np

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Liberation Sans', 'Arial']

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS_DIR = REPO_ROOT / "assets" / "diagrams"
DEFAULT_A_PATH = str(DIAGRAMS_DIR / "diagram_a_original.png")
DEFAULT_B_PATH = str(DIAGRAMS_DIR / "diagram_b_prototype.png")

# ==============================================================================
# DIAGRAM A: ORIGINAL PROPOSED IN-WALL SMART SWITCH ARCHITECTURE
# ==============================================================================
def create_diagram_a(output_path=DEFAULT_A_PATH):
    DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(23, 14), dpi=300)
    ax.set_xlim(0, 230)
    ax.set_ylim(0, 145)
    ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')
    ax.set_facecolor('#F8FAFC')

    # Top Title Banner
    title_box = FancyBboxPatch((6, 127), 218, 14, boxstyle="round,pad=0.5,rounding_size=2",
                               facecolor='#0F172A', edgecolor='#1E293B', linewidth=1.5)
    ax.add_patch(title_box)
    ax.text(115, 135.5, "DIAGRAM A: ORIGINAL PROPOSED IN-WALL SMART SWITCH ARCHITECTURE",
            color='#FFFFFF', fontsize=16, weight='bold', ha='center', va='center')
    ax.text(115, 131, "Commercial Target Design | ESP32-C3 SuperMini In-Wall Retrofit | Isolated 240VAC Mains Step-Down | Dual 10A Relays | Dry Contact Override",
            color='#94A3B8', fontsize=9.5, ha='center', va='center')

    def draw_component(x, y, w, h, title, subtitle="", fill="#FFFFFF", border="#475569", title_color="#0F172A"):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5",
                             facecolor=fill, edgecolor=border, linewidth=1.8, zorder=2)
        ax.add_patch(box)
        if subtitle:
            ax.text(x + w/2, y + h - 3.2, title, fontsize=9.5, weight='bold', color=title_color, ha='center', va='center', zorder=3)
            ax.text(x + w/2, y + h - 6.8, subtitle, fontsize=7.2, color='#64748B', ha='center', va='center', zorder=3)
        else:
            ax.text(x + w/2, y + h/2, title, fontsize=9.5, weight='bold', color=title_color, ha='center', va='center', zorder=3)
        return box

    def draw_box_pin(box_x, box_w, y, label, side="left", color="#334155", fontsize=7.5):
        if side == "left":
            px = box_x
            tx = box_x + 1.8
            ha = "left"
        else:
            px = box_x + box_w
            tx = box_x + box_w - 1.8
            ha = "right"
        ax.plot(px, y, 'o', color=color, markersize=4, zorder=4)
        ax.text(tx, y, label, fontsize=fontsize, color=color, weight='bold', ha=ha, va='center', zorder=4)
        return px, y

    def draw_wire(points, color="#2563EB", lw=1.8, style='-', label=None, label_pos=None):
        pts = np.array(points)
        ax.plot(pts[:, 0], pts[:, 1], color=color, linewidth=lw, linestyle=style, zorder=1)
        if label and label_pos:
            ax.text(label_pos[0], label_pos[1], label, fontsize=7.5, color=color, weight='bold',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#F8FAFC', edgecolor='none', alpha=0.95), zorder=5)

    def draw_node(x, y, color="#2563EB", size=4.5):
        ax.plot(x, y, 'o', color=color, markersize=size, zorder=4)

    # -------------------------------------------------------------
    # 1. 240VAC MAINS POWER SUPPLY & SURGE PROTECTION (Left)
    # -------------------------------------------------------------
    sec_pwr = FancyBboxPatch((6, 56), 68, 65, boxstyle="round,pad=0.5,rounding_size=2",
                             facecolor='#FEF2F2', edgecolor='#F87171', linewidth=1.5, linestyle='--', zorder=0)
    ax.add_patch(sec_pwr)
    ax.text(9, 117, "STAGE 1: 240VAC MAINS STEP-DOWN & SURGE PROTECTION", fontsize=9.5, weight='bold', color='#991B1B')

    # Mains Terminal
    draw_component(9, 74, 16, 38, "AC MAINS", "240V 50Hz L/N", fill="#FEE2E2", border="#EF4444", title_color="#991B1B")
    draw_box_pin(9, 16, 98, "LIVE (L)", side="right", color="#B91C1C", fontsize=7.2)
    draw_box_pin(9, 16, 82, "NEUT (N)", side="right", color="#1D4ED8", fontsize=7.2)

    # Fuse & MOV
    fuse = FancyBboxPatch((30, 96), 10, 4, boxstyle="round,pad=0.1", facecolor='#FEF08A', edgecolor='#CA8A04', linewidth=1.4, zorder=2)
    ax.add_patch(fuse)
    ax.text(35, 98, "FUSE 2A", fontsize=6.8, weight='bold', color='#854D0E', ha='center', va='center', zorder=3)

    mov = FancyBboxPatch((31, 82), 8, 8, boxstyle="round,pad=0.1", facecolor='#FED7AA', edgecolor='#EA580C', linewidth=1.2, zorder=2)
    ax.add_patch(mov)
    ax.text(35, 86, "MOV\n14D471K", fontsize=6, weight='bold', color='#9A3412', ha='center', va='center', zorder=3)

    # Protection wiring
    draw_wire([[25, 98], [30, 98]], color="#B91C1C", lw=2)
    draw_wire([[40, 98], [47, 98]], color="#B91C1C", lw=2)
    draw_wire([[28, 98], [28, 90], [31, 90]], color="#B91C1C", lw=1.5)
    draw_node(28, 98, color="#B91C1C")

    draw_wire([[25, 82], [31, 82]], color="#1D4ED8", lw=2)
    draw_wire([[39, 82], [47, 82]], color="#1D4ED8", lw=2)
    draw_wire([[35, 82], [35, 78], [28, 78], [28, 82]], color="#1D4ED8", lw=1.5)
    draw_node(28, 82, color="#1D4ED8")

    # HLK-PM01 Module
    draw_component(47, 74, 25, 36, "HLK-PM01", "240VAC -> 5VDC (3W)", fill="#FFFFFF", border="#64748B")
    draw_box_pin(47, 25, 98, "AC(L)", side="left", color="#B91C1C")
    draw_box_pin(47, 25, 82, "AC(N)", side="left", color="#1D4ED8")
    draw_box_pin(47, 25, 98, "+5V DC", side="right", color="#DC2626")
    draw_box_pin(47, 25, 82, "GND", side="right", color="#334155")

    # AMS1117-3.3 Regulator
    draw_component(47, 58, 25, 13, "AMS1117-3.3", "3.3V LDO Regulator", fill="#F1F5F9", border="#64748B")
    draw_box_pin(47, 25, 66, "VIN (5V)", side="left", color="#DC2626")
    draw_box_pin(47, 25, 60, "GND", side="left", color="#334155")
    draw_box_pin(47, 25, 63, "VOUT (3.3V)", side="right", color="#16A34A")

    # Connect 5V to LDO VIN
    draw_wire([[72, 98], [75, 98], [75, 66], [72, 66]], color="#DC2626", lw=2)
    draw_node(75, 98, color="#DC2626")
    draw_wire([[72, 82], [74, 82], [74, 60], [72, 60]], color="#334155", lw=1.8)
    draw_node(74, 82, color="#334155")

    # -------------------------------------------------------------
    # 2. MANUAL ROCKER WALL SWITCH INTERFACE (Bottom Left)
    # -------------------------------------------------------------
    sec_sw = FancyBboxPatch((6, 8), 68, 44, boxstyle="round,pad=0.5,rounding_size=2",
                            facecolor='#FAF5FF', edgecolor='#C084FC', linewidth=1.5, linestyle='--', zorder=0)
    ax.add_patch(sec_sw)
    ax.text(9, 48, "STAGE 2: MANUAL WALL SWITCH (FAIL-SAFE OVERRIDE)", fontsize=9, weight='bold', color='#6B21A8')

    draw_component(9, 15, 22, 28, "WALL SWITCH", "Rocker Contact", fill="#F3E8FF", border="#A855F7", title_color="#6B21A8")
    draw_box_pin(9, 22, 34, "Term 1", side="right", color="#7E22CE")
    draw_box_pin(9, 22, 22, "Term 2 (GND)", side="right", color="#334155")

    # 10k Pull-up & 100nF Cap
    r_pull = FancyBboxPatch((37, 31), 9, 6, boxstyle="round,pad=0.1", facecolor='#E9D5FF', edgecolor='#9333EA', linewidth=1.2, zorder=2)
    ax.add_patch(r_pull)
    ax.text(41.5, 34, "10k OHM", fontsize=6.8, weight='bold', color='#581C87', ha='center', va='center', zorder=3)

    c_flt = FancyBboxPatch((37, 19), 9, 6, boxstyle="round,pad=0.1", facecolor='#E0E7FF', edgecolor='#6366F1', linewidth=1.2, zorder=2)
    ax.add_patch(c_flt)
    ax.text(41.5, 22, "100nF CAP", fontsize=6.5, weight='bold', color='#3730A3', ha='center', va='center', zorder=3)

    # Wall switch wiring
    draw_wire([[31, 34], [37, 34]], color="#7E22CE", lw=1.8)
    draw_wire([[46, 34], [53, 34]], color="#7E22CE", lw=1.8)
    draw_node(53, 34, color="#7E22CE")
    # Pullup to 3.3V
    draw_wire([[41.5, 37], [41.5, 42], [70, 42]], color="#16A34A", lw=1.5, label="3.3V Pullup", label_pos=(56, 43.5))
    # Cap to GND
    draw_wire([[53, 34], [53, 24], [46, 24]], color="#7E22CE", lw=1.5)
    draw_wire([[37, 22], [31, 22]], color="#334155", lw=1.5)
    draw_wire([[31, 22], [31, 12], [70, 12]], color="#334155", lw=1.5)
    draw_node(31, 22, color="#334155")
    # Dry Contact Signal wire to ESP32 GPIO9
    draw_wire([[53, 34], [67, 34], [67, 27], [84, 27]], color="#7E22CE", lw=1.8, label="Dry Contact Sense (GPIO9)", label_pos=(69, 28.5))

    ax.text(9, 10.5, "* Toggles relays instantly in C++ interrupt even if Wi-Fi or server is offline.", fontsize=7, color='#6B21A8', style='italic')

    # -------------------------------------------------------------
    # 3. MICROCONTROLLER: ESP32-C3 SuperMini (Center)
    # -------------------------------------------------------------
    sec_mcu = FancyBboxPatch((82, 12), 58, 109, boxstyle="round,pad=0.5,rounding_size=2",
                             facecolor='#EFF6FF', edgecolor='#3B82F6', linewidth=2, zorder=0)
    ax.add_patch(sec_mcu)
    ax.text(111, 117, "ESP32-C3 SUPERMINI (160MHz RISC-V)", fontsize=11, weight='bold', color='#1E40AF', ha='center')
    ax.text(111, 113.5, "Integrated 2.4GHz 802.11 b/g/n Wi-Fi & Bluetooth 5 (LE)", fontsize=8, color='#2563EB', ha='center')

    draw_component(84, 16, 54, 93, "ESP32-C3 Core", "Firmware: C++ / MQTT Client", fill="#FFFFFF", border="#2563EB", title_color="#1E3A8A")

    # Left Pins (Power & Control)
    draw_box_pin(84, 54, 98, "3V3 (VCC)", side="left", color="#16A34A")
    draw_box_pin(84, 54, 88, "GND (GND)", side="left", color="#334155")
    draw_box_pin(84, 54, 70, "GPIO8 (STATUS)", side="left", color="#CA8A04")
    draw_box_pin(84, 54, 52, "GPIO2 (BOOT)", side="left", color="#64748B")
    draw_box_pin(84, 54, 27, "GPIO9 (WALL_SW)", side="left", color="#7E22CE")

    # Right Pins (Outputs to Relays)
    draw_box_pin(84, 54, 90, "GPIO4 (LIGHTS_CTRL)", side="right", color="#EA580C")
    draw_box_pin(84, 54, 56, "GPIO5 (AC_CTRL)", side="right", color="#0284C7")
    draw_box_pin(84, 54, 32, "UART0 TX/RX", side="right", color="#64748B")

    # Power connections into ESP32
    draw_wire([[72, 63], [78, 63], [78, 98], [84, 98]], color="#16A34A", lw=2, label="3.3V DC Rail", label_pos=(77, 80))
    draw_wire([[74, 82], [76, 82], [76, 88], [84, 88]], color="#334155", lw=1.8, label="GND Rail", label_pos=(76, 85))
    draw_wire([[70, 42], [78, 42]], color="#16A34A", lw=1.5)
    draw_node(78, 63, color="#16A34A")
    draw_wire([[70, 12], [76, 12], [76, 82]], color="#334155", lw=1.5)
    draw_node(76, 82, color="#334155")

    # Onboard Status LED block
    led_box = FancyBboxPatch((104, 67), 18, 6, boxstyle="round,pad=0.1", facecolor='#FEF08A', edgecolor='#CA8A04', linewidth=1.2, zorder=3)
    ax.add_patch(led_box)
    ax.text(113, 70, "LED GPIO8", fontsize=6.8, weight='bold', color='#854D0E', ha='center', va='center', zorder=4)
    draw_wire([[84, 70], [104, 70]], color="#CA8A04", lw=1.4)

    # Wi-Fi Cloud / Server Representation
    ax.annotate("", xy=(111, 124), xytext=(111, 109),
                arrowprops=dict(arrowstyle="->", color="#2563EB", lw=2))
    ax.text(111, 125, "((( IIUM Campus Wi-Fi 2.4GHz )))", fontsize=8.5, weight='bold', color='#2563EB', ha='center')
    ax.text(111, 122, "MQTT Pub/Sub <-> Central FastAPI Server", fontsize=7.5, color='#1E40AF', ha='center')

    # -------------------------------------------------------------
    # 4. OPTO-ISOLATED DUAL RELAY STAGE & 240V LOADS (Right)
    # -------------------------------------------------------------
    sec_rel = FancyBboxPatch((146, 8), 76, 113, boxstyle="round,pad=0.5,rounding_size=2",
                             facecolor='#FFFBEB', edgecolor='#F59E0B', linewidth=1.5, linestyle='--', zorder=0)
    ax.add_patch(sec_rel)
    ax.text(149, 117, "STAGE 3: OPTO-ISOLATED 240V RELAY DRIVERS & LOADS", fontsize=9, weight='bold', color='#B45309')

    # --- RELAY 1: Classroom Lights ---
    draw_component(148, 76, 22, 26, "PC817 #1", "Optocoupler", fill="#FFFFFF", border="#F59E0B", title_color="#B45309")
    draw_box_pin(148, 22, 90, "ANODE", side="left", color="#EA580C", fontsize=6.8)
    draw_box_pin(148, 22, 82, "CATHODE", side="left", color="#334155", fontsize=6.8)
    draw_box_pin(148, 22, 90, "COLL (5V)", side="right", color="#DC2626", fontsize=6.8)
    draw_box_pin(148, 22, 82, "EMIT", side="right", color="#EA580C", fontsize=6.8)

    draw_component(176, 74, 28, 30, "RELAY 1 (LIGHTS)", "5V Coil / 10A 250VAC", fill="#FEF3C7", border="#D97706", title_color="#92400E")
    draw_box_pin(176, 28, 90, "VCC (5V)", side="left", color="#DC2626", fontsize=7)
    draw_box_pin(176, 28, 82, "IN (TRIG)", side="left", color="#EA580C", fontsize=7)
    draw_box_pin(176, 28, 90, "COM (240V L)", side="right", color="#B91C1C", fontsize=7)
    draw_box_pin(176, 28, 80, "NO (SWITCHED)", side="right", color="#EA580C", fontsize=7)

    draw_component(209, 76, 12, 26, "LIGHTS", "Fluorescent\n/ LED Panel", fill="#FEF9C3", border="#CA8A04", title_color="#854D0E")

    # Wire GPIO4 to PC817 #1
    draw_wire([[138, 90], [148, 90]], color="#EA580C", lw=2, label="Lights Signal", label_pos=(143, 92))
    draw_wire([[148, 82], [142, 82], [142, 75], [84, 75]], color="#334155", lw=1.5)
    # Wire PC817 #1 to Relay 1
    draw_wire([[170, 82], [176, 82]], color="#EA580C", lw=1.8)
    # Switched Load to Lights
    draw_wire([[204, 80], [209, 80]], color="#EA580C", lw=2.2, label="Switched L", label_pos=(206, 82))
    draw_wire([[221, 88], [225, 88], [225, 121], [14, 121], [14, 82]], color="#1D4ED8", lw=1.5, label="240V AC Neutral Bus", label_pos=(160, 122.5))
    draw_node(14, 82, color="#1D4ED8")

    # --- RELAY 2: Classroom AC ---
    draw_component(148, 24, 22, 26, "PC817 #2", "Optocoupler", fill="#FFFFFF", border="#0284C7", title_color="#0369A1")
    draw_box_pin(148, 22, 38, "ANODE", side="left", color="#0284C7", fontsize=6.8)
    draw_box_pin(148, 22, 30, "CATHODE", side="left", color="#334155", fontsize=6.8)
    draw_box_pin(148, 22, 38, "COLL (5V)", side="right", color="#DC2626", fontsize=6.8)
    draw_box_pin(148, 22, 30, "EMIT", side="right", color="#0284C7", fontsize=6.8)

    draw_component(176, 22, 28, 30, "RELAY 2 (AC)", "5V Coil / 10A 250VAC", fill="#E0F2FE", border="#0284C7", title_color="#0369A1")
    draw_box_pin(176, 28, 38, "VCC (5V)", side="left", color="#DC2626", fontsize=7)
    draw_box_pin(176, 28, 30, "IN (TRIG)", side="left", color="#0284C7", fontsize=7)
    draw_box_pin(176, 28, 38, "COM (240V L)", side="right", color="#B91C1C", fontsize=7)
    draw_box_pin(176, 28, 28, "NO (SWITCHED)", side="right", color="#0284C7", fontsize=7)

    draw_component(209, 24, 12, 26, "AIR COND.", "1.5 - 2.5 HP\nCassette/Split", fill="#BAE6FD", border="#0284C7", title_color="#0369A1")

    # Wire GPIO5 to PC817 #2
    draw_wire([[138, 56], [144, 56], [144, 38], [148, 38]], color="#0284C7", lw=2, label="AC Signal", label_pos=(141, 47))
    draw_wire([[148, 30], [142, 30], [142, 75]], color="#334155", lw=1.5)
    # Wire PC817 #2 to Relay 2
    draw_wire([[170, 30], [176, 30]], color="#0284C7", lw=1.8)
    # Switched Load to AC
    draw_wire([[204, 28], [209, 28]], color="#0284C7", lw=2.2, label="Switched L", label_pos=(206, 30))
    draw_wire([[221, 36], [225, 36], [225, 88]], color="#1D4ED8", lw=1.5)

    # 240V Live Distribution to Relay COMs
    draw_wire([[17, 98], [17, 105], [206, 105], [206, 90], [204, 90]], color="#B91C1C", lw=2, label="240V AC Live Bus (Fused)", label_pos=(80, 106.5))
    draw_node(17, 98, color="#B91C1C")
    draw_wire([[206, 90], [206, 38], [204, 38]], color="#B91C1C", lw=2)
    draw_node(206, 90, color="#B91C1C")

    # 5V Coil Power Distribution to Relays
    draw_wire([[75, 98], [75, 102], [172, 102], [172, 90], [176, 90]], color="#DC2626", lw=1.8, label="+5V Coil Supply", label_pos=(130, 103.5))
    draw_wire([[172, 90], [170, 90]], color="#DC2626", lw=1.5)
    draw_wire([[172, 90], [172, 38], [176, 38]], color="#DC2626", lw=1.8)
    draw_node(172, 90, color="#DC2626")
    draw_wire([[172, 38], [170, 38]], color="#DC2626", lw=1.5)

    # Bottom Summary Notes
    note_box = FancyBboxPatch((6, 2), 218, 5, boxstyle="round,pad=0.2,rounding_size=1",
                              facecolor='#F1F5F9', edgecolor='#CBD5E1', linewidth=1)
    ax.add_patch(note_box)
    ax.text(8, 4.5, "ENGINEERING HIGHLIGHTS:", fontsize=7.5, weight='bold', color='#1E293B')
    ax.text(35, 4.5, "1. Galvanic Isolation: Optocouplers (PC817) isolate 3.3V logic from 5V relay coils. Relays provide >2.5kV air gap isolation from 240V mains.", fontsize=7, color='#475569')
    ax.text(35, 3.0, "2. Redundant Fail-Safe: Wall switch provides offline hardware toggle. If Wi-Fi drops, switch toggles loads directly via hardware interrupt.", fontsize=7, color='#475569')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Diagram A successfully regenerated at: {output_path}")

# ==============================================================================
# DIAGRAM B: CURRENT PHYSICAL BREADBOARD DEMONSTRATION PROTOTYPE
# ==============================================================================
def create_diagram_b(output_path=DEFAULT_B_PATH):
    DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(24, 14), dpi=300)
    ax.set_xlim(0, 240)
    ax.set_ylim(-6, 145)
    ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')
    ax.set_facecolor('#F8FAFC')

    # Top Title Banner
    title_box = FancyBboxPatch((6, 127), 228, 14, boxstyle="round,pad=0.5,rounding_size=2",
                               facecolor='#065F46', edgecolor='#047857', linewidth=1.5)
    ax.add_patch(title_box)
    ax.text(120, 135.5, "DIAGRAM B: PHYSICAL DEMONSTRATION HARDWARE PROTOTYPE (CURRENT WORKING BENCH BUILD)",
            color='#FFFFFF', fontsize=16, weight='bold', ha='center', va='center')
    ax.text(120, 131, "Hardware Build: Arduino Uno R3 (ATmega328P) | 74HC595 Shift Register | 5641AS 4-Digit Display | 3x LEDs | 2x Pushbuttons | 5V Powerbank",
            color='#A7F3D0', fontsize=9.5, ha='center', va='center')

    def draw_component(x, y, w, h, title, subtitle="", fill="#FFFFFF", border="#475569", title_color="#0F172A"):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5",
                             facecolor=fill, edgecolor=border, linewidth=1.8, zorder=2)
        ax.add_patch(box)
        if subtitle:
            ax.text(x + w/2, y + h - 3.2, title, fontsize=9.5, weight='bold', color=title_color, ha='center', va='center', zorder=3)
            ax.text(x + w/2, y + h - 6.8, subtitle, fontsize=7.2, color='#64748B', ha='center', va='center', zorder=3)
        else:
            ax.text(x + w/2, y + h/2, title, fontsize=9.5, weight='bold', color=title_color, ha='center', va='center', zorder=3)
        return box

    def draw_box_pin(box_x, box_w, y, label, side="left", color="#334155", fontsize=7.5):
        if side == "left":
            px = box_x
            tx = box_x + 1.8
            ha = "left"
        else:
            px = box_x + box_w
            tx = box_x + box_w - 1.8
            ha = "right"
        ax.plot(px, y, 'o', color=color, markersize=4, zorder=4)
        ax.text(tx, y, label, fontsize=fontsize, color=color, weight='bold', ha=ha, va='center', zorder=4)
        return px, y

    def draw_wire(points, color="#2563EB", lw=1.8, style='-', label=None, label_pos=None):
        pts = np.array(points)
        ax.plot(pts[:, 0], pts[:, 1], color=color, linewidth=lw, linestyle=style, zorder=1)
        if label and label_pos:
            ax.text(label_pos[0], label_pos[1], label, fontsize=7.5, color=color, weight='bold',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#F8FAFC', edgecolor='none', alpha=0.95), zorder=5)

    def draw_node(x, y, color="#2563EB", size=4.5):
        ax.plot(x, y, 'o', color=color, markersize=size, zorder=4)

    # -------------------------------------------------------------
    # 1. 5V POWER SOURCE & HOST INTERFACE (Left)
    # -------------------------------------------------------------
    draw_component(6, 85, 34, 30, "5V DC POWER SOURCE", "Portable Power Bank (Untethered)\nor PC Host USB Cable", fill="#FEF3C7", border="#D97706", title_color="#92400E")
    draw_box_pin(6, 34, 105, "USB 5V VBUS", side="right", color="#DC2626")
    draw_box_pin(6, 34, 95, "USB GND", side="right", color="#1E293B")
    draw_box_pin(6, 34, 89, "D+ / D- SERIAL DATA", side="right", color="#0284C7")

    draw_component(6, 48, 34, 26, "HOST DESKTOP GUI", "switch_gui.py (CustomTkinter)\n115200 Baud / Serial Sync", fill="#E0F2FE", border="#0284C7", title_color="#0369A1")
    draw_box_pin(6, 34, 61, "UART CDC COM PORT", side="right", color="#0284C7")

    # -------------------------------------------------------------
    # 2. ARDUINO UNO R3 MICROCONTROLLER (Center-Left)
    # -------------------------------------------------------------
    sec_uno = FancyBboxPatch((48, 10), 66, 112, boxstyle="round,pad=0.5,rounding_size=2",
                             facecolor='#ECFDF5', edgecolor='#059669', linewidth=2, zorder=0)
    ax.add_patch(sec_uno)
    ax.text(81, 118, "ARDUINO UNO R3 (ATmega328P @ 16 MHz)", fontsize=11, weight='bold', color='#065F46', ha='center')
    ax.text(81, 114.5, "POC Controller | 32KB Flash | 2KB SRAM | 1KB EEPROM", fontsize=8, color='#047857', ha='center')

    draw_component(52, 14, 58, 97, "Arduino Uno Core", "Firmware: smart_switch.ino", fill="#FFFFFF", border="#059669", title_color="#065F46")

    # Left Pins (Power, Analog Digits, USB)
    draw_box_pin(52, 58, 105, "+5V POWER RAIL", side="left", color="#DC2626")
    draw_box_pin(52, 58, 95, "GND POWER RAIL", side="left", color="#1E293B")
    draw_box_pin(52, 58, 87, "USB CDC SERIAL", side="left", color="#0284C7")
    draw_box_pin(52, 58, 60, "Pin A0 (DIGIT 1 EN)", side="left", color="#9333EA")
    draw_box_pin(52, 58, 52, "Pin A1 (DIGIT 2 EN)", side="left", color="#9333EA")
    draw_box_pin(52, 58, 44, "Pin A2 (DIGIT 3 EN)", side="left", color="#9333EA")
    draw_box_pin(52, 58, 36, "Pin A3 (DIGIT 4 EN)", side="left", color="#9333EA")
    draw_box_pin(52, 58, 22, "RESET", side="left", color="#64748B")

    # Right Pins (Digital Outputs & Inputs)
    draw_box_pin(52, 58, 102, "Pin 13 (LIGHTS_LED)", side="right", color="#CA8A04")
    draw_box_pin(52, 58, 92, "Pin 12 (AC_LED)", side="right", color="#0284C7")
    draw_box_pin(52, 58, 82, "Pin 11 (STANDBY_LED)", side="right", color="#DC2626")
    draw_box_pin(52, 58, 68, "Pin 10 (BTN_OVERRIDE)", side="right", color="#7C3AED")
    draw_box_pin(52, 58, 58, "Pin 9 (BTN_ACCEL 600x)", side="right", color="#D97706")
    draw_box_pin(52, 58, 44, "Pin 8 (74HC595 DATA)", side="right", color="#2563EB")
    draw_box_pin(52, 58, 34, "Pin 7 (74HC595 LATCH)", side="right", color="#16A34A")
    draw_box_pin(52, 58, 24, "Pin 6 (74HC595 CLOCK)", side="right", color="#9333EA")

    # Wires from Power/Host to Uno
    draw_wire([[40, 105], [52, 105]], color="#DC2626", lw=2, label="+5V DC", label_pos=(46, 106.5))
    draw_wire([[40, 95], [52, 95]], color="#1E293B", lw=2, label="GND", label_pos=(46, 96.5))
    draw_wire([[40, 61], [46, 61], [46, 87], [52, 87]], color="#0284C7", lw=1.8, label="Serial Sync", label_pos=(44, 73))

    # -------------------------------------------------------------
    # 3. APPLIANCE LEDs (Top Right)
    # -------------------------------------------------------------
    sec_led = FancyBboxPatch((124, 84), 110, 38, boxstyle="round,pad=0.5,rounding_size=2",
                             facecolor='#FEFCE8', edgecolor='#FACC15', linewidth=1.5, zorder=0)
    ax.add_patch(sec_led)
    ax.text(127, 118, "STAGE 1: APPLIANCE STATE INDICATOR LEDs (ROWS 1-10)", fontsize=9, weight='bold', color='#854D0E')

    # Yellow LED: Lights
    draw_component(146, 104, 52, 7.5, "LIGHTS LED (YELLOW) + 220R", "", fill="#FEF08A", border="#CA8A04", title_color="#713F12")
    draw_box_pin(146, 52, 107.75, "ANODE (+)", side="left", color="#CA8A04", fontsize=7.5)
    draw_box_pin(146, 52, 107.75, "CATHODE (-)", side="right", color="#1E293B", fontsize=7.5)

    # Blue LED: AC
    draw_component(146, 94, 52, 7.5, "AC LED (BLUE) + 220R", "", fill="#BAE6FD", border="#0284C7", title_color="#075985")
    draw_box_pin(146, 52, 97.75, "ANODE (+)", side="left", color="#0284C7", fontsize=7.5)
    draw_box_pin(146, 52, 97.75, "CATHODE (-)", side="right", color="#1E293B", fontsize=7.5)

    # Red LED: Standby
    draw_component(146, 84, 52, 7.5, "STANDBY LED (RED) + 220R", "", fill="#FECACA", border="#DC2626", title_color="#991B1B")
    draw_box_pin(146, 52, 87.75, "ANODE (+)", side="left", color="#DC2626", fontsize=7.5)
    draw_box_pin(146, 52, 87.75, "CATHODE (-)", side="right", color="#1E293B", fontsize=7.5)

    # Wires from Uno to LEDs
    draw_wire([[110, 102], [128, 102], [128, 107.75], [146, 107.75]], color="#CA8A04", lw=2, label="Pin 13 (Lights)", label_pos=(131, 105))
    draw_wire([[110, 92], [132, 92], [132, 97.75], [146, 97.75]], color="#0284C7", lw=2, label="Pin 12 (AC)", label_pos=(135, 94))
    draw_wire([[110, 82], [136, 82], [136, 87.75], [146, 87.75]], color="#DC2626", lw=2, label="Pin 11 (Standby)", label_pos=(139, 84))

    # Common LED Ground Return
    draw_wire([[198, 107.75], [206, 107.75], [206, 87.75]], color="#1E293B", lw=1.5)
    draw_wire([[198, 97.75], [206, 97.75]], color="#1E293B", lw=1.5)
    draw_wire([[198, 87.75], [206, 87.75], [206, 76]], color="#1E293B", lw=1.8, label="LED GND Return", label_pos=(209, 80))
    draw_node(206, 107.75, color="#1E293B")
    draw_node(206, 97.75, color="#1E293B")

    # -------------------------------------------------------------
    # 4. INPUT BUTTONS: 2x TACTILE SWITCHES (Middle Right)
    # -------------------------------------------------------------
    sec_btn = FancyBboxPatch((123, 55), 52, 27, boxstyle="round,pad=0.4,rounding_size=1.5",
                             facecolor='#F5F3FF', edgecolor='#DDD6FE', linewidth=1.2, zorder=0)
    ax.add_patch(sec_btn)
    ax.text(125, 78.5, "STAGE 2: TACTILE BUTTONS (INPUT_PULLUP)", fontsize=8.5, weight='bold', color='#5B21B6')

    draw_component(125, 68, 47, 7.5, "BTN 1: MANUAL OVERRIDE (D10)", "", fill="#EDE9FE", border="#8B5CF6", title_color="#5B21B6")
    draw_box_pin(125, 47, 71.75, "IN (D10)", side="left", color="#7C3AED", fontsize=7.2)
    draw_box_pin(125, 47, 71.75, "GND", side="right", color="#1E293B", fontsize=7.2)

    draw_component(125, 57.5, 47, 7.5, "BTN 2: ACCELERATOR 600x (D9)", "", fill="#FEF3C7", border="#F59E0B", title_color="#92400E")
    draw_box_pin(125, 47, 61.25, "IN (D9)", side="left", color="#D97706", fontsize=7.2)
    draw_box_pin(125, 47, 61.25, "GND", side="right", color="#1E293B", fontsize=7.2)

    # Wires from Uno to Buttons
    draw_wire([[110, 68], [116, 68], [116, 71.75], [125, 71.75]], color="#7C3AED", lw=1.8)
    draw_wire([[110, 58], [118, 58], [118, 61.25], [125, 61.25]], color="#D97706", lw=1.8)

    # Button Ground Return
    draw_wire([[172, 71.75], [175, 71.75], [175, 61.25], [172, 61.25]], color="#1E293B", lw=1.5)
    draw_wire([[175, 66.5], [206, 66.5], [206, 76]], color="#1E293B", lw=1.5)
    draw_node(206, 76, color="#1E293B")

    # -------------------------------------------------------------
    # 5. SHIFT REGISTER: SN74HC595N (Lower Middle)
    # -------------------------------------------------------------
    sec_sr = FancyBboxPatch((124, 8), 48, 45, boxstyle="round,pad=0.5,rounding_size=1.5",
                            facecolor='#EFF6FF', edgecolor='#60A5FA', linewidth=1.5, zorder=0)
    ax.add_patch(sec_sr)
    ax.text(126, 50, "SN74HC595N SHIFT REGISTER", fontsize=8.5, weight='bold', color='#1E40AF')
    ax.text(126, 46.5, "Rows 33-40 (Col E & F) | 8-Bit Serial-In", fontsize=7, color='#3B82F6')

    draw_component(126, 10, 44, 34, "74HC595 Chip", "Notch towards Row 33", fill="#FFFFFF", border="#2563EB", title_color="#1E3A8A")

    # 74HC595 Inputs (Left side)
    draw_box_pin(126, 44, 40, "DS / SER (Pin 14)", side="left", color="#2563EB", fontsize=7)
    draw_box_pin(126, 44, 33, "ST_CP / LATCH (Pin 12)", side="left", color="#16A34A", fontsize=7)
    draw_box_pin(126, 44, 26, "SH_CP / CLK (Pin 11)", side="left", color="#9333EA", fontsize=7)
    draw_box_pin(126, 44, 19, "OE (Pin 13) -> GND", side="left", color="#1E293B", fontsize=6.5)
    draw_box_pin(126, 44, 13, "VCC (16) & MR (10) -> 5V", side="left", color="#DC2626", fontsize=6.5)

    # 74HC595 Outputs (Right side - Segments)
    draw_box_pin(126, 44, 41, "QA (Seg A, P15)", side="right", color="#0284C7", fontsize=6.5)
    draw_box_pin(126, 44, 37, "QB (Seg B, P1)", side="right", color="#0284C7", fontsize=6.5)
    draw_box_pin(126, 44, 33, "QC (Seg C, P2)", side="right", color="#0284C7", fontsize=6.5)
    draw_box_pin(126, 44, 29, "QD (Seg D, P3)", side="right", color="#0284C7", fontsize=6.5)
    draw_box_pin(126, 44, 25, "QE (Seg E, P4)", side="right", color="#0284C7", fontsize=6.5)
    draw_box_pin(126, 44, 21, "QF (Seg F, P5)", side="right", color="#0284C7", fontsize=6.5)
    draw_box_pin(126, 44, 17, "QG (Seg G, P6)", side="right", color="#0284C7", fontsize=6.5)
    draw_box_pin(126, 44, 13, "QH (Seg DP, P7)", side="right", color="#0284C7", fontsize=6.5)

    # Wires from Uno to 74HC595
    draw_wire([[110, 44], [118, 44], [118, 40], [126, 40]], color="#2563EB", lw=1.8, label="D8 (Data)", label_pos=(117, 42.5))
    draw_wire([[110, 34], [120, 34], [120, 33], [126, 33]], color="#16A34A", lw=1.8, label="D7 (Latch)", label_pos=(117, 32.5))
    draw_wire([[110, 24], [122, 24], [122, 26], [126, 26]], color="#9333EA", lw=1.8, label="D6 (Clock)", label_pos=(117, 22.5))

    # -------------------------------------------------------------
    # 6. 4-DIGIT 7-SEGMENT DISPLAY: 5641AS (Right)
    # -------------------------------------------------------------
    sec_disp = FancyBboxPatch((180, 8), 54, 69, boxstyle="round,pad=0.5,rounding_size=2",
                              facecolor='#F1F5F9', edgecolor='#64748B', linewidth=1.5, zorder=0)
    ax.add_patch(sec_disp)
    ax.text(183, 73.5, "STAGE 4: 5641AS 4-DIGIT DISPLAY", fontsize=8.5, weight='bold', color='#0F172A')
    ax.text(183, 70, "Common Cathode | Rows 50-55 Col D/H", fontsize=7, color='#475569')

    draw_component(182, 10, 50, 53, "5641AS Display", "Clock / Countdowns", fill="#FFFFFF", border="#334155", title_color="#0F172A")

    # Segment Inputs (Left side of Display)
    draw_box_pin(182, 50, 41, "Seg A (P11)", side="left", color="#0284C7", fontsize=6.8)
    draw_box_pin(182, 50, 37, "Seg B (P7)", side="left", color="#0284C7", fontsize=6.8)
    draw_box_pin(182, 50, 33, "Seg C (P4)", side="left", color="#0284C7", fontsize=6.8)
    draw_box_pin(182, 50, 29, "Seg D (P2)", side="left", color="#0284C7", fontsize=6.8)
    draw_box_pin(182, 50, 25, "Seg E (P1)", side="left", color="#0284C7", fontsize=6.8)
    draw_box_pin(182, 50, 21, "Seg F (P10)", side="left", color="#0284C7", fontsize=6.8)
    draw_box_pin(182, 50, 17, "Seg G (P5)", side="left", color="#0284C7", fontsize=6.8)
    draw_box_pin(182, 50, 13, "Seg DP (P3)", side="left", color="#0284C7", fontsize=6.8)

    # 8-Bit Parallel Segment Bus from 74HC595 to Display
    for y_bus in [41, 37, 33, 29, 25, 21, 17, 13]:
        draw_wire([[170, y_bus], [182, y_bus]], color="#0284C7", lw=1.3)
    ax.text(176, 43, "8-Bit Bus", fontsize=7, color='#0284C7', ha='center', weight='bold')

    # Digit Cathode Pins (Right side of Display)
    draw_box_pin(182, 50, 56, "DIGIT 1 (P12 / Row 55c)", side="right", color="#9333EA", fontsize=6.8)
    draw_box_pin(182, 50, 48, "DIGIT 2 (P9 / Row 52c)", side="right", color="#9333EA", fontsize=6.8)
    draw_box_pin(182, 50, 40, "DIGIT 3 (P8 / Row 51c)", side="right", color="#9333EA", fontsize=6.8)
    draw_box_pin(182, 50, 32, "DIGIT 4 (P6 / Row 50i)", side="right", color="#9333EA", fontsize=6.8)

    # Multiplexing lines from Arduino A0-A3 routed underneath
    draw_wire([[52, 60], [44, 60], [44, 5], [235, 5], [235, 56], [232, 56]], color="#9333EA", lw=1.3)
    draw_wire([[52, 52], [42, 52], [42, 3.5], [236.5, 3.5], [236.5, 48], [232, 48]], color="#9333EA", lw=1.3)
    draw_wire([[52, 44], [40, 44], [40, 2], [238, 2], [238, 40], [232, 40]], color="#9333EA", lw=1.3)
    draw_wire([[52, 36], [38, 36], [38, 0.5], [239.5, 0.5], [239.5, 32], [232, 32]], color="#9333EA", lw=1.3)
    ax.text(140, 3.5, "4-Digit Multiplexing Control Lines (Arduino Pins A0-A3 Active LOW)", fontsize=8, color='#9333EA', weight='bold', ha='center')

    # Ground Return Routing to Arduino GND
    draw_wire([[206, 66.5], [206, 74], [212, 74], [212, 122], [48, 122], [48, 95], [52, 95]], color="#1E293B", lw=1.5, label="Common GND Bus", label_pos=(130, 123.5))

    # Bottom Summary Notes
    note_box = FancyBboxPatch((6, -4), 228, 5.5, boxstyle="round,pad=0.2,rounding_size=1",
                              facecolor='#F1F5F9', edgecolor='#CBD5E1', linewidth=1)
    ax.add_patch(note_box)
    ax.text(8, -1.5, "DEMONSTRATION HARDWARE HIGHLIGHTS:", fontsize=8, weight='bold', color='#0F172A')
    ax.text(48, -1.5, "1. Safe 5V DC low-voltage bench equivalent to demonstrate schedule automation, pre-cooling, and fail-safe logic without 240V hazards.", fontsize=7.2, color='#475569')
    ax.text(48, -3.0, "2. 74HC595 shift register serializes 8 segment pins into 3 Arduino pins (D8, D7, D6), leaving plenty of pins for LEDs and buttons.", fontsize=7.2, color='#475569')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Diagram B successfully regenerated at: {output_path}")

if __name__ == "__main__":
    create_diagram_a()
    create_diagram_b()
