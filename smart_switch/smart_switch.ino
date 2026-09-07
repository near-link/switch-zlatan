/*
 * Automated Low-Cost In-Wall Microcontroller Switch
 * Complete Production Firmware (ZLATANFC - IIUM Classroom Energy Automation)
 * 
 * Hardware Mapping:
 * - Pin 13: 🟡 Classroom Lights (Yellow LED)
 * - Pin 12: 🔵 Air Conditioner (Blue LED)
 * - Pin 11: 🔴 Status / Standby (Red LED)
 * - Pin 10: 🔘 Button 1: In-Wall Manual Switch Override (INPUT_PULLUP)
 * - Pin 9:  🔘 Button 2: Fast-Forward Demo Speed Button (INPUT_PULLUP)
 * - Pin 2:  🔘 Button 3: Day Switch Advance & Display Button (INPUT_PULLUP)
 * - Pin 3:  🔔 Audio Alert / Grace Countdown Beeper
 * 
 * 4-Digit Display (5641AS Common Cathode) + 74HC595 Shift Register:
 * - Pin 8:  Shift Register Serial Data (DS)
 * - Pin 7:  Shift Register Latch Clock (ST_CP)
 * - Pin 6:  Shift Register Shift Clock (SH_CP)
 * - Pin A0: Digit 1 Common Cathode
 * - Pin A1: Digit 2 Common Cathode (has colon/dot)
 * - Pin A2: Digit 3 Common Cathode
 * - Pin A3: Digit 4 Common Cathode
 * 
 * Non-Volatile Memory:
 * - EEPROM: Permanent 7-Day academic schedule persistence (Monday through Sunday).
 *           Supports untethered 9V battery operation and standalone energy optimization.
 */

#include <Arduino.h>
#include <EEPROM.h>

// --- Pin Definitions ---
const int PIN_YELLOW      = 13;
const int PIN_BLUE        = 12;
const int PIN_RED         = 11;
const int PIN_BTN_MANUAL  = 10;
const int PIN_BTN_SPEED   = 9;
const int PIN_BTN_DAY     = 2; // 📅 Day Switch Button (INPUT_PULLUP)
const int PIN_BUZZER      = 3; // 🔔 Audio Alert / Grace Countdown Beeper

// 74HC595 Shift Register Pins
const int PIN_DATA  = 8;
const int PIN_LATCH = 7;
const int PIN_CLOCK = 6;

// 4-Digit Display Digit Pins (Common Cathode)
const int PIN_DIGIT1 = A0;
const int PIN_DIGIT2 = A1;
const int PIN_DIGIT3 = A2;
const int PIN_DIGIT4 = A3;
const int DIGIT_PINS[] = { PIN_DIGIT1, PIN_DIGIT2, PIN_DIGIT3, PIN_DIGIT4 };

// --- 7-Segment Patterns (0-9) ---
// Bit order: [DP, G, F, E, D, C, B, A]
const uint8_t DIGIT_PATTERNS[] = {
  0b00111111, // 0
  0b00000110, // 1
  0b01011011, // 2
  0b01001111, // 3
  0b01100110, // 4
  0b01101101, // 5
  0b01111101, // 6
  0b00000111, // 7
  0b01111111, // 8
  0b01101111  // 9
};

// 7-Segment Patterns for Day Names (dAY1 to dAY7):
// Digit 0='d', Digit 1='A', Digit 2='y', Digit 3='1'-'7'
const uint8_t DAY_DISPLAYS[7][4] = {
  // 0: Monday -> "dAY1"
  { 0b01011110, 0b01110111, 0b01101110, 0b00000110 },
  // 1: Tuesday -> "dAY2"
  { 0b01011110, 0b01110111, 0b01101110, 0b01011011 },
  // 2: Wednesday -> "dAY3"
  { 0b01011110, 0b01110111, 0b01101110, 0b01001111 },
  // 3: Thursday -> "dAY4"
  { 0b01011110, 0b01110111, 0b01101110, 0b01100110 },
  // 4: Friday -> "dAY5"
  { 0b01011110, 0b01110111, 0b01101110, 0b01101101 },
  // 5: Saturday -> "dAY6"
  { 0b01011110, 0b01110111, 0b01101110, 0b01111101 },
  // 6: Sunday -> "dAY7"
  { 0b01011110, 0b01110111, 0b01101110, 0b00000111 }
};

const char* const DAY_STRS[] = { "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN" };

// 7-Segment Patterns for Override Modes:
const uint8_t PAT_PRES[4] = { 0b01110011, 0b01010000, 0b01111001, 0b01101101 }; // "PrES"
const uint8_t PAT_FON[4]  = { 0b01110001, 0b01000000, 0b00111111, 0b01010100 }; // "F-On"
const uint8_t PAT_FOFF[4] = { 0b01110001, 0b01000000, 0b00111111, 0b01110001 }; // "F-OF"
const uint8_t PAT_AUTO[4] = { 0b01110111, 0b00111110, 0b01111000, 0b01011100 }; // "AUto"

uint8_t customSplash[4] = {0, 0, 0, 0};
unsigned long splashExpireMs = 0;

void triggerSplash(const uint8_t pat[4], unsigned long durationMs = 1500) {
  for (int i = 0; i < 4; i++) customSplash[i] = pat[i];
  splashExpireMs = millis() + durationMs;
}

// --- EEPROM Configuration & Storage ---
#define EEPROM_MAGIC 0x8D

struct DaySchedule {
  uint8_t startH1;
  uint8_t startM1;
  uint8_t endH1;
  uint8_t endM1;
  uint8_t startH2;
  uint8_t startM2;
  uint8_t endH2;
  uint8_t endM2;
};

struct Config {
  uint8_t magic;
  DaySchedule days[7]; // 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
  uint8_t preCoolMin;
  uint8_t graceMin;
  uint8_t nightSweepH; // Curfew sweep hour (0-23, default 0)
  uint8_t nightSweepM; // Curfew sweep minute (0-59, default 0)
  uint8_t forceOnMin;  // Force ON override duration (minutes, default 60)
} config;

// --- State Machine ---
enum SystemState {
  STATE_STANDBY,        // Off hours: Red ON, Utilities OFF
  STATE_PRECOOL,        // Pre-cooling AC: Blue ON, Yellow OFF
  STATE_CLASS_ACTIVE,   // In Session: Yellow & Blue ON
  STATE_GRACE_PERIOD    // Class Ended: Grace countdown before auto-shutdown
};

enum OverrideState {
  OVERRIDE_AUTO = 0,         // 0: Strict schedule adherence
  OVERRIDE_FORCE_ON = 1,     // 1: Utilities forced ON (ad-hoc / overtime with countdown)
  OVERRIDE_FORCE_OFF = 2,    // 2: Utilities forced OFF (early dismissal, auto-resyncs at session end)
  OVERRIDE_PRESENTATION = 3  // 3: Projector mode (Lights OFF, AC ON during class)
};

SystemState currentState = STATE_STANDBY;
SystemState scheduledState = STATE_STANDBY;
SystemState lastScheduledState = STATE_STANDBY;
OverrideState overrideMode = OVERRIDE_AUTO;
unsigned long overrideRemainingSec = 0; // Countdown for OVERRIDE_FORCE_ON
int forceOffUntilMin = 0;
int forceOnUntilMin = 0;
int presentationUntilMin = 0;

// --- Active Day Tracking (0 = Monday, ..., 6 = Sunday) ---
uint8_t currentDay = 0;
unsigned long daySplashExpireMs = 0; // Temporary banner splash when peeking or rolling over

// --- Clock & Timing ---
uint8_t currentHour   = 7;
uint8_t currentMinute = 45;
uint8_t currentSecond = 0;
unsigned long lastTickMs = 0;
unsigned long lastTelemetryMs = 0;
unsigned long lastBlinkMs = 0;
bool blinkState = false;

// Speed Multipliers: 1x (Real), 60x (1s = 1m), 600x (1s = 10m when holding Button 2)
int baseSpeedFactor = 1;
int activeSpeedFactor = 1;

// --- Button Tracking & Debounce ---
int lastBtnManualState = HIGH;
unsigned long lastBtnManualDebounce = 0;
unsigned long btnManualPressMs = 0;
bool isBtnManualPressed = false;
bool btnManualLongFired = false;

int lastBtnSpeedState = HIGH;
unsigned long lastBtnSpeedDebounce = 0;

int lastBtnDayState = HIGH;
unsigned long lastBtnDayDebounce = 0;
unsigned long btnDayPressMs = 0;
bool isBtnDayPressed = false;
bool btnDayAdvanced = false;

// --- Acoustic Alert / Beeper Engine ---
bool buzzerActive = false;
unsigned long buzzerStopMs = 0;
SystemState previousState = STATE_STANDBY;
int lastWarningBeepSec = -1;

void triggerBeep(uint16_t freq = 2000, unsigned long durationMs = 60) {
  tone(PIN_BUZZER, freq);
  digitalWrite(PIN_BUZZER, HIGH);
  buzzerActive = true;
  buzzerStopMs = millis() + durationMs;
}

void updateBuzzer() {
  if (buzzerActive && (long)(millis() - buzzerStopMs) >= 0) {
    noTone(PIN_BUZZER);
    digitalWrite(PIN_BUZZER, LOW);
    buzzerActive = false;
  }
}

// Display buffer: 4 digits + colon flag
int dispDigit[4] = { 0, 7, 4, 5 };
bool dispColon = true;

// Forward declarations
void evaluateSchedule();
void updateOutputs();
void engageForceOff();
void engageForceOn(int mins = 60);
void engagePresentation();
void engageAuto();

// --- Watch-Style Progressive Acceleration Engine ---
unsigned long btnSpeedPressMs = 0;
unsigned long lastWatchStepMs = 0;
int currentAccelTier = 0;
bool isBtnSpeedHeld = false;

void advanceMinutes(int mins) {
  currentMinute += mins;
  while (currentMinute >= 60) {
    currentMinute -= 60;
    currentHour++;
    while (currentHour >= 24) {
      currentHour -= 24;
      // Day Rollover past midnight: Mon -> Tue -> Wed -> Thu -> Fri -> Sat -> Sun -> Mon
      currentDay = (currentDay + 1) % 7;
      overrideMode = OVERRIDE_AUTO;
      overrideRemainingSec = 0;
      forceOffUntilMin = 0;
      forceOnUntilMin = 0;
      presentationUntilMin = 0;
      triggerBeep(3200, 80); // Day transition chime!
      daySplashExpireMs = millis() + 1500; // Splash day banner (e.g. dAY2)
    }
  }
  currentSecond = 0;
  dispDigit[0] = (currentHour / 10) % 10;
  dispDigit[1] = currentHour % 10;
  dispDigit[2] = (currentMinute / 10) % 10;
  dispDigit[3] = currentMinute % 10;
  dispColon = true;

  // Countdown deduction during fast-forward
  if (overrideMode == OVERRIDE_FORCE_ON && overrideRemainingSec > 0) {
    unsigned long secAdvance = (unsigned long)mins * 60;
    if (overrideRemainingSec > secAdvance) {
      overrideRemainingSec -= secAdvance;
    } else {
      overrideRemainingSec = 0;
      forceOnUntilMin = 0;
      overrideMode = OVERRIDE_AUTO;
      triggerSplash(PAT_AUTO, 1500);
      triggerBeep(800, 300);
    }
  }

  // Real-time evaluation during fast forward
  evaluateSchedule();
  updateOutputs();
}

void loadConfig() {
  EEPROM.get(0, config);
  if (config.magic != EEPROM_MAGIC) {
    config.magic = EEPROM_MAGIC;

    // Day 0: Monday (08:30-10:00, 14:00-16:30)
    config.days[0].startH1 = 8;  config.days[0].startM1 = 30;
    config.days[0].endH1   = 10; config.days[0].endM1   = 0;
    config.days[0].startH2 = 14; config.days[0].startM2 = 0;
    config.days[0].endH2   = 16; config.days[0].endM2   = 30;

    // Day 1: Tuesday (10:00-11:30, 14:00-17:00)
    config.days[1].startH1 = 10; config.days[1].startM1 = 0;
    config.days[1].endH1   = 11; config.days[1].endM1   = 30;
    config.days[1].startH2 = 14; config.days[1].startM2 = 0;
    config.days[1].endH2   = 17; config.days[1].endM2   = 0;

    // Day 2: Wednesday (08:30-10:00, 14:00-16:00)
    config.days[2].startH1 = 8;  config.days[2].startM1 = 30;
    config.days[2].endH1   = 10; config.days[2].endM1   = 0;
    config.days[2].startH2 = 14; config.days[2].startM2 = 0;
    config.days[2].endH2   = 16; config.days[2].endM2   = 0;

    // Day 3: Thursday (11:30-13:00, Standby afternoon)
    config.days[3].startH1 = 11; config.days[3].startM1 = 30;
    config.days[3].endH1   = 13; config.days[3].endM1   = 0;
    config.days[3].startH2 = 0;  config.days[3].startM2 = 0;
    config.days[3].endH2   = 0;  config.days[3].endM2   = 0;

    // Day 4: Friday (09:00-11:30, Standby afternoon)
    config.days[4].startH1 = 9;  config.days[4].startM1 = 0;
    config.days[4].endH1   = 11; config.days[4].endM1   = 30;
    config.days[4].startH2 = 0;  config.days[4].startM2 = 0;
    config.days[4].endH2   = 0;  config.days[4].endM2   = 0;

    // Day 5: Saturday (Weekend Standby)
    config.days[5].startH1 = 0;  config.days[5].startM1 = 0;
    config.days[5].endH1   = 0;  config.days[5].endM1   = 0;
    config.days[5].startH2 = 0;  config.days[5].startM2 = 0;
    config.days[5].endH2   = 0;  config.days[5].endM2   = 0;

    // Day 6: Sunday (Weekend Standby)
    config.days[6].startH1 = 0;  config.days[6].startM1 = 0;
    config.days[6].endH1   = 0;  config.days[6].endM1   = 0;
    config.days[6].startH2 = 0;  config.days[6].startM2 = 0;
    config.days[6].endH2   = 0;  config.days[6].endM2   = 0;

    config.preCoolMin = 10;
    config.graceMin   = 10;
    config.nightSweepH = 0;
    config.nightSweepM = 0;
    config.forceOnMin  = 60;
    EEPROM.put(0, config);
  }
}

void saveConfig() {
  config.magic = EEPROM_MAGIC;
  EEPROM.put(0, config);
}

int toMinutes(uint8_t h, uint8_t m) {
  return h * 60 + m;
}

void setSegments(uint8_t pattern) {
  digitalWrite(PIN_LATCH, LOW);
  shiftOut(PIN_DATA, PIN_CLOCK, MSBFIRST, pattern);
  digitalWrite(PIN_LATCH, HIGH);
}

void refreshDisplay() {
  unsigned long now = millis();
  // Show Day name banner if Day Button is physically pressed OR day splash window is active
  bool showDay = (digitalRead(PIN_BTN_DAY) == LOW) || (now < daySplashExpireMs);
  bool showSplash = (!showDay && now < splashExpireMs);

  for (int i = 0; i < 4; i++) {
    uint8_t pat = 0;

    if (showDay) {
      uint8_t dIdx = currentDay % 7;
      pat = DAY_DISPLAYS[dIdx][i];
      // Colon omitted during Day name banner
    } else if (showSplash) {
      pat = customSplash[i];
    } else {
      if (dispDigit[i] >= 0 && dispDigit[i] <= 9) {
        pat = DIGIT_PATTERNS[dispDigit[i]];
      }
      // Colon / decimal dot on Digit 2 (Hour separator)
      if (i == 1 && dispColon) {
        pat |= 0b10000000;
      }
    }

    setSegments(pat);
    digitalWrite(DIGIT_PINS[i], LOW);  // Turn digit ON (Common Cathode)
    delayMicroseconds(1000);
    digitalWrite(DIGIT_PINS[i], HIGH); // Turn digit OFF
    setSegments(0);                    // Blank
  }
}

void updateClock() {
  if (isBtnSpeedHeld) {
    return; // Watch-style acceleration engine is driving the clock
  }

  unsigned long now = millis();
  unsigned long interval = 1000 / activeSpeedFactor;
  if (interval < 4) interval = 4;

  if (now - lastTickMs >= interval) {
    lastTickMs = now;
    currentSecond++;

    // Countdown deduction for OVERRIDE_FORCE_ON
    if (overrideMode == OVERRIDE_FORCE_ON && overrideRemainingSec > 0) {
      overrideRemainingSec--;
      if (overrideRemainingSec == 0) {
        overrideMode = OVERRIDE_AUTO;
        forceOnUntilMin = 0;
        triggerSplash(PAT_AUTO, 1500);
        triggerBeep(800, 300);
        evaluateSchedule();
        updateOutputs();
        lastTelemetryMs = 0;
      }
    }

    if (currentSecond >= 60) {
      currentSecond = 0;
      currentMinute++;
      if (currentMinute >= 60) {
        currentMinute = 0;
        currentHour++;
        if (currentHour >= 24) {
          currentHour = 0;
          // Day Rollover past midnight!
          currentDay = (currentDay + 1) % 7;
          overrideMode = OVERRIDE_AUTO;
          overrideRemainingSec = 0;
          forceOffUntilMin = 0;
          forceOnUntilMin = 0;
          presentationUntilMin = 0;
          triggerBeep(3200, 80); // Day transition chime!
          daySplashExpireMs = millis() + 1500; // Splash day name banner
        }
      }
    }
  }

  // Update Display Buffer with HH:MM
  dispDigit[0] = (currentHour / 10) % 10;
  dispDigit[1] = currentHour % 10;
  dispDigit[2] = (currentMinute / 10) % 10;
  dispDigit[3] = currentMinute % 10;
  dispColon = (currentSecond % 2 == 0); // Blink colon with seconds
}

void evaluateSchedule() {
  uint8_t dayIdx = currentDay % 7;
  DaySchedule activeSched = config.days[dayIdx];

  int currentTotalMin = toMinutes(currentHour, currentMinute);

  int c1Start = toMinutes(activeSched.startH1, activeSched.startM1);
  int c1End   = toMinutes(activeSched.endH1,   activeSched.endM1);
  int c1Pre   = c1Start - config.preCoolMin;
  int c1Grace = c1End + config.graceMin;
  if (c1Pre < 0) c1Pre = 0;
  if (c1Grace > 1440) c1Grace = 1440;

  int c2Start = toMinutes(activeSched.startH2, activeSched.startM2);
  int c2End   = toMinutes(activeSched.endH2,   activeSched.endM2);
  int c2Pre   = c2Start - config.preCoolMin;
  int c2Grace = c2End + config.graceMin;
  if (c2Pre < 0) c2Pre = 0;
  if (c2Grace > 1440) c2Grace = 1440;

  bool matched = false;
  SystemState newScheduledState = STATE_STANDBY;

  // Class 1 checks (only if slot configured)
  if (c1End > c1Start) {
    if (currentTotalMin >= c1Start && currentTotalMin < c1End) {
      newScheduledState = STATE_CLASS_ACTIVE;
      matched = true;
    } else if (currentTotalMin >= c1Pre && currentTotalMin < c1Start) {
      newScheduledState = STATE_PRECOOL;
      matched = true;
    } else if (currentTotalMin >= c1End && currentTotalMin < c1Grace) {
      newScheduledState = STATE_GRACE_PERIOD;
      matched = true;
    }
  }

  // Class 2 checks (only if slot configured and not already matched)
  if (!matched && c2End > c2Start) {
    if (currentTotalMin >= c2Start && currentTotalMin < c2End) {
      newScheduledState = STATE_CLASS_ACTIVE;
      matched = true;
    } else if (currentTotalMin >= c2Pre && currentTotalMin < c2Start) {
      newScheduledState = STATE_PRECOOL;
      matched = true;
    } else if (currentTotalMin >= c2End && currentTotalMin < c2Grace) {
      newScheduledState = STATE_GRACE_PERIOD;
      matched = true;
    }
  }

  // Off-hours / Standby
  if (!matched) {
    newScheduledState = STATE_STANDBY;
  }

  // Check Schedule Boundary Transitions for Auto-Resynchronization!
  // 1. If early dismissal (FORCE_OFF): check if current session ended or reached Standby!
  if (overrideMode == OVERRIDE_FORCE_OFF) {
    if (currentTotalMin >= forceOffUntilMin || currentTotalMin < (forceOffUntilMin - 300) || (lastScheduledState != STATE_STANDBY && newScheduledState == STATE_STANDBY)) {
      overrideMode = OVERRIDE_AUTO;
      forceOffUntilMin = 0;
      triggerSplash(PAT_AUTO, 1500);
      triggerBeep(2000, 50);
    }
  }
  // 2. If presentation mode: return to AUTO when class ends or ad-hoc window expires!
  else if (overrideMode == OVERRIDE_PRESENTATION) {
    if (currentTotalMin >= presentationUntilMin || currentTotalMin < (presentationUntilMin - 300) || (lastScheduledState == STATE_CLASS_ACTIVE && (newScheduledState == STATE_GRACE_PERIOD || newScheduledState == STATE_STANDBY))) {
      overrideMode = OVERRIDE_AUTO;
      presentationUntilMin = 0;
      triggerSplash(PAT_AUTO, 1500);
      triggerBeep(2000, 50);
    }
  }
  // 3. If ad-hoc FORCE_ON:
  else if (overrideMode == OVERRIDE_FORCE_ON) {
    if (newScheduledState == STATE_PRECOOL || newScheduledState == STATE_CLASS_ACTIVE) {
      overrideMode = OVERRIDE_AUTO;
      forceOnUntilMin = 0;
      overrideRemainingSec = 0;
      triggerSplash(PAT_AUTO, 1500);
      triggerBeep(2400, 80);
    } else if (forceOnUntilMin > 0 && (currentTotalMin >= forceOnUntilMin || currentTotalMin < (forceOnUntilMin - 300))) {
      overrideMode = OVERRIDE_AUTO;
      forceOnUntilMin = 0;
      overrideRemainingSec = 0;
      triggerSplash(PAT_AUTO, 1500);
      triggerBeep(800, 300);
    }
  }
  lastScheduledState = newScheduledState;

  scheduledState = newScheduledState;

  // If in AUTO mode, currentState follows scheduledState directly
  if (overrideMode == OVERRIDE_AUTO) {
    currentState = scheduledState;
  }

  // Audio Alerts on State Transitions (only in AUTO mode)
  if (overrideMode == OVERRIDE_AUTO && currentState != previousState) {
    if (currentState == STATE_CLASS_ACTIVE) {
      triggerBeep(2400, 100); // Class session start chime
    } else if (currentState == STATE_PRECOOL) {
      triggerBeep(1800, 80);  // Pre-cooling engaged
    } else if (currentState == STATE_GRACE_PERIOD) {
      triggerBeep(1400, 150); // Grace countdown initiated
    } else if (currentState == STATE_STANDBY) {
      triggerBeep(800, 250);  // Power cutoff tone
    }
    previousState = currentState;
  }

  // Grace Period Countdown Warning Beeps (Urgency scales as shutdown nears)
  if (overrideMode == OVERRIDE_AUTO && currentState == STATE_GRACE_PERIOD) {
    int curMin = toMinutes(currentHour, currentMinute);
    int graceEndMin = 0;

    if (c1End > c1Start && curMin >= c1End && curMin < c1Grace) {
      graceEndMin = c1Grace;
    } else if (c2End > c2Start && curMin >= c2End && curMin < c2Grace) {
      graceEndMin = c2Grace;
    }

    if (graceEndMin > 0) {
      long remainingSec = (long)(graceEndMin - curMin) * 60 - currentSecond;
      if (remainingSec <= 10 && remainingSec > 0) {
        // Final 10 seconds: urgent 1Hz emergency countdown
        if (currentSecond != lastWarningBeepSec) {
          triggerBeep(2800, 50);
          lastWarningBeepSec = currentSecond;
        }
      } else if (remainingSec <= 60 && remainingSec > 10) {
        // Final 1 minute: warning beep every 5 seconds
        if ((currentSecond % 5 == 0) && (currentSecond != lastWarningBeepSec)) {
          triggerBeep(2200, 45);
          lastWarningBeepSec = currentSecond;
        }
      } else if (remainingSec > 60) {
        // General grace period: periodic acoustic ping every 15 seconds
        if ((currentSecond % 15 == 0) && (currentSecond != lastWarningBeepSec)) {
          triggerBeep(1600, 35);
          lastWarningBeepSec = currentSecond;
        }
      }
    }
  }

  // Countdown Warning Beeps for OVERRIDE_FORCE_ON
  if (overrideMode == OVERRIDE_FORCE_ON && overrideRemainingSec > 0) {
    if (overrideRemainingSec <= 300) {
      if (overrideRemainingSec % 60 == 0 && currentSecond != lastWarningBeepSec) {
        triggerBeep(1500, 80); // 1 chirp per minute in final 5 min
        lastWarningBeepSec = currentSecond;
      } else if (overrideRemainingSec <= 10 && overrideRemainingSec % 2 == 0 && currentSecond != lastWarningBeepSec) {
        triggerBeep(2000, 40); // Urgent chirps every 2s in final 10s
        lastWarningBeepSec = currentSecond;
      }
    }
  }

  // Night Sweep / Curfew Cutoff Warning Beeps (Final 10 seconds before sweep)
  long currentSecOfDay = (long)currentHour * 3600L + (long)currentMinute * 60L + currentSecond;
  long sweepSecOfDay = (long)config.nightSweepH * 3600L + (long)config.nightSweepM * 60L;
  long secToSweep = (sweepSecOfDay - currentSecOfDay + 86400L) % 86400L;

  if (secToSweep <= 10 && secToSweep > 0) {
    if (currentSecond != lastWarningBeepSec) {
      // Night sweep curfew warning tone: authoritative 1100 Hz warning pulse (distinct from 2800 Hz urgent grace chirp)
      triggerBeep(1100, 75);
      lastWarningBeepSec = currentSecond;
    }
  }

  // Night Sweep Curfew Cutoff Enforcement: At cutoff moment, purge any active overrides!
  if (secToSweep == 0 && currentSecond == 0) {
    if (overrideMode != OVERRIDE_AUTO) {
      overrideMode = OVERRIDE_AUTO;
      overrideRemainingSec = 0;
      forceOffUntilMin = 0;
      forceOnUntilMin = 0;
      presentationUntilMin = 0;
      triggerBeep(800, 300); // Mechanical load power cutoff tone
    }
  }
}

void updateOutputs() {
  unsigned long now = millis();
  if (now - lastBlinkMs >= 250) {
    lastBlinkMs = now;
    blinkState = !blinkState;
  }

  long currentSecOfDay = (long)currentHour * 3600L + (long)currentMinute * 60L + currentSecond;
  long sweepSecOfDay = (long)config.nightSweepH * 3600L + (long)config.nightSweepM * 60L;
  long secToSweep = (sweepSecOfDay - currentSecOfDay + 86400L) % 86400L;
  bool isSweepCountdown = (secToSweep <= 10 && secToSweep > 0);

  if (overrideMode == OVERRIDE_FORCE_ON) {
    digitalWrite(PIN_YELLOW, HIGH);
    digitalWrite(PIN_BLUE, HIGH);
    digitalWrite(PIN_RED, blinkState ? HIGH : LOW); // Warning pulse
    return;
  }
  else if (overrideMode == OVERRIDE_FORCE_OFF) {
    digitalWrite(PIN_YELLOW, LOW);
    digitalWrite(PIN_BLUE, LOW);
    bool slowBlink = ((now / 1000) % 2 == 0); // 1Hz heartbeat pulse
    digitalWrite(PIN_RED, slowBlink ? HIGH : LOW);
    return;
  }
  else if (overrideMode == OVERRIDE_PRESENTATION) {
    digitalWrite(PIN_YELLOW, LOW); // Lights OFF for projector
    digitalWrite(PIN_BLUE, HIGH);  // AC ON for comfort
    digitalWrite(PIN_RED, LOW);
    return;
  }

  // Pure Schedule State (OVERRIDE_AUTO)
  switch (currentState) {
    case STATE_STANDBY:
      digitalWrite(PIN_YELLOW, LOW);
      digitalWrite(PIN_BLUE, LOW);
      digitalWrite(PIN_RED, isSweepCountdown ? (blinkState ? HIGH : LOW) : HIGH);
      break;

    case STATE_PRECOOL:
      digitalWrite(PIN_YELLOW, LOW);
      digitalWrite(PIN_BLUE, HIGH);
      digitalWrite(PIN_RED, LOW);
      break;

    case STATE_CLASS_ACTIVE:
      digitalWrite(PIN_YELLOW, HIGH);
      digitalWrite(PIN_BLUE, HIGH);
      digitalWrite(PIN_RED, LOW);
      break;

    case STATE_GRACE_PERIOD:
      digitalWrite(PIN_YELLOW, HIGH);
      digitalWrite(PIN_BLUE, HIGH);
      digitalWrite(PIN_RED, blinkState ? HIGH : LOW); // Warning blink
      break;
  }
}

void engageForceOff() {
  overrideMode = OVERRIDE_FORCE_OFF;
  overrideRemainingSec = 0;
  forceOnUntilMin = 0;
  presentationUntilMin = 0;

  uint8_t dayIdx = currentDay % 7;
  DaySchedule activeSched = config.days[dayIdx];
  int curMin = toMinutes(currentHour, currentMinute);
  int c1Start = toMinutes(activeSched.startH1, activeSched.startM1);
  int c1End   = toMinutes(activeSched.endH1,   activeSched.endM1);
  int c1Grace = c1End + config.graceMin;
  int c2Start = toMinutes(activeSched.startH2, activeSched.startM2);
  int c2End   = toMinutes(activeSched.endH2,   activeSched.endM2);
  int c2Grace = c2End + config.graceMin;

  if (c1End > c1Start && curMin >= (c1Start - config.preCoolMin) && curMin < c1Grace) {
    forceOffUntilMin = c1Grace;
  } else if (c2End > c2Start && curMin >= (c2Start - config.preCoolMin) && curMin < c2Grace) {
    forceOffUntilMin = c2Grace;
  } else {
    forceOffUntilMin = curMin + 60;
  }

  triggerSplash(PAT_FOFF, 1500);
  triggerBeep(1600, 60);
  evaluateSchedule();
  updateOutputs();
  lastTelemetryMs = 0;
}

void engageForceOn(int mins) {
  if (mins <= 0) mins = 60;
  overrideMode = OVERRIDE_FORCE_ON;
  int curMin = toMinutes(currentHour, currentMinute);
  forceOnUntilMin = curMin + mins;
  overrideRemainingSec = (unsigned long)mins * 60;
  forceOffUntilMin = 0;
  presentationUntilMin = 0;

  triggerSplash(PAT_FON, 1500);
  triggerBeep(2600, 60);
  evaluateSchedule();
  updateOutputs();
  lastTelemetryMs = 0;
}

void engagePresentation() {
  overrideMode = OVERRIDE_PRESENTATION;
  int curMin = toMinutes(currentHour, currentMinute);
  uint8_t dayIdx = currentDay % 7;
  DaySchedule activeSched = config.days[dayIdx];
  int c1Start = toMinutes(activeSched.startH1, activeSched.startM1);
  int c1End   = toMinutes(activeSched.endH1,   activeSched.endM1);
  int c1Grace = c1End + config.graceMin;
  int c2Start = toMinutes(activeSched.startH2, activeSched.startM2);
  int c2End   = toMinutes(activeSched.endH2,   activeSched.endM2);
  int c2Grace = c2End + config.graceMin;

  if (c1End > c1Start && curMin >= (c1Start - config.preCoolMin) && curMin < c1Grace) {
    presentationUntilMin = c1Grace;
  } else if (c2End > c2Start && curMin >= (c2Start - config.preCoolMin) && curMin < c2Grace) {
    presentationUntilMin = c2Grace;
  } else {
    presentationUntilMin = curMin + 60;
  }
  forceOffUntilMin = 0;
  forceOnUntilMin = 0;
  overrideRemainingSec = 0;

  triggerSplash(PAT_PRES, 1500);
  triggerBeep(2700, 80);
  evaluateSchedule();
  updateOutputs();
  lastTelemetryMs = 0;
}

void engageAuto() {
  overrideMode = OVERRIDE_AUTO;
  overrideRemainingSec = 0;
  forceOffUntilMin = 0;
  forceOnUntilMin = 0;
  presentationUntilMin = 0;

  triggerSplash(PAT_AUTO, 1500);
  triggerBeep(2000, 50);
  evaluateSchedule();
  updateOutputs();
  lastTelemetryMs = 0;
}

void handleButtons() {
  unsigned long now = millis();

  // Button 1 (Pin 10): Manual Wall Switch Override
  // Tap: Toggle Force ON/OFF or Return to AUTO. Hold 1.2s: Presentation Mode.
  int btnManual = digitalRead(PIN_BTN_MANUAL);
  if (btnManual == LOW) {
    if (!isBtnManualPressed) {
      if (now - lastBtnManualDebounce > 50) {
        isBtnManualPressed = true;
        btnManualPressMs = now;
        btnManualLongFired = false;
        lastBtnManualDebounce = now;
      }
    } else {
      // Button is being held down: check for Long Press (>= 1200ms)
      if (!btnManualLongFired && (now - btnManualPressMs >= 1200)) {
        btnManualLongFired = true;
        if (overrideMode == OVERRIDE_PRESENTATION) {
          engageAuto();
        } else {
          engagePresentation();
        }
      }
    }
  } else {
    // btnManual == HIGH (Released)
    if (isBtnManualPressed) {
      if (!btnManualLongFired) {
        // Short TAP (< 1200ms)
        if (overrideMode != OVERRIDE_AUTO) {
          engageAuto();
        } else {
          // In AUTO mode: determine action based on scheduled state
          if (scheduledState == STATE_CLASS_ACTIVE || scheduledState == STATE_PRECOOL || scheduledState == STATE_GRACE_PERIOD) {
            engageForceOff();
          } else {
            engageForceOn(config.forceOnMin > 0 ? config.forceOnMin : 60);
          }
        }
      }
      isBtnManualPressed = false;
      lastBtnManualDebounce = now;
    }
  }

  // Button 2 (Pin 9): Digital Watch Style Progressive Fast-Forward
  int btnSpeed = digitalRead(PIN_BTN_SPEED);

  if (btnSpeed == LOW) {
    // Button is physically held DOWN (Active LOW with INPUT_PULLUP)
    if (!isBtnSpeedHeld) {
      if (now - lastBtnSpeedDebounce > 50) {
        isBtnSpeedHeld = true;
        btnSpeedPressMs = now;
        lastWatchStepMs = now;
        currentAccelTier = 0;
        advanceMinutes(1);       // Tap: immediate +1 minute bump!
        triggerBeep(2800, 25);   // Crisp initial tap chirp
        lastBtnSpeedDebounce = now;
      }
    } else {
      // Button is being CONTINUOUSLY HELD DOWN
      unsigned long holdDuration = now - btnSpeedPressMs;

      // Tier 0: 0 - 350ms (Initial hold pause / tap debounce window)
      if (holdDuration <= 350) {
        // Debounce window: waiting to distinguish between tap vs hold
      }
      // Tier 1: 350ms - 1500ms (Gentle stepping: +1 min every 160ms ~ 6.2 min/sec)
      else if (holdDuration <= 1500) {
        if (currentAccelTier < 1) {
          currentAccelTier = 1;
          triggerBeep(2400, 25); // Tier 1 engage chirp
        }
        if (now - lastWatchStepMs >= 160) {
          lastWatchStepMs = now;
          advanceMinutes(1);
          triggerBeep(3200, 8); // Soft micro-tick pip
        }
      }
      // Tier 2: 1500ms - 3200ms (Medium acceleration: +2 mins every 100ms ~ 20 min/sec)
      else if (holdDuration <= 3200) {
        if (currentAccelTier < 2) {
          currentAccelTier = 2;
          triggerBeep(2800, 30); // Tier 2 gear-shift chime
        }
        if (now - lastWatchStepMs >= 100) {
          lastWatchStepMs = now;
          advanceMinutes(2);
          triggerBeep(3400, 8); // Soft micro-tick pip
        }
      }
      // Tier 3: 3200ms - 5500ms (Rapid cruise: +5 mins every 75ms ~ 66 min/sec = 1.1 hr/sec)
      else if (holdDuration <= 5500) {
        if (currentAccelTier < 3) {
          currentAccelTier = 3;
          triggerBeep(3300, 35); // Tier 3 gear-shift chime
        }
        if (now - lastWatchStepMs >= 75) {
          lastWatchStepMs = now;
          advanceMinutes(5);
        }
      }
      // Tier 4: > 5500ms (Warp Speed: +15 mins every 50ms ~ 300 min/sec = 5 hrs/sec!)
      else {
        if (currentAccelTier < 4) {
          currentAccelTier = 4;
          triggerBeep(3800, 45); // Tier 4 warp chime!
        }
        if (now - lastWatchStepMs >= 50) {
          lastWatchStepMs = now;
          advanceMinutes(15);
        }
      }
    }
  } else {
    // Button is released (HIGH)
    if (isBtnSpeedHeld) {
      if (now - lastBtnSpeedDebounce > 50) {
        unsigned long totalHold = now - btnSpeedPressMs;
        isBtnSpeedHeld = false;
        lastTickMs = now; // Resume regular ticking smoothly from this exact time
        lastBtnSpeedDebounce = now;
        if (totalHold > 350) {
          triggerBeep(2200, 30); // Release confirmation chime
        }
      }
    }
  }

  // Button 3 (Pin 2): Day Switch Button (Tap to Peek, Hold 600ms to Advance ONCE)
  int btnDay = digitalRead(PIN_BTN_DAY);
  if (btnDay == LOW) {
    if (!isBtnDayPressed) {
      if (now - lastBtnDayDebounce > 50) {
        isBtnDayPressed = true;
        btnDayPressMs = now;
        btnDayAdvanced = false;
        // Peek current day immediately on display!
        daySplashExpireMs = now + 1500;
        triggerBeep(2400, 25); // Soft peek chirp
        lastBtnDayDebounce = now;
      }
    } else {
      // Button held down: keep showing day banner while held
      daySplashExpireMs = now + 1500;
      if (!btnDayAdvanced && (now - btnDayPressMs >= 600)) {
        // Hold threshold reached (600ms): Advance day ONCE!
        currentDay = (currentDay + 1) % 7;
        btnDayAdvanced = true; // Latched: will not advance again until released!
        triggerBeep(3000, 60); // Day advance confirmation chime
        evaluateSchedule();
        updateOutputs();
        lastTelemetryMs = 0;   // Immediate telemetry update
      }
    }
  } else {
    // btnDay == HIGH (Released)
    if (isBtnDayPressed) {
      daySplashExpireMs = now + 1500; // Persist day name for 1.5s after release
      isBtnDayPressed = false;
      lastBtnDayDebounce = now;
    }
  }
}

void processSerialCommands() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  if (line.startsWith("SYNC:")) {
    int h = line.substring(5, 7).toInt();
    int m = line.substring(8, 10).toInt();
    int s = line.substring(11, 13).toInt();
    currentHour   = constrain(h, 0, 23);
    currentMinute = constrain(m, 0, 59);
    currentSecond = constrain(s, 0, 59);
    evaluateSchedule();
    updateOutputs();
    Serial.println(F("OK:TIME_SYNCED"));
  }
  else if (line.startsWith("SET_DAY_SCHED:")) {
    // Format: SET_DAY_SCHED:<day 0-6>:<sH1>:<sM1>:<eH1>:<eM1>:<sH2>:<sM2>:<eH2>:<eM2>
    int parts[9];
    int partIndex = 0;
    int fromIdx = 14;
    for (int i = 14; i <= line.length() && partIndex < 9; i++) {
      if (i == line.length() || line.charAt(i) == ':') {
        parts[partIndex++] = line.substring(fromIdx, i).toInt();
        fromIdx = i + 1;
      }
    }
    if (partIndex == 9) {
      int d = constrain(parts[0], 0, 6);
      config.days[d].startH1 = parts[1];
      config.days[d].startM1 = parts[2];
      config.days[d].endH1   = parts[3];
      config.days[d].endM1   = parts[4];
      config.days[d].startH2 = parts[5];
      config.days[d].startM2 = parts[6];
      config.days[d].endH2   = parts[7];
      config.days[d].endM2   = parts[8];
      saveConfig();
      evaluateSchedule();
      updateOutputs();
      Serial.print(F("OK:DAY_SCHED_SAVED:"));
      Serial.println(d);
    } else {
      Serial.println(F("ERR:BAD_DAY_SCHED_FORMAT"));
    }
  }
  else if (line.startsWith("SET_POLICY:")) {
    // Format: SET_POLICY:<precool>:<grace>[:<sweepH>:<sweepM>[:<forceOnMin>]]
    int colon1 = line.indexOf(':', 11);
    if (colon1 != -1) {
      config.preCoolMin = line.substring(11, colon1).toInt();
      int colon2 = line.indexOf(':', colon1 + 1);
      if (colon2 != -1) {
        config.graceMin = line.substring(colon1 + 1, colon2).toInt();
        int colon3 = line.indexOf(':', colon2 + 1);
        if (colon3 != -1) {
          config.nightSweepH = line.substring(colon2 + 1, colon3).toInt() % 24;
          int colon4 = line.indexOf(':', colon3 + 1);
          if (colon4 != -1) {
            config.nightSweepM = line.substring(colon3 + 1, colon4).toInt() % 60;
            config.forceOnMin  = line.substring(colon4 + 1).toInt();
            if (config.forceOnMin <= 0) config.forceOnMin = 60;
          } else {
            config.nightSweepM = line.substring(colon3 + 1).toInt() % 60;
          }
        } else {
          config.nightSweepH = line.substring(colon2 + 1).toInt() % 24;
          config.nightSweepM = 0;
        }
      } else {
        config.graceMin = line.substring(colon1 + 1).toInt();
      }
      saveConfig();
      evaluateSchedule();
      updateOutputs();
      triggerBeep(2400, 80);
      Serial.println(F("OK:POLICY_SAVED"));
    } else {
      Serial.println(F("ERR:BAD_POLICY_FORMAT"));
    }
  }
  else if (line.startsWith("SET_SWEEP:")) {
    // Format: SET_SWEEP:<sweepH>:<sweepM>
    int colon = line.indexOf(':', 10);
    if (colon != -1) {
      config.nightSweepH = line.substring(10, colon).toInt() % 24;
      config.nightSweepM = line.substring(colon + 1).toInt() % 60;
      saveConfig();
      triggerBeep(2400, 80);
      Serial.println(F("OK:SWEEP_SAVED"));
    } else {
      Serial.println(F("ERR:BAD_SWEEP_FORMAT"));
    }
  }
  else if (line.startsWith("SET_DAY:")) {
    // Format: SET_DAY:<0-6 or MON-SUN>
    String dStr = line.substring(8);
    dStr.toUpperCase();
    int targetDay = -1;
    if (dStr == "0" || dStr.startsWith("MON")) targetDay = 0;
    else if (dStr == "1" || dStr.startsWith("TUE")) targetDay = 1;
    else if (dStr == "2" || dStr.startsWith("WED")) targetDay = 2;
    else if (dStr == "3" || dStr.startsWith("THU")) targetDay = 3;
    else if (dStr == "4" || dStr.startsWith("FRI")) targetDay = 4;
    else if (dStr == "5" || dStr.startsWith("SAT")) targetDay = 5;
    else if (dStr == "6" || dStr.startsWith("SUN")) targetDay = 6;

    if (targetDay >= 0 && targetDay < 7) {
      currentDay = targetDay;
      triggerBeep(2800, 50);
      daySplashExpireMs = millis() + 1500;
      evaluateSchedule();
      updateOutputs();
      Serial.print(F("OK:DAY_SET:"));
      Serial.println(DAY_STRS[currentDay]);
    } else {
      Serial.println(F("ERR:INVALID_DAY"));
    }
  }
  else if (line.startsWith("SET_2DAY:")) {
    int parts[18];
    int partIndex = 0;
    int fromIdx = 9;
    for (int i = 9; i <= line.length() && partIndex < 18; i++) {
      if (i == line.length() || line.charAt(i) == ':') {
        parts[partIndex++] = line.substring(fromIdx, i).toInt();
        fromIdx = i + 1;
      }
    }
    if (partIndex == 18) {
      config.days[0].startH1 = parts[0];
      config.days[0].startM1 = parts[1];
      config.days[0].endH1   = parts[2];
      config.days[0].endM1   = parts[3];
      config.days[0].startH2 = parts[4];
      config.days[0].startM2 = parts[5];
      config.days[0].endH2   = parts[6];
      config.days[0].endM2   = parts[7];

      config.days[1].startH1 = parts[8];
      config.days[1].startM1 = parts[9];
      config.days[1].endH1   = parts[10];
      config.days[1].endM1   = parts[11];
      config.days[1].startH2 = parts[12];
      config.days[1].startM2 = parts[13];
      config.days[1].endH2   = parts[14];
      config.days[1].endM2   = parts[15];

      config.preCoolMin = parts[16];
      config.graceMin   = parts[17];
      saveConfig();
      evaluateSchedule();
      updateOutputs();
      triggerBeep(2400, 80);
      Serial.println(F("OK:2DAY_SAVED"));
    } else {
      Serial.println(F("ERR:BAD_2DAY_FORMAT"));
    }
  }
  else if (line.startsWith("SET_SCHED:")) {
    int parts[10];
    int partIndex = 0;
    int fromIdx = 10;
    for (int i = 10; i <= line.length() && partIndex < 10; i++) {
      if (i == line.length() || line.charAt(i) == ':') {
        parts[partIndex++] = line.substring(fromIdx, i).toInt();
        fromIdx = i + 1;
      }
    }
    if (partIndex == 10) {
      int d = currentDay % 7;
      config.days[d].startH1 = parts[0];
      config.days[d].startM1 = parts[1];
      config.days[d].endH1   = parts[2];
      config.days[d].endM1   = parts[3];
      config.days[d].startH2 = parts[4];
      config.days[d].startM2 = parts[5];
      config.days[d].endH2   = parts[6];
      config.days[d].endM2   = parts[7];
      config.preCoolMin = parts[8];
      config.graceMin   = parts[9];
      saveConfig();
      evaluateSchedule();
      updateOutputs();
      triggerBeep(2400, 80);
      Serial.println(F("OK:SCHED_SAVED"));
    } else {
      Serial.println(F("ERR:BAD_SCHED_FORMAT"));
    }
  }
  else if (line.startsWith("SET_SPEED:")) {
    baseSpeedFactor = line.substring(10).toInt();
    if (baseSpeedFactor < 1) baseSpeedFactor = 1;
    activeSpeedFactor = baseSpeedFactor;
    Serial.println(F("OK:SPEED_SET"));
  }
  else if (line.equals("AUTO_MODE") || line.equals("AUTO")) {
    engageAuto();
    Serial.println(F("OK:AUTO_MODE"));
  }
  else if (line.startsWith("FORCE_ON")) {
    int mins = (config.forceOnMin > 0 ? config.forceOnMin : 60);
    if (line.length() > 8 && line.charAt(8) == ':') {
      mins = line.substring(9).toInt();
    }
    engageForceOn(mins);
    Serial.println(F("OK:FORCE_ON"));
  }
  else if (line.equals("FORCE_OFF")) {
    engageForceOff();
    Serial.println(F("OK:FORCE_OFF"));
  }
  else if (line.equals("PRESENTATION")) {
    engagePresentation();
    Serial.println(F("OK:PRESENTATION"));
  }
  else if (line.equals("MANUAL_TOGGLE")) {
    if (overrideMode != OVERRIDE_AUTO) {
      engageAuto();
      Serial.println(F("OK:AUTO_ENGAGED"));
    } else {
      if (scheduledState == STATE_CLASS_ACTIVE || scheduledState == STATE_PRECOOL || scheduledState == STATE_GRACE_PERIOD) {
        engageForceOff();
        Serial.println(F("OK:FORCE_OFF"));
      } else {
        engageForceOn(config.forceOnMin > 0 ? config.forceOnMin : 60);
        Serial.println(F("OK:FORCE_ON"));
      }
    }
  }
  else if (line.startsWith("BEEP")) {
    int freq = 2200;
    int dur = 100;
    if (line.length() > 5 && line.charAt(4) == ':') {
      int colon2 = line.indexOf(':', 5);
      if (colon2 != -1) {
        freq = line.substring(5, colon2).toInt();
        dur = line.substring(colon2 + 1).toInt();
      } else {
        dur = line.substring(5).toInt();
      }
    }
    if (freq <= 0) freq = 2200;
    if (dur <= 0) dur = 100;
    triggerBeep(freq, dur);
    Serial.println(F("OK:BEEP_PLAYED"));
  }
  else if (line.equals("PING")) {
    Serial.println(F("PONG:IN_WALL_SWITCH_V1"));
  }
}

void sendTelemetry() {
  unsigned long now = millis();
  if (now - lastTelemetryMs >= 1000) {
    lastTelemetryMs = now;

    Serial.print(F("TLM:"));
    if (currentHour < 10)   Serial.print('0'); Serial.print(currentHour);   Serial.print(':');
    if (currentMinute < 10) Serial.print('0'); Serial.print(currentMinute); Serial.print(':');
    if (currentSecond < 10) Serial.print('0'); Serial.print(currentSecond); Serial.print(',');

    if (overrideMode == OVERRIDE_FORCE_ON) {
      Serial.print(F("FORCE_ON"));
    } else if (overrideMode == OVERRIDE_FORCE_OFF) {
      Serial.print(F("FORCE_OFF"));
    } else if (overrideMode == OVERRIDE_PRESENTATION) {
      Serial.print(F("PRESENTATION"));
    } else {
      switch (currentState) {
        case STATE_STANDBY:      Serial.print(F("STANDBY")); break;
        case STATE_PRECOOL:      Serial.print(F("PRECOOL")); break;
        case STATE_CLASS_ACTIVE: Serial.print(F("CLASS"));   break;
        case STATE_GRACE_PERIOD: Serial.print(F("GRACE"));   break;
      }
    }
    Serial.print(',');

    Serial.print(digitalRead(PIN_YELLOW)); Serial.print(',');
    Serial.print(digitalRead(PIN_BLUE));   Serial.print(',');
    Serial.print(digitalRead(PIN_RED));    Serial.print(',');
    Serial.print((int)overrideMode); Serial.print(',');
    Serial.print(activeSpeedFactor); Serial.print(',');
    Serial.print(DAY_STRS[currentDay % 7]); Serial.print(',');
    int remMin = 0;
    if (overrideMode == OVERRIDE_FORCE_ON) {
      int curMin = toMinutes(currentHour, currentMinute);
      if (forceOnUntilMin > curMin) {
        remMin = forceOnUntilMin - curMin;
      } else if (overrideRemainingSec > 0) {
        remMin = (overrideRemainingSec + 59) / 60;
      }
    }
    Serial.println(remMin);
  }
}

void setup() {
  pinMode(PIN_YELLOW, OUTPUT);
  pinMode(PIN_BLUE, OUTPUT);
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  pinMode(PIN_BTN_MANUAL, INPUT_PULLUP);
  pinMode(PIN_BTN_SPEED, INPUT_PULLUP);
  pinMode(PIN_BTN_DAY, INPUT_PULLUP);

  pinMode(PIN_DATA, OUTPUT);
  pinMode(PIN_LATCH, OUTPUT);
  pinMode(PIN_CLOCK, OUTPUT);

  for (int i = 0; i < 4; i++) {
    pinMode(DIGIT_PINS[i], OUTPUT);
    digitalWrite(DIGIT_PINS[i], HIGH);
  }

  Serial.begin(9600);
  loadConfig();
  evaluateSchedule();
  updateOutputs();
  triggerBeep(2200, 60); // Power-on boot chime
}

void loop() {
  updateClock();
  evaluateSchedule();
  updateOutputs();
  updateBuzzer();
  handleButtons();
  processSerialCommands();
  sendTelemetry();
  refreshDisplay();
}
