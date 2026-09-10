// web/static/app.js - Minimalist Brutalist BMS & 1-Click Period Matrix Engine

let activeView = "viewConsole";
let activeScope = "room"; // "campus", "kulliyyah", "level", "room"
let activeBuilding = "KOE";
let activeLevel = 2;
let activeRoom = "E1-2-14";

let hierarchyData = null;
let currentClasses = [];
let totalOccupiedSlots = 0;
let iiumPeriods = [
    { index: 1, code: "P1", start_h: 8, start_m: 30, end_h: 10, end_m: 0, time_str: "08:30-10:00" },
    { index: 2, code: "P2", start_h: 10, start_m: 0, end_h: 11, end_m: 30, time_str: "10:00-11:30" },
    { index: 3, code: "P3", start_h: 11, start_m: 30, end_h: 13, end_m: 0, time_str: "11:30-13:00" },
    { index: 4, code: "P4", start_h: 14, start_m: 0, end_h: 15, end_m: 30, time_str: "14:00-15:30" },
    { index: 5, code: "P5", start_h: 15, start_m: 30, end_h: 17, end_m: 0, time_str: "15:30-17:00" },
    { index: 6, code: "P6", start_h: 17, start_m: 0, end_h: 18, end_m: 30, time_str: "17:00-18:30" }
];

let ws = null;
let lastTelemetry = null;
let sessionIdleSeconds = 0;
const TARIFF_PER_KWH = 0.365; // TNB Commercial Tariff (RM)
const AVOIDED_POWER_KW = 2.1; // 2.5HP AC (1.8kW) + Room Lights (0.3kW)
const CO2_PER_KWH = 0.694;    // kg CO2 per kWh

const DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"];
const DAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];

// GLOBAL AUTH FETCH INTERCEPTOR & SESSION MANAGEMENT
const _nativeFetch = window.fetch;
window.fetch = async function(resource, init = {}) {
    init = init || {};
    init.headers = init.headers || {};
    const token = sessionStorage.getItem("switch_token") || window.switchToken;
    if (token) {
        if (init.headers instanceof Headers) {
            if (!init.headers.has("Authorization")) {
                init.headers.set("Authorization", `Bearer ${token}`);
            }
        } else if (Array.isArray(init.headers)) {
            init.headers.push(["Authorization", `Bearer ${token}`]);
        } else {
            if (!init.headers["Authorization"]) {
                init.headers["Authorization"] = `Bearer ${token}`;
            }
        }
    }
    const response = await _nativeFetch(resource, init);
    const urlStr = typeof resource === 'string' ? resource : (resource?.url || '');
    if (response.status === 401 && !urlStr.includes("/api/auth/verify")) {
        sessionStorage.removeItem("switch_auth");
        sessionStorage.removeItem("switch_token");
        window.switchToken = null;
        const overlay = document.getElementById("authOverlay");
        if (overlay) overlay.style.display = "flex";
        const input = document.getElementById("authPasswordInput");
        if (input) {
            input.value = "";
            input.focus();
        }
    }
    return response;
};

// AUTHENTICATION OVERLAY LOGIC
async function verifyPassword() {
    const input = document.getElementById("authPasswordInput");
    const errorMsg = document.getElementById("authErrorMsg");
    const overlay = document.getElementById("authOverlay");
    if (!input) return;

    try {
        const res = await fetch("/api/auth/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ password: input.value })
        });
        const data = await res.json();
        if (res.ok && data.authenticated) {
            sessionStorage.setItem("switch_auth", "true");
            if (data.token) {
                sessionStorage.setItem("switch_token", data.token);
                window.switchToken = data.token;
            }
            if (overlay) overlay.style.display = "none";
            if (errorMsg) errorMsg.style.display = "none";
            if (typeof initWebSocket === "function" && (!ws || ws.readyState !== WebSocket.OPEN)) {
                initWebSocket();
            }
        } else {
            if (errorMsg) {
                errorMsg.innerText = (data && data.detail) ? data.detail.toUpperCase() : "ACCESS DENIED: INVALID PASSCODE";
                errorMsg.style.display = "block";
            }
            input.value = "";
            input.focus();
            input.style.borderColor = "#ff4444";
            setTimeout(() => { if (input) input.style.borderColor = ""; }, 1500);
        }
    } catch (e) {
        // Fallback for network issues
        if (errorMsg) {
            errorMsg.innerText = "AUTHENTICATION SERVICE OFFLINE";
            errorMsg.style.display = "block";
        }
    }
}

function checkAuthGate() {
    if (sessionStorage.getItem("switch_auth") === "true") {
        const overlay = document.getElementById("authOverlay");
        if (overlay) overlay.style.display = "none";
        if (typeof initWebSocket === "function" && (!ws || ws.readyState !== WebSocket.OPEN)) {
            initWebSocket();
        }
    } else {
        const overlay = document.getElementById("authOverlay");
        if (overlay) overlay.style.display = "flex";
        const input = document.getElementById("authPasswordInput");
        if (input) setTimeout(() => input.focus(), 100);
    }
}
window.verifyPassword = verifyPassword;
window.checkAuthGate = checkAuthGate;

document.addEventListener("DOMContentLoaded", () => {
    checkAuthGate();
    // 1. Initial Data Hydration
    if (window.INITIAL_HIERARCHY) {
        hierarchyData = window.INITIAL_HIERARCHY;
        populateHierarchySelects(hierarchyData);
    } else {
        fetchHierarchy();
    }

    if (window.INITIAL_PERIODS) {
        iiumPeriods = window.INITIAL_PERIODS;
    }

    if (window.INITIAL_CLASSES) {
        currentClasses = window.INITIAL_CLASSES;
        renderMatrixTable(currentClasses);
        updateConsoleScheduleSummary(currentClasses);
    } else {
        fetchRoomClasses(activeRoom);
    }

    if (window.INITIAL_HARDWARE && window.INITIAL_HARDWARE.time) {
        applyTelemetry(window.INITIAL_HARDWARE);
    }

    // Restore saved hardware digital twin perspective
    try {
        const savedModel = localStorage.getItem("switch_hw_model") || "bench";
        switchHardwareModel(savedModel);
    } catch (e) {
        switchHardwareModel("bench");
    }

    // 2. Setup Navigation & Routing
    const urlParams = new URLSearchParams(window.location.search);
    const roomParam = urlParams.get("room");
    if (roomParam) activeRoom = roomParam;

    switchConsoleRoom(activeRoom);
    initNavigation();
    initWebSocket();
    fetchPolicy();
    fetchLogs();
    updateEnergySavings();

    // 3. Fallback Polling & Savings Timer
    setInterval(() => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            fetchStatus();
        }
    }, 2000);

    setInterval(updateEnergySavings, 1000);
});

// =============================================================================
// NAVIGATION & SPA HASH ROUTING
// =============================================================================
function initNavigation() {
    const params = new URLSearchParams(window.location.search);
    const viewParam = params.get("view");
    const hash = window.location.hash.toLowerCase();

    if (viewParam === "timetable" || hash === "#timetable") {
        navigate("viewTimetable");
    } else if (viewParam === "analytics" || hash === "#analytics") {
        navigate("viewAnalytics");
    } else if (viewParam === "diagnostics" || hash === "#diagnostics") {
        navigate("viewDiagnostics");
    } else {
        navigate("viewConsole");
    }
}

function navigate(viewId) {
    if (viewId === "viewDiagnostics" && activeRoom !== "E1-2-14") {
        showToast("DIAGNOSTICS EXCLUSIVE TO DEV BENCH UNIT [E1-2-14]");
        viewId = "viewConsole";
    }

    activeView = viewId;
    window.location.hash = viewId.replace("view", "").toLowerCase();

    document.querySelectorAll(".nav-item").forEach(el => {
        const isMatch = el.getAttribute("data-view") === viewId;
        el.classList.toggle("active", isMatch);
        if (isMatch && typeof el.scrollIntoView === "function") {
            el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
        }
    });

    document.querySelectorAll(".screen-view").forEach(el => {
        el.classList.toggle("active", el.id === viewId);
    });

    const meta = {
        viewConsole: { tag: "SEC.01", title: "HARDWARE DIGITAL TWIN & CONTROLS" },
        viewTimetable: { tag: "SEC.02", title: "CAMPUS TIMETABLE MATRIX // 1-CLICK SCHEDULER" },
        viewAnalytics: { tag: "SEC.03", title: "ENERGY CONSERVATION & SDG 7 METRICS" },
        viewDiagnostics: { tag: "SEC.04", title: "EDGE GATEWAY SERIAL TELEMETRY STREAM" }
    }[viewId] || { tag: "SYS", title: "SWITCH_" };

    const tagEl = document.getElementById("topbarTag");
    const titleEl = document.getElementById("screenTitle");
    if (tagEl) tagEl.textContent = meta.tag;
    if (titleEl) titleEl.textContent = meta.title;

    if (viewId === "viewTimetable") {
        fetchRoomClasses(activeRoom);
    } else if (viewId === "viewAnalytics") {
        fetchLogs();
    }
}

// =============================================================================
// SCOPE BROADCAST & CAMPUS HIERARCHY
// =============================================================================
function setScope(scope) {
    activeScope = scope;
    document.querySelectorAll("#scopeSegmentedControl .segmented-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-scope") === scope);
    });

    const scopeBadge = document.getElementById("activeScopeBadge");
    if (scopeBadge) scopeBadge.textContent = `SCOPE: ${scope.toUpperCase()}`;

    // Enable/disable dropdowns based on active scope
    const selBuilding = document.getElementById("selectBuilding");
    const selLevel = document.getElementById("selectLevel");
    const selRoom = document.getElementById("selectRoom");

    if (scope === "campus") {
        if (selBuilding) selBuilding.disabled = true;
        if (selLevel) selLevel.disabled = true;
        if (selRoom) selRoom.disabled = true;
    } else if (scope === "kulliyyah") {
        if (selBuilding) selBuilding.disabled = false;
        if (selLevel) selLevel.disabled = true;
        if (selRoom) selRoom.disabled = true;
    } else if (scope === "level") {
        if (selBuilding) selBuilding.disabled = false;
        if (selLevel) selLevel.disabled = false;
        if (selRoom) selRoom.disabled = true;
    } else { // "room"
        if (selBuilding) selBuilding.disabled = false;
        if (selLevel) selLevel.disabled = false;
        if (selRoom) selRoom.disabled = false;
    }

    updateScopeModalText();
    showToast(`BROADCAST SCOPE SET TO: ${scope.toUpperCase()}`);
}

async function fetchHierarchy() {
    try {
        const res = await fetch("/api/hierarchy");
        if (res.ok) {
            hierarchyData = await res.json();
            populateHierarchySelects(hierarchyData);
        }
    } catch (e) {
        console.error("fetchHierarchy error:", e);
    }
}

function populateHierarchySelects(data) {
    const kulliyyahs = data.kulliyyahs || data.buildings || [];
    const selBuilding = document.getElementById("selectBuilding");
    if (!selBuilding || kulliyyahs.length === 0) return;

    selBuilding.innerHTML = kulliyyahs.map(k => `<option value="${k.id}">${k.name}</option>`).join('');
    selBuilding.value = activeBuilding;

    updateLevelAndRoomSelects();
}

function updateLevelAndRoomSelects() {
    if (!hierarchyData) return;
    const kulliyyahs = hierarchyData.kulliyyahs || hierarchyData.buildings || [];
    const kObj = kulliyyahs.find(k => k.id === activeBuilding) || kulliyyahs[0];
    if (!kObj) return;

    const selLevel = document.getElementById("selectLevel");
    const selRoom = document.getElementById("selectRoom");

    if (selLevel && kObj.levels) {
        selLevel.innerHTML = kObj.levels.map(l => `<option value="${l.level}">Level ${l.level}</option>`).join('');
        selLevel.value = activeLevel;
    }

    if (selRoom && kObj.levels) {
        const lObj = kObj.levels.find(l => l.level === activeLevel) || kObj.levels[0];
        if (lObj && lObj.rooms) {
            selRoom.innerHTML = lObj.rooms.map(r => `<option value="${r.id}">${r.name}</option>`).join('');
            selRoom.value = activeRoom;
        }
    }

    updateTopBadges();
}

function onHierarchyFilterChange() {
    activeBuilding = document.getElementById("selectBuilding").value;
    activeLevel = parseInt(document.getElementById("selectLevel").value) || 2;
    activeRoom = document.getElementById("selectRoom").value;

    updateLevelAndRoomSelects();
    switchConsoleRoom(activeRoom);
    updateScopeModalText();
}

function switchConsoleRoom(roomId) {
    activeRoom = roomId;
    const isPoc = (activeRoom === "E1-2-14");
    
    const roomBadge = document.getElementById("activeRoomBadge");
    if (roomBadge) {
        roomBadge.textContent = `TARGET: ${activeRoom}${isPoc ? " [POC SWITCH]" : " [EDGE NODE]"}`;
    }
    
    const typeBadge = document.getElementById("controllerTypeBadge");
    if (typeBadge) {
        if (isPoc) {
            typeBadge.textContent = "LIVE SERIAL USB";
            typeBadge.style.background = "#003311";
            typeBadge.style.color = "#00ff66";
            typeBadge.style.borderColor = "#00aa44";
        } else {
            typeBadge.textContent = "SIMULATED EDGE NODE (MQTT/REST)";
            typeBadge.style.background = "#1a1500";
            typeBadge.style.color = "#ffcc00";
            typeBadge.style.borderColor = "#aa8800";
        }
    }

    const devBadge = document.getElementById("controllerDevBadge");
    if (devBadge) {
        devBadge.style.display = isPoc ? "inline-block" : "none";
    }

    const demoSpeed = document.getElementById("demoSpeedSection");
    if (demoSpeed) {
        demoSpeed.style.display = isPoc ? "block" : "none";
    }

    const demoJumps = document.getElementById("demoStateJumpsSection");
    if (demoJumps) {
        demoJumps.style.display = isPoc ? "block" : "none";
    }

    const btnBuzzer = document.getElementById("btnTestBuzzer");
    if (btnBuzzer) {
        btnBuzzer.style.display = isPoc ? "" : "none";
    }

    const navDiag = document.getElementById("navItemDiagnostics");
    if (navDiag) {
        navDiag.style.display = isPoc ? "" : "none";
    }

    if (!isPoc && activeView === "viewDiagnostics") {
        navigate("viewConsole");
    }

    const consolePanelTitle = document.getElementById("consolePanelTitle");
    if (consolePanelTitle) {
        consolePanelTitle.textContent = isPoc 
            ? "ATmega328P Microcontroller Real-Time Actuation" 
            : `Production Smart Switch Controller [${activeRoom}]`;
    }

    const consoleDevPort = document.getElementById("consoleDevPort");
    if (consoleDevPort) {
        consoleDevPort.textContent = isPoc 
            ? "DEV: /dev/ttyACM0" 
            : "EDGE PROTOCOL: MQTT/TLS OVER WI-FI";
    }

    const clockSubtext = document.getElementById("clockSubtext");
    if (clockSubtext) {
        clockSubtext.textContent = isPoc 
            ? "HARDWARE REAL-TIME CLOCK [RTC-EMU // DEMO]" 
            : "PRECISION I2C RTC [DS3231 + NTP SYNC]";
    }

    const btnFlashConsole = document.getElementById("btnFlashConsole");
    if (btnFlashConsole) {
        btnFlashConsole.textContent = isPoc ? "FLASH EEPROM [USB]" : "DEPLOY SCHEDULE [MQTT]";
    }

    const btnFlashTimetable = document.getElementById("btnFlashTimetable");
    if (btnFlashTimetable) {
        btnFlashTimetable.innerHTML = isPoc 
            ? "<span>FLASH TO DEV SWITCH [USB]</span>" 
            : `<span>DEPLOY TO ${activeRoom} [MQTT]</span>`;
    }
    
    const selConsole = document.getElementById("consoleRoomSelect");
    if (selConsole) selConsole.value = activeRoom;
    const selRoom = document.getElementById("selectRoom");
    if (selRoom) selRoom.value = activeRoom;
    
    fetchStatus();
    fetchRoomClasses(activeRoom);
    showToast(`SWITCHED TARGET TO ROOM: ${activeRoom} ${isPoc ? '(LIVE BENCH HARDWARE)' : '(SIMULATED FLEET NODE)'}`);
}

function updateTopBadges() {
    const roomBadge = document.getElementById("activeRoomBadge");
    if (roomBadge) {
        const isPoc = activeRoom === "E1-2-14";
        roomBadge.textContent = `TARGET: ${activeRoom}${isPoc ? " [POC SWITCH]" : " [EDGE NODE]"}`;
    }
    const selConsole = document.getElementById("consoleRoomSelect");
    if (selConsole && selConsole.value !== activeRoom) {
        selConsole.value = activeRoom;
    }
}

function updateScopeModalText() {
    const el = document.getElementById("imaluumScopeText");
    if (!el) return;
    if (activeScope === "campus") {
        el.value = "CAMPUS-WIDE (ALL KULLIYYAHS & ROOMS)";
    } else if (activeScope === "kulliyyah") {
        el.value = `KULLIYYAH: ${activeBuilding} (ALL ROOMS)`;
    } else if (activeScope === "level") {
        el.value = `LEVEL: ${activeBuilding} LEVEL ${activeLevel}`;
    } else {
        el.value = `ROOM: ${activeRoom}`;
    }
}

// =============================================================================
// 1-CLICK IIUM PERIOD MATRIX ENGINE
// =============================================================================
async function fetchRoomClasses(room) {
    try {
        const res = await fetch(`/api/classes?room=${room}`);
        if (res.ok) {
            currentClasses = await res.json();
            renderMatrixTable(currentClasses);
            updateConsoleScheduleSummary(currentClasses);
        }
    } catch (e) {
        console.error("fetchRoomClasses error:", e);
    }
}

function renderMatrixTable(classes) {
    const tbody = document.getElementById("matrixTableBody");
    if (!tbody) return;

    const todayIdx = (new Date().getDay() === 0) ? 6 : new Date().getDay() - 1;
    const activeSwitchDayIdx = (lastTelemetry && lastTelemetry.day) ? DAY_CODES.indexOf(lastTelemetry.day) : -1;
    tbody.innerHTML = "";
    totalOccupiedSlots = 0;

    DAYS.forEach((dayName, dayIdx) => {
        const isToday = dayIdx === todayIdx;
        const isSwitchActive = dayIdx === activeSwitchDayIdx;
        const tr = document.createElement("tr");
        tr.className = `day-row ${isToday ? 'active-today' : ''} ${isSwitchActive ? 'switch-active-day' : ''}`;

        // Day Column
        const th = document.createElement("th");
        th.className = "col-day-header";
        th.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:2px;">
                <span style="font-weight:800; font-size:0.75rem;">${dayName}</span>
                ${isSwitchActive ? '<span style="background:#fff; color:#000; padding:1px 4px; font-size:0.56rem; font-weight:700; width:fit-content; letter-spacing:0.02em;">ACTIVE ON SWITCH</span>' : (isToday ? '<span style="font-size:0.58rem; color:var(--text-dim);">[TODAY]</span>' : '')}
            </div>
            <div class="day-row-actions">
                <button class="row-mini-btn" onclick="toggleFullDay(${dayIdx}, true)" title="Mark all periods occupied">FILL</button>
                <button class="row-mini-btn" onclick="toggleFullDay(${dayIdx}, false)" title="Clear day">CLR</button>
            </div>
        `;
        tr.appendChild(th);

        // Periods 1, 2, 3
        [1, 2, 3].forEach(pIdx => {
            tr.appendChild(createSlotCell(dayIdx, pIdx, classes));
        });

        // Break Column (Lunch / Zuhr / Jummah)
        const tdBreak = document.createElement("td");
        tdBreak.className = "cell-break";
        tdBreak.textContent = dayIdx === 4 ? "JUMMAH" : "ZUHR";
        tr.appendChild(tdBreak);

        // Periods 4, 5, 6
        [4, 5, 6].forEach(pIdx => {
            tr.appendChild(createSlotCell(dayIdx, pIdx, classes));
        });

        tbody.appendChild(tr);
    });

    updateSummaryDeckMetrics();
}

const pendingSlotToggles = new Set();
let refreshClassesTimeout = null;

function updateSummaryDeckMetrics() {
    let occupiedCount = 0;
    DAYS.forEach((_, dIdx) => {
        iiumPeriods.forEach(p => {
            if (currentClasses.some(c => c.day_of_week === dIdx && c.start_hour === p.start_h && c.start_minute === p.start_m)) {
                occupiedCount++;
            }
        });
    });
    totalOccupiedSlots = occupiedCount;

    const summaryPeriodEl = document.getElementById("summaryPeriodCount");
    const summaryHoursEl = document.getElementById("summaryOperatingHours");
    const summaryAvoidedEl = document.getElementById("summaryAvoidedHours");
    const summaryScopeEl = document.getElementById("summaryScopeCount");

    if (summaryPeriodEl) summaryPeriodEl.textContent = `${totalOccupiedSlots} / 42`;
    if (summaryHoursEl) summaryHoursEl.textContent = `${(totalOccupiedSlots * 1.5).toFixed(1)} HRS`;
    if (summaryAvoidedEl) summaryAvoidedEl.textContent = `${Math.max(0, 63.0 - totalOccupiedSlots * 1.5).toFixed(1)} HRS`;
    if (summaryScopeEl) summaryScopeEl.textContent = `${activeScope.toUpperCase()}`;
    updateEnergySavings();
}

function updateTableCellsFromData(classes) {
    document.querySelectorAll("#matrixTableBody td.slot-cell").forEach(cell => {
        const dayIdx = parseInt(cell.getAttribute("data-day"));
        const pIdx = parseInt(cell.getAttribute("data-period"));
        const slotKey = `${dayIdx}_${pIdx}`;
        if (pendingSlotToggles.has(slotKey)) return;

        const period = iiumPeriods.find(p => p.index === pIdx);
        if (!period) return;

        const isOcc = classes.some(c =>
            c.day_of_week === dayIdx &&
            c.start_hour === period.start_h &&
            c.start_minute === period.start_m
        );

        cell.classList.toggle("occupied", isOcc);
        const stateSpan = cell.querySelector(".slot-state-text");
        if (stateSpan) {
            stateSpan.textContent = isOcc ? 'OCCUPIED' : '---';
        }
    });
}

async function syncClassesSilently(room) {
    if (pendingSlotToggles.size > 0) return;
    try {
        const res = await fetch(`/api/classes?room=${room}`);
        if (res.ok) {
            currentClasses = await res.json();
            updateTableCellsFromData(currentClasses);
            updateSummaryDeckMetrics();
            updateConsoleScheduleSummary(currentClasses, lastTelemetry ? lastTelemetry.day : null);
        }
    } catch (e) {
        console.error("Silent sync error:", e);
    }
}

function createSlotCell(dayIdx, pIdx, classes) {
    const period = iiumPeriods.find(p => p.index === pIdx);
    const td = document.createElement("td");
    td.className = "slot-cell";
    td.setAttribute("data-day", dayIdx);
    td.setAttribute("data-period", pIdx);

    // Check if occupied
    const isOccupied = classes.some(c =>
        c.day_of_week === dayIdx &&
        c.start_hour === period.start_h &&
        c.start_minute === period.start_m
    );

    if (isOccupied) {
        td.classList.add("occupied");
        totalOccupiedSlots++;
    }

    td.innerHTML = `
        <div class="slot-inner">
            <span class="slot-state-text">${isOccupied ? 'OCCUPIED' : '---'}</span>
            <span class="slot-time-sub">${period.code}</span>
        </div>
    `;

    td.onclick = () => onSlotClick(dayIdx, pIdx, td);
    return td;
}

async function onSlotClick(dayIdx, pIdx, cellEl) {
    const slotKey = `${dayIdx}_${pIdx}`;
    if (pendingSlotToggles.has(slotKey)) {
        return; // Debounce rapid double-clicks on the same cell
    }

    pendingSlotToggles.add(slotKey);
    const currentlyOccupied = cellEl.classList.contains("occupied");
    const targetState = currentlyOccupied ? "vacant" : "occupied";

    // Immediate optimistic update on this specific cell DOM
    cellEl.classList.toggle("occupied", targetState === "occupied");
    const stateSpan = cellEl.querySelector(".slot-state-text");
    if (stateSpan) {
        stateSpan.textContent = (targetState === "occupied") ? 'OCCUPIED' : '---';
    }

    // Update in-memory currentClasses optimistically so counters & summary update immediately
    const period = iiumPeriods.find(p => p.index === pIdx);
    if (targetState === "occupied") {
        if (!currentClasses.some(c => c.day_of_week === dayIdx && c.start_hour === period.start_h && c.start_minute === period.start_m)) {
            currentClasses.push({
                building: activeBuilding,
                level: activeLevel,
                room: activeRoom,
                label: `Period ${pIdx}`,
                day_of_week: dayIdx,
                start_hour: period.start_h,
                start_minute: period.start_m,
                end_hour: period.end_h,
                end_minute: period.end_m,
                is_active: 1
            });
        }
    } else {
        currentClasses = currentClasses.filter(c => !(c.day_of_week === dayIdx && c.start_hour === period.start_h && c.start_minute === period.start_m));
    }

    updateSummaryDeckMetrics();
    updateConsoleScheduleSummary(currentClasses, lastTelemetry ? lastTelemetry.day : null);

    try {
        const res = await fetch("/api/timetable/toggle", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                building: activeBuilding,
                level: activeLevel,
                room: activeRoom,
                day_of_week: dayIdx,
                period_index: pIdx,
                scope: activeScope,
                target_state: targetState
            })
        });
        const data = await res.json();
        if (data.status === "success") {
            const isOcc = (data.new_state === "occupied");
            cellEl.classList.toggle("occupied", isOcc);
            if (stateSpan) {
                stateSpan.textContent = isOcc ? 'OCCUPIED' : '---';
            }
            showToast(`P${pIdx} ${DAYS[dayIdx]}: ${data.new_state.toUpperCase()} [${activeScope.toUpperCase()}]`);

            // Debounced background sync: wait 800ms of inactivity before background reconciliation
            clearTimeout(refreshClassesTimeout);
            refreshClassesTimeout = setTimeout(() => {
                syncClassesSilently(activeRoom);
            }, 800);
        } else {
            // Revert on error
            cellEl.classList.toggle("occupied", currentlyOccupied);
            if (stateSpan) {
                stateSpan.textContent = currentlyOccupied ? 'OCCUPIED' : '---';
            }
        }
    } catch (e) {
        console.error("Slot toggle error:", e);
        cellEl.classList.toggle("occupied", currentlyOccupied);
        if (stateSpan) {
            stateSpan.textContent = currentlyOccupied ? 'OCCUPIED' : '---';
        }
    } finally {
        pendingSlotToggles.delete(slotKey);
    }
}

async function toggleFullDay(dayIdx, setOccupied) {
    const targetState = setOccupied ? "occupied" : "vacant";
    const periodIndices = [1, 2, 3, 4, 5, 6];

    // Optimistically update all cells in this row immediately
    periodIndices.forEach(pIdx => {
        const cell = document.querySelector(`.slot-cell[data-day="${dayIdx}"][data-period="${pIdx}"]`);
        if (cell) {
            cell.classList.toggle("occupied", setOccupied);
            const stateSpan = cell.querySelector(".slot-state-text");
            if (stateSpan) stateSpan.textContent = setOccupied ? 'OCCUPIED' : '---';
        }
        const period = iiumPeriods.find(p => p.index === pIdx);
        if (setOccupied) {
            if (!currentClasses.some(c => c.day_of_week === dayIdx && c.start_hour === period.start_h && c.start_minute === period.start_m)) {
                currentClasses.push({
                    building: activeBuilding, level: activeLevel, room: activeRoom,
                    label: `Period ${pIdx}`, day_of_week: dayIdx,
                    start_hour: period.start_h, start_minute: period.start_m,
                    end_hour: period.end_h, end_minute: period.end_m, is_active: 1
                });
            }
        } else {
            currentClasses = currentClasses.filter(c => !(c.day_of_week === dayIdx && c.start_hour === period.start_h && c.start_minute === period.start_m));
        }
    });

    updateSummaryDeckMetrics();
    updateConsoleScheduleSummary(currentClasses, lastTelemetry ? lastTelemetry.day : null);

    const promises = periodIndices.map(pIdx =>
        fetch("/api/timetable/toggle", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                building: activeBuilding,
                level: activeLevel,
                room: activeRoom,
                day_of_week: dayIdx,
                period_index: pIdx,
                scope: activeScope,
                target_state: targetState
            })
        })
    );
    await Promise.all(promises);

    showToast(`${DAYS[dayIdx]} ${setOccupied ? 'FILLED' : 'CLEARED'} [${activeScope.toUpperCase()}]`);
    syncClassesSilently(activeRoom);
    fetchLogs();
}

async function applyPreset(presetName) {
    try {
        const res = await fetch("/api/timetable/preset", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                building: activeBuilding,
                level: activeLevel,
                room: activeRoom,
                scope: activeScope,
                preset: presetName
            })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`APPLIED PRESET '${presetName.toUpperCase()}' TO ${data.affected_rooms} ROOMS`);
            fetchRoomClasses(activeRoom);
            fetchLogs();
        }
    } catch (e) {
        console.error("applyPreset error:", e);
    }
}

async function clearScopeSchedule() {
    if (!confirm(`CONFIRM: Clear all timetable entries for scope [${activeScope.toUpperCase()}]?`)) return;

    try {
        const res = await fetch("/api/timetable/clear-scope", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                building: activeBuilding,
                level: activeLevel,
                room: activeRoom,
                scope: activeScope
            })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`CLEARED TIMETABLE ENTRIES FOR ${data.affected_rooms} ROOMS`);
            fetchRoomClasses(activeRoom);
            fetchLogs();
        }
    } catch (e) {
        console.error("clearScope error:", e);
    }
}

// --- i-Ma'luum Import ---
function openImaluumModal() {
    updateScopeModalText();
    openModal("modalImaluum");
}

async function executeImaluumImport() {
    const matric = document.getElementById("imaluumMatric").value.trim() || "2119988";
    const btn = document.getElementById("btnFetchImaluum");
    if (btn) btn.disabled = true;

    showToast("CONNECTING TO IMALUUM.IIUM.EDU.MY API...");

    try {
        const res = await fetch("/api/import/imaluum", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                building: activeBuilding,
                level: activeLevel,
                room: activeRoom,
                scope: activeScope,
                matric_no: matric
            })
        });
        const data = await res.json();
        if (res.ok) {
            closeModal("modalImaluum");
            showToast(`SUCCESS: IMPORTED ${data.imported_count} SESSIONS FROM I-MA'LUUM`);
            fetchRoomClasses(activeRoom);
            fetchLogs();
        } else {
            showToast("ERROR: I-MA'LUUM IMPORT FAILED");
        }
    } catch (e) {
        showToast("ERROR: I-MA'LUUM API CONNECTION REFUSED");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// =============================================================================
// EEPROM SCHEDULE DEPLOYMENT & CONSOLE SUMMARY
// =============================================================================
async function deploySchedule() {
    const isPoc = (activeRoom === "E1-2-14");
    if (isPoc) {
        showToast("TRANSMITTING 7-DAY EEPROM MATRIX TO DEV ATMEGA328P [USB]...");
    } else {
        showToast(`DISPATCHING 7-DAY SCHEDULE TO EDGE SWITCH [${activeRoom}] VIA MQTT/TLS...`);
    }

    try {
        const res = await fetch(`/api/deploy?room=${activeRoom}`, { method: "POST" });
        const data = await res.json();
        if (res.ok) {
            const count = (data.deployed && data.deployed.commands) ? data.deployed.commands.length : 8;
            if (isPoc) {
                showToast(`OK: 7-DAY EEPROM FLASHED TO DEV SWITCH [E1-2-14] // ${count} CMDS`);
                const ackEl = document.getElementById("consoleLastAck");
                if (ackEl) ackEl.textContent = "OK:POLICY_SAVED";
            } else {
                showToast(`OK: SCHEDULE DEPLOYED TO EDGE NODE [${activeRoom}] VIA MQTT/TLS // ${count} CMDS`);
                const ackEl = document.getElementById("consoleLastAck");
                if (ackEl) ackEl.textContent = `OK:EDGE_DEPLOY:${activeRoom}`;
            }
            fetchLogs();
        } else {
            showToast(isPoc ? "DEPLOYMENT FAILED: SERIAL DEVICE BUSY OR DISCONNECTED" : "DEPLOYMENT FAILED: EDGE BROKER UNREACHABLE");
        }
    } catch (e) {
        showToast("DEPLOYMENT ERROR: GATEWAY OFFLINE");
    }
}

async function setSwitchDay(dayCode) {
    try {
        const res = await fetch(`/api/hardware/day?day=${dayCode}`, { method: "POST" });
        if (res.ok) {
            showToast(`OK: SWITCH JUMPED TO ${dayCode}`);
            const ackEl = document.getElementById("consoleLastAck");
            if (ackEl) ackEl.textContent = `OK:DAY_SET:${dayCode}`;
            fetchLogs();
        } else {
            showToast("FAILED TO SET DAY: SERIAL DISCONNECTED");
        }
    } catch (e) {
        showToast("DAY SWITCH ERROR: GATEWAY OFFLINE");
    }
}

function updateConsoleScheduleSummary(classes, targetDayCode) {
    let targetIdx = (new Date().getDay() === 0) ? 6 : new Date().getDay() - 1;
    if (targetDayCode && DAY_CODES.indexOf(targetDayCode) !== -1) {
        targetIdx = DAY_CODES.indexOf(targetDayCode);
    }
    const dayClasses = classes.filter(c => c.day_of_week === targetIdx);

    const morning = dayClasses.filter(c => c.start_hour < 13);
    const afternoon = dayClasses.filter(c => c.start_hour >= 13);

    const s1El = document.getElementById("consoleSlot1Desc");
    const s2El = document.getElementById("consoleSlot2Desc");

    if (s1El) {
        if (morning.length > 0) {
            const sH = Math.min(...morning.map(c => c.start_hour));
            const sM = Math.min(...morning.filter(c => c.start_hour === sH).map(c => c.start_minute));
            const eH = Math.max(...morning.map(c => c.end_hour));
            const eM = Math.max(...morning.filter(c => c.end_hour === eH).map(c => c.end_minute));
            s1El.textContent = `ACTIVE (${pad(sH)}:${pad(sM)} - ${pad(eH)}:${pad(eM)})`;
        } else {
            s1El.textContent = "STANDBY (NO MORNING SESSIONS)";
        }
    }

    if (s2El) {
        if (afternoon.length > 0) {
            const sH = Math.min(...afternoon.map(c => c.start_hour));
            const sM = Math.min(...afternoon.filter(c => c.start_hour === sH).map(c => c.start_minute));
            const eH = Math.max(...afternoon.map(c => c.end_hour));
            const eM = Math.max(...afternoon.filter(c => c.end_hour === eH).map(c => c.end_minute));
            s2El.textContent = `ACTIVE (${pad(sH)}:${pad(sM)} - ${pad(eH)}:${pad(eM)})`;
        } else {
            s2El.textContent = "STANDBY (NO AFTERNOON SESSIONS)";
        }
    }
}

function pad(n) {
    return String(n).padStart(2, '0');
}

// =============================================================================
// WEBSOCKET TELEMETRY & HARDWARE DIGITAL TWIN
// =============================================================================
function initWebSocket() {
    if (sessionStorage.getItem("switch_auth") !== "true") {
        return; // Do not connect WebSocket if unauthenticated
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = sessionStorage.getItem("switch_token") || window.switchToken || '';
    const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry${tokenQuery}`;

    try {
        ws = new WebSocket(wsUrl);
    } catch (e) {
        console.warn("WebSocket init error:", e);
        return;
    }

    ws.onopen = () => {
        updateConnectionState(true);
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === "mode_change" && msg.mode) {
                applySystemModeUI(msg.mode, msg.data);
                if (msg.data) applyTelemetry(msg.data);
            } else if (msg.type === "telemetry" && msg.data) {
                applyTelemetry(msg.data);
            }
        } catch (e) {
            console.error("Telemetry parse error:", e);
        }
    };

    ws.onclose = (event) => {
        updateConnectionState(false);
        if (event && event.code === 1008) {
            // Policy violation / unauthorized
            sessionStorage.removeItem("switch_auth");
            sessionStorage.removeItem("switch_token");
            window.switchToken = null;
            const overlay = document.getElementById("authOverlay");
            if (overlay) overlay.style.display = "flex";
            return;
        }
        if (sessionStorage.getItem("switch_auth") === "true") {
            setTimeout(initWebSocket, 2000);
        }
    };

    ws.onerror = () => {
        updateConnectionState(false);
    };
}

function updateConnectionState(online) {
    const dot = document.getElementById("sidebarHwDot");
    const text = document.getElementById("sidebarHwText");
    if (dot) dot.classList.toggle("alert", !online);
    if (text) text.textContent = online ? "ONLINE" : "OFFLINE";
}

// Hardcoded +1 second display compensator to eliminate telemetry transmission & render latency
function advanceTimeOneSecond(timeStr) {
    if (!timeStr || typeof timeStr !== "string") return timeStr;
    const parts = timeStr.split(":");
    if (parts.length !== 3) return timeStr;
    let h = parseInt(parts[0], 10);
    let m = parseInt(parts[1], 10);
    let s = parseInt(parts[2], 10);
    if (isNaN(h) || isNaN(m) || isNaN(s)) return timeStr;

    s += 1;
    if (s >= 60) {
        s = 0;
        m += 1;
        if (m >= 60) {
            m = 0;
            h = (h + 1) % 24;
        }
    }
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

function applyTelemetry(data) {
    lastTelemetry = data;

    // Digital Clock (Compensated +1s for real-time visual alignment)
    const clockEl = document.getElementById("digitalClockDisplay");
    if (clockEl && data.time) {
        clockEl.textContent = advanceTimeOneSecond(data.time);
    }

    // Relays
    const boxLights = document.getElementById("boxRelayLights");
    const boxAC = document.getElementById("boxRelayAC");
    const boxStandby = document.getElementById("boxRelayStandby");

    if (boxLights) {
        boxLights.textContent = data.lights_on ? "ACTIVE" : "STANDBY";
        boxLights.classList.toggle("energized", data.lights_on);
    }
    if (boxAC) {
        boxAC.textContent = data.ac_on ? "ACTIVE" : "STANDBY";
        boxAC.classList.toggle("energized", data.ac_on);
    }
    if (boxStandby) {
        boxStandby.textContent = data.standby_on ? "ACTIVE" : "STANDBY";
        boxStandby.classList.toggle("energized", data.standby_on);
    }

    // Top State Badge
    const stateBadge = document.getElementById("switchStateBadge");
    if (stateBadge && data.state) {
        let label = `STATE: ${data.state.toUpperCase()}`;
        if (data.override_mode === 1) {
            const rem = data.timer_remaining_min !== undefined ? data.timer_remaining_min : 0;
            label = `STATE: FORCE ON [${rem}M REMAINING]`;
        } else if (data.override_mode === 2) {
            label = `STATE: FORCE OFF [EARLY VACATE]`;
        } else if (data.override_mode === 3) {
            label = `STATE: PRESENTATION [AC ONLY]`;
        }
        stateBadge.textContent = label;
    }

    // Last Ack
    const ackEl = document.getElementById("consoleLastAck");
    if (ackEl && data.last_ack) {
        ackEl.textContent = data.last_ack;
    }

    // Control Mode Buttons Highlighting (AUTO, FORCE_ON, FORCE_OFF, PRESENTATION)
    const mode = (data.override_mode !== undefined) ? data.override_mode : (data.manual_override ? 1 : 0);
    setControlModeUI(mode);

    // Speed Multiplier Buttons
    [1, 60, 600].forEach(f => {
        const btn = document.getElementById(`btnSpeed${f}`);
        if (btn) btn.classList.toggle("active", data.speed_factor === f);
    });

    // Diagnostics Feed
    const feed = document.getElementById("diagnosticsFeed");
    if (feed) {
        const line = `TLM:${data.time},${data.state},Y=${data.lights_on?1:0},B=${data.ac_on?1:0},R=${data.standby_on?1:0},OVERRIDE=${data.manual_override?1:0},SPEED=${data.speed_factor}\n`;
        feed.textContent = (line + feed.textContent).slice(0, 3000);
    }

    // Real-Time Connected Electrical Load (Watts & Amps)
    const loadWatts = (data.lights_on ? 480 : 0) + (data.ac_on ? 2200 : 0);
    const loadAmps = (loadWatts / 240.0) + (data.standby_on ? 0.02 : 0);

    const elLoad = document.getElementById("metricLiveLoad");
    const elLoadSub = document.getElementById("metricLiveLoadSub");
    const elCurrent = document.getElementById("metricLiveCurrent");

    if (elLoad) elLoad.textContent = `${loadWatts} W`;
    if (elCurrent) elCurrent.textContent = `${loadAmps.toFixed(2)} A`;
    if (elLoadSub) {
        if (loadWatts > 0) {
            elLoadSub.textContent = (data.lights_on && data.ac_on)
                ? "HVAC + LIGHTS ACTIVE"
                : (data.ac_on ? "HVAC PRE-COOLING ENGAGED" : "LIGHTING ONLY");
        } else {
            elLoadSub.textContent = "STANDBY // ZERO WASTE";
        }
    }

    // Automation Pipeline Progress Step
    document.querySelectorAll(".pipeline-step").forEach(step => step.classList.remove("active"));
    const stateUpper = (data.state || "").toUpperCase();
    if (stateUpper === "PRECOOL") {
        const s = document.getElementById("pipePrecool");
        if (s) s.classList.add("active");
    } else if (stateUpper === "CLASS" || data.manual_override) {
        const s = document.getElementById("pipeClass");
        if (s) s.classList.add("active");
    } else if (stateUpper === "GRACE" || stateUpper === "URGENT" || stateUpper === "WARNING") {
        let remainingSec = 999;

        if (stateUpper === "URGENT") {
            remainingSec = 5;
        } else if (stateUpper === "WARNING") {
            remainingSec = 30;
        } else if (data.time) {
            const timeParts = data.time.split(":").map(x => parseInt(x, 10));
            if (timeParts.length >= 2) {
                const curH = !isNaN(timeParts[0]) ? timeParts[0] : 0;
                const curM = !isNaN(timeParts[1]) ? timeParts[1] : 0;
                const curS = !isNaN(timeParts[2]) ? timeParts[2] : 0;
                const curTotalMin = curH * 60 + curM;

                const graceMin = parseInt(document.getElementById("policyGrace")?.value, 10) || 10;
                const candidateEnds = [700, 1030]; // Standard demo/class defaults (11:40, 17:10)

                const dayIdx = data.day ? DAY_CODES.indexOf(data.day) : -1;
                const dayClasses = (dayIdx !== -1 && currentClasses && currentClasses.length > 0)
                    ? currentClasses.filter(c => c.day_of_week === dayIdx)
                    : (currentClasses || []);

                dayClasses.forEach(c => {
                    if (c.end_hour !== undefined && c.end_minute !== undefined) {
                        candidateEnds.push(c.end_hour * 60 + c.end_minute + graceMin);
                    }
                });

                // Find candidate graceEndMin:
                // 1) Smallest future cutoff where (end - curTotalMin) <= graceMin
                let matchedEnd = candidateEnds
                    .filter(end => end >= curTotalMin && (end - curTotalMin) <= graceMin)
                    .sort((a, b) => a - b)[0];

                // 2) Fallback: if clock just crossed end (e.g. curTotalMin == end and curS > 0)
                if (!matchedEnd) {
                    matchedEnd = candidateEnds
                        .filter(end => Math.abs(end - curTotalMin) <= 1)
                        .sort((a, b) => Math.abs(a - curTotalMin) - Math.abs(b - curTotalMin))[0];
                }

                // 3) General fallback: closest candidate
                if (!matchedEnd) {
                    matchedEnd = candidateEnds.sort((a, b) => Math.abs(a - curTotalMin) - Math.abs(b - curTotalMin))[0];
                }

                remainingSec = (matchedEnd - curTotalMin) * 60 - curS;
            }
        }

        if (remainingSec <= 10) {
            // [ 5 ] URGENT ALERT (1S) - Final 10 seconds rapid countdown
            const s = document.getElementById("pipeGrace1");
            if (s) s.classList.add("active");
        } else if (remainingSec <= 60) {
            // [ 4 ] WARNING PULSE (5S) - Final 1 minute warning
            const s = document.getElementById("pipeGrace5");
            if (s) s.classList.add("active");
        } else {
            // [ 3 ] GRACE PING (15S) - General grace period
            const s = document.getElementById("pipeGrace15");
            if (s) s.classList.add("active");
        }
    } else {
        const s = document.getElementById("pipeStandby");
        if (s) s.classList.add("active");
    }

    // Active Day Badges & Matrix Highlighting
    if (data.day) {
        const dayIdx = DAY_CODES.indexOf(data.day);
        const dayNum = (dayIdx !== -1) ? dayIdx + 1 : 1;
        const dayName = (dayIdx !== -1) ? DAYS[dayIdx] : data.day;

        const dayBadge = document.getElementById("switchDayBadge");
        if (dayBadge) {
            dayBadge.textContent = `DAY: ${data.day} [DAY ${dayNum}]`;
        }

        const dayDesc = document.getElementById("consoleActiveDayDesc");
        if (dayDesc) {
            dayDesc.textContent = `${dayName} [DAY ${dayNum}]`;
        }

        document.querySelectorAll(".day-pill-btn").forEach(btn => {
            btn.classList.toggle("active", btn.textContent.trim() === data.day);
        });

        updateConsoleScheduleSummary(currentClasses, data.day);

        // Highlight active day row in matrix table
        document.querySelectorAll("#matrixTableBody tr.day-row").forEach((row, idx) => {
            const isToday = idx === ((new Date().getDay() === 0) ? 6 : new Date().getDay() - 1);
            const isSwitchActive = idx === dayIdx;
            row.classList.toggle("switch-active-day", isSwitchActive);
            const titleEl = row.querySelector(".col-day-header > div");
            if (titleEl) {
                titleEl.innerHTML = `
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span style="font-weight:800; font-size:0.75rem;">${DAYS[idx]}</span>
                        ${isSwitchActive ? '<span style="background:#fff; color:#000; padding:1px 4px; font-size:0.56rem; font-weight:700; width:fit-content; letter-spacing:0.02em;">ACTIVE ON SWITCH</span>' : (isToday ? '<span style="font-size:0.58rem; color:var(--text-dim);">[TODAY]</span>' : '')}
                    </div>
                `;
            }
        });
    }

    // Diagnostics Pin Inspector Badges
    const p13 = document.getElementById("pin13Badge");
    const p12 = document.getElementById("pin12Badge");
    const p11 = document.getElementById("pin11Badge");
    const p10 = document.getElementById("pin10Badge");
    const p9  = document.getElementById("pin9Badge");
    const p2  = document.getElementById("pin2Badge");

    if (p13) {
        p13.textContent = data.lights_on ? "HIGH [480W]" : "LOW";
        p13.classList.toggle("active", data.lights_on);
    }
    if (p12) {
        p12.textContent = data.ac_on ? "HIGH [2200W]" : "LOW";
        p12.classList.toggle("active", data.ac_on);
    }
    if (p11) {
        p11.textContent = data.standby_on ? "HIGH [STANDBY]" : "LOW";
        p11.classList.toggle("active", data.standby_on);
    }
    if (p10) {
        p10.textContent = data.manual_override ? "OVERRIDE" : "IDLE";
        p10.classList.toggle("active", data.manual_override);
    }
    if (p9) {
        p9.textContent = data.speed_factor > 1 ? `${data.speed_factor}X FAST` : "IDLE";
        p9.classList.toggle("active", data.speed_factor > 1);
    }
    if (p2) {
        p2.textContent = data.day ? `DAY ${data.day}` : "READY";
        p2.classList.toggle("active", true);
    }

    // --- 1/3 Width Tactical Hardware Digital Twin Telemetry ---
    if (data.mode) {
        applySystemModeUI(data.mode, data);
    }

    // 5641AS 7-Segment Display Module Readout
    const sevenSeg = document.getElementById("sevenSegDisplay");
    if (sevenSeg) {
        if (data.display_digits) {
            sevenSeg.textContent = data.display_digits;
        } else if (data.time) {
            sevenSeg.textContent = data.time.slice(0, 5);
        }
    }

    // 5mm Diffused LEDs Array
    const hwLedYellow = document.getElementById("hwLedYellow");
    const hwLedBlue = document.getElementById("hwLedBlue");
    const hwLedRed = document.getElementById("hwLedRed");
    const hwLedYellowState = document.getElementById("hwLedYellowState");
    const hwLedBlueState = document.getElementById("hwLedBlueState");
    const hwLedRedState = document.getElementById("hwLedRedState");

    if (hwLedYellow) {
        hwLedYellow.classList.toggle("active", !!data.lights_on);
        if (hwLedYellowState) hwLedYellowState.textContent = data.lights_on ? "ENERGIZED" : "OFF";
    }
    if (hwLedBlue) {
        hwLedBlue.classList.toggle("active", !!data.ac_on);
        if (hwLedBlueState) hwLedBlueState.textContent = data.ac_on ? "ENERGIZED" : "OFF";
    }
    if (hwLedRed) {
        hwLedRed.classList.toggle("active", !!data.standby_on);
        if (hwLedRedState) hwLedRedState.textContent = data.standby_on ? "ENERGIZED" : "STANDBY";
    }

    // Piezo Buzzer Transducer (Pin 3 PWM)
    const grill = document.getElementById("buzzerGrill");
    const harmonicText = document.getElementById("buzzerHarmonicText");
    if (grill) {
        grill.classList.toggle("active", !!data.buzzer_active);
    }
    if (harmonicText) {
        if (data.buzzer_active && data.buzzer_freq) {
            harmonicText.textContent = `${data.buzzer_freq} HZ ACTIVE`;
            playBuzzerTone(data.buzzer_freq, 60);
        } else {
            harmonicText.textContent = "SILENT // 0 HZ";
        }
    }
}

// =========================================================================
// HARDWARE DIGITAL TWIN CONTROLS & WEB AUDIO SYNTHESIZER
// =========================================================================
let audioCtx = null;
window.audioMuted = true;

function toggleAudioSynthesizer() {
    window.audioMuted = !window.audioMuted;
    const btn = document.getElementById("btnToggleAudioSynth");
    if (btn) {
        btn.textContent = window.audioMuted ? "BEEPER: MUTE" : "BEEPER: ON";
        btn.classList.toggle("btn-primary", !window.audioMuted);
    }
    if (!window.audioMuted && !audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
}

function playBuzzerTone(freq, durationMs = 60) {
    if (window.audioMuted) return;
    try {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === "suspended") audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "square"; // Realistic square harmonic of 5V passive piezo
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + (durationMs / 1000.0));
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + (durationMs / 1000.0));
    } catch (e) {
        console.debug("Web audio tone error:", e);
    }
}

function switchHardwareModel(model) {
    const stage = document.getElementById("hwVisualStage");
    const imgBench = document.getElementById("hwImgBench");
    const imgWall = document.getElementById("hwImgWall");
    const tabBench = document.getElementById("tabModelBench");
    const tabWall = document.getElementById("tabModelWall");

    const isWall = (model === "wall");
    if (stage) {
        stage.classList.toggle("model-bench", !isWall);
        stage.classList.toggle("model-wall", isWall);
        stage.setAttribute("data-active-model", isWall ? "wall" : "bench");
    }
    if (imgBench) imgBench.classList.toggle("active", !isWall);
    if (imgWall) imgWall.classList.toggle("active", isWall);
    if (tabBench) tabBench.classList.toggle("active", !isWall);
    if (tabWall) tabWall.classList.toggle("active", isWall);

    try {
        localStorage.setItem("switch_hw_model", isWall ? "wall" : "bench");
    } catch (e) {}
}

function applySystemModeUI(mode, hwState) {
    const workspace = document.getElementById("consoleWorkspace");
    const badge = document.getElementById("systemModeBadge");
    const sideMode = document.getElementById("sidebarModeText");

    if (mode === "physical") {
        if (workspace) {
            workspace.classList.remove("mode-twin");
            workspace.classList.add("mode-physical");
        }
        if (badge) {
            badge.textContent = "MODE: PHYSICAL BENCH";
            badge.style.borderColor = "#ffaa00";
            badge.style.color = "#ffaa00";
            badge.style.background = "#221100";
        }
        if (sideMode) {
            sideMode.textContent = "PHYSICAL BENCH";
            sideMode.style.color = "#ffaa00";
        }
    } else {
        if (workspace) {
            workspace.classList.remove("mode-physical");
            workspace.classList.add("mode-twin");
        }
        if (badge) {
            badge.textContent = "MODE: DIGITAL TWIN";
            badge.style.borderColor = "#00aa55";
            badge.style.color = "#00ff88";
            badge.style.background = "#001a11";
        }
        if (sideMode) {
            sideMode.textContent = "DIGITAL TWIN";
            sideMode.style.color = "#00ff88";
        }
    }
}

let btnHoldTimers = {};

function triggerButtonPulse(btnId) {
    const btn = document.getElementById(`hwBtn${btnId}`);
    const gpioVal = document.getElementById(`hwBtn${btnId}State`);
    if (btn) btn.classList.add("pressed");
    if (gpioVal) {
        gpioVal.textContent = "GND [LOW]";
        gpioVal.style.color = "#ff4444";
    }
    setTimeout(() => {
        if (btn) btn.classList.remove("pressed");
        if (gpioVal) {
            gpioVal.textContent = "PULLUP";
            gpioVal.style.color = "#00ff88";
        }
    }, 250);
}

function hwButtonDown(btnId) {
    const btn = document.getElementById(`hwBtn${btnId}`);
    if (btn) btn.classList.add("pressed");
    const gpioVal = document.getElementById(`hwBtn${btnId}State`);
    if (gpioVal) {
        gpioVal.textContent = "GND [LOW]";
        gpioVal.style.color = "#ff4444";
    }
    btnHoldTimers[btnId] = { start: Date.now(), held: false };
    const holdDuration = btnId === 3 ? 600 : (btnId === 1 ? 1200 : 1000);

    btnHoldTimers[btnId].timeout = setTimeout(() => {
        btnHoldTimers[btnId].held = true;
        sendHardwareButton(btnId, "hold");
        playBuzzerTone(3200, 80);
    }, holdDuration);
}

function hwButtonUp(btnId) {
    const btn = document.getElementById(`hwBtn${btnId}`);
    if (btn) btn.classList.remove("pressed");
    const gpioVal = document.getElementById(`hwBtn${btnId}State`);
    if (gpioVal) {
        gpioVal.textContent = "PULLUP";
        gpioVal.style.color = "#00ff88";
    }
    if (btnHoldTimers[btnId]) {
        clearTimeout(btnHoldTimers[btnId].timeout);
    }
}

function hwButtonClick(btnId) {
    if (btnHoldTimers[btnId] && btnHoldTimers[btnId].held) {
        btnHoldTimers[btnId].held = false;
        return; // Handled as hold
    }
    triggerButtonPulse(btnId);
    sendHardwareButton(btnId, "tap");
    playBuzzerTone(2800, 30);
}

async function sendHardwareButton(btnId, action) {
    triggerButtonPulse(btnId);
    try {
        await fetch("/api/hardware/button", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ button_id: btnId, action: action })
        });
    } catch (e) {
        console.error("Hardware button dispatch error:", e);
    }
}

window.switchHardwareModel = switchHardwareModel;
window.applySystemModeUI = applySystemModeUI;
window.hwButtonDown = hwButtonDown;
window.hwButtonUp = hwButtonUp;
window.hwButtonClick = hwButtonClick;
window.sendHardwareButton = sendHardwareButton;
window.toggleAudioSynthesizer = toggleAudioSynthesizer;
window.playBuzzerTone = playBuzzerTone;


async function fetchStatus() {
    try {
        const res = await fetch(`/api/status?room=${activeRoom}`);
        if (res.ok) {
            const data = await res.json();
            if (data.hardware) applyTelemetry(data.hardware);
        }
    } catch (e) {
        console.error("fetchStatus error:", e);
    }
}

// --- Hardware Control API Calls ---
function setControlModeUI(mode) {
    const btnAuto = document.getElementById("btnModeAuto") || document.getElementById("btnAutoMode");
    const btnForceOn = document.getElementById("btnModeForceOn") || document.getElementById("btnManualOverride");
    const btnForceOff = document.getElementById("btnModeForceOff");
    const btnPres = document.getElementById("btnModePres");

    if (btnAuto) btnAuto.classList.toggle("btn-primary", mode === 0);
    if (btnForceOn) btnForceOn.classList.toggle("btn-primary", mode === 1);
    if (btnForceOff) btnForceOff.classList.toggle("btn-primary", mode === 2);
    if (btnPres) btnPres.classList.toggle("btn-primary", mode === 3);
}

async function setAutoMode() {
    setControlModeUI(0);
    try {
        const res = await fetch("/api/override/auto", { method: "POST" });
        if (res.ok) {
            showToast("RETURNED TO EEPROM SCHEDULE AUTO MODE");
            fetchStatus();
        }
    } catch (e) {
        showToast("COMMAND ERROR");
    }
}

async function setForceOn(minutes = null) {
    let dur = minutes;
    if (dur === null) {
        const foInput = document.getElementById("policyForceOn");
        dur = foInput ? parseInt(foInput.value, 10) || 60 : 60;
    }
    setControlModeUI(1);
    try {
        const res = await fetch("/api/override/force-on", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ minutes: dur })
        });
        if (res.ok) {
            showToast(`FORCE ON ENGAGED (${dur} MIN AUTO-OFF TIMER)`);
            fetchStatus();
        }
    } catch (e) {
        showToast("COMMAND ERROR");
    }
}

async function setForceOff() {
    setControlModeUI(2);
    try {
        const res = await fetch("/api/override/force-off", { method: "POST" });
        if (res.ok) {
            showToast("FORCE OFF ENGAGED (AUTO RESYNC AT SESSION END)");
            fetchStatus();
        }
    } catch (e) {
        showToast("COMMAND ERROR");
    }
}

async function setPresentationMode() {
    setControlModeUI(3);
    try {
        const res = await fetch("/api/override/presentation", { method: "POST" });
        if (res.ok) {
            showToast("PRESENTATION MODE ENGAGED (LIGHTS OFF, AC ON)");
            fetchStatus();
        }
    } catch (e) {
        showToast("COMMAND ERROR");
    }
}

async function toggleManualOverride() {
    const btnAuto = document.getElementById("btnModeAuto") || document.getElementById("btnAutoMode");
    const isAuto = btnAuto && btnAuto.classList.contains("btn-primary");
    if (isAuto) {
        await setForceOn(60);
    } else {
        await setAutoMode();
    }
}

async function syncHostClock() {
    try {
        const res = await fetch("/api/clock/sync", { method: "POST" });
        const data = await res.json();
        if (res.ok) showToast(`CLOCK SYNCHRONIZED: ${data.synced_time}`);
    } catch (e) {
        showToast("SYNC FAILED");
    }
}

async function testBuzzer(freq = 2200, duration = 120) {
    try {
        const res = await fetch(`/api/hardware/beep?freq=${freq}&duration=${duration}`, { method: "POST" });
        if (res.ok) {
            showToast(`BEEPER TEST DISPATCHED [PIN 3 // ${freq}Hz]`);
        } else {
            showToast("BEEPER TEST FAILED - CHECK SERIAL");
        }
    } catch (e) {
        showToast("BEEPER COMMAND ERROR");
    }
}

async function setSpeed(factor) {
    try {
        const res = await fetch("/api/speed", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ factor: factor })
        });
        if (res.ok) showToast(`ACCELERATION SET TO ${factor}X`);
    } catch (e) {
        showToast("SPEED COMMAND ERROR");
    }
}

async function setDemoTime(hour, minute, second = 0, day = "MON") {
    // Instant optimistic visual feedback on pipeline progress
    document.querySelectorAll(".pipeline-step").forEach(step => step.classList.remove("active"));
    if (hour === 8 && minute <= 30) {
        const s = document.getElementById("pipePrecool");
        if (s) s.classList.add("active");
    } else if ((hour === 8 && minute > 30) || (hour >= 9 && hour < 11) || (hour === 11 && minute < 30)) {
        const s = document.getElementById("pipeClass");
        if (s) s.classList.add("active");
    } else if (hour === 11 && minute >= 30 && minute < 40) {
        const remSec = (40 - minute) * 60 - second;
        let s = document.getElementById("pipeGrace15");
        if (remSec <= 10) {
            s = document.getElementById("pipeGrace1");
        } else if (remSec <= 60) {
            s = document.getElementById("pipeGrace5");
        }
        if (s) s.classList.add("active");
    } else {
        const s = document.getElementById("pipeStandby");
        if (s) s.classList.add("active");
    }

    // Optimistic Day UI switch (defaults to Monday for schedule replication)
    if (day) {
        const dayIdx = DAY_CODES.indexOf(day);
        const dayNum = (dayIdx !== -1) ? dayIdx + 1 : 1;
        const dayName = (dayIdx !== -1) ? DAYS[dayIdx] : day;
        const dayBadge = document.getElementById("switchDayBadge");
        if (dayBadge) dayBadge.textContent = `DAY: ${day} [DAY ${dayNum}]`;
        const dayDesc = document.getElementById("consoleActiveDayDesc");
        if (dayDesc) dayDesc.textContent = `${dayName} [DAY ${dayNum}]`;
        document.querySelectorAll(".day-pill-btn").forEach(btn => {
            btn.classList.toggle("active", btn.textContent.trim() === day);
        });
        updateConsoleScheduleSummary(currentClasses, day);
    }

    try {
        const payload = { hour: hour, minute: minute, second: second };
        if (day) payload.day = day;
        const res = await fetch("/api/clock/set", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            const hStr = String(hour).padStart(2, '0');
            const mStr = String(minute).padStart(2, '0');
            const sStr = String(second).padStart(2, '0');
            showToast(`DEMO JUMP -> ${day ? day + ' ' : ''}${hStr}:${mStr}:${sStr}`);
            fetchLogs();
        } else {
            showToast("TIME SET FAILED");
        }
    } catch (e) {
        showToast("TIME SET ERROR");
    }
}

function updateNightSweepButton(cutoffStr) {
    const sweepBtn = document.getElementById("btnNightSweepDemo");
    if (!sweepBtn) return;

    let [h, m] = (cutoffStr || "00:00").split(":").map(x => parseInt(x, 10));
    if (isNaN(h)) h = 0;
    if (isNaN(m)) m = 0;

    // Calculate 10 seconds behind (h:m:00 minus 10 seconds)
    let totalSec = (h * 3600 + m * 60 - 10 + 86400) % 86400;
    let targetH = Math.floor(totalSec / 3600);
    let targetM = Math.floor((totalSec % 3600) / 60);
    let targetS = totalSec % 60;

    const hStr = String(targetH).padStart(2, '0');
    const mStr = String(targetM).padStart(2, '0');
    const sStr = String(targetS).padStart(2, '0');

    const timeSpan = sweepBtn.querySelector(".demo-jump-time");
    if (timeSpan) {
        timeSpan.textContent = `${hStr}:${mStr}:${sStr}`;
    } else {
        sweepBtn.textContent = `${hStr}:${mStr}:${sStr} SWEEP`;
    }
    sweepBtn.title = `Night sweep test: Jumps to 10s before ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')} curfew cutoff (1100Hz warning pulses)`;
    sweepBtn.dataset.hour = targetH;
    sweepBtn.dataset.minute = targetM;
    sweepBtn.dataset.second = targetS;
}

async function triggerNightSweepDemo() {
    const sweepBtn = document.getElementById("btnNightSweepDemo");
    let h = 23, m = 59, s = 50;
    if (sweepBtn && sweepBtn.dataset.hour !== undefined) {
        h = parseInt(sweepBtn.dataset.hour, 10);
        m = parseInt(sweepBtn.dataset.minute, 10);
        s = parseInt(sweepBtn.dataset.second, 10);
    }

    // Step 1: Jump clock to 10 seconds before night sweep curfew on Monday
    await setDemoTime(h, m, s, "MON");

    // Step 2: If utilities were off (Standby), engage FORCE_ON so evaluators
    // visually witness the Night Sweep countdown and subsequent hard cutoff terminating active loads!
    if (lastTelemetry && !lastTelemetry.lights_on && !lastTelemetry.ac_on) {
        try {
            await fetch("/api/hardware/force_on", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ minutes: 60 })
            });
        } catch (e) {
            console.error("Force ON post-jump error:", e);
        }
    }
}

// =============================================================================
// ENERGY METRICS & AUDIT LOGS
// =============================================================================
function updateEnergySavings() {
    if (lastTelemetry && (lastTelemetry.state === "STANDBY" || (!lastTelemetry.lights_on && !lastTelemetry.ac_on))) {
        sessionIdleSeconds++;
    }

    // Weekly schedule avoidance baseline (63 open room hours minus scheduled class hours)
    const occupiedCount = currentClasses ? currentClasses.length : 9;
    const weeklyAvoidedHours = Math.max(0, 63.0 - (occupiedCount * 1.5));
    const weeklyAvoidedKwh = weeklyAvoidedHours * AVOIDED_POWER_KW;

    const liveKwh = (sessionIdleSeconds / 3600) * AVOIDED_POWER_KW;
    const totalKwh = weeklyAvoidedKwh + liveKwh;
    const totalCost = totalKwh * TARIFF_PER_KWH;
    const totalCo2 = totalKwh * CO2_PER_KWH;

    const elKwh = document.getElementById("metricAvoidedKwh");
    const elCost = document.getElementById("metricCostSaved");
    const elCo2 = document.getElementById("metricCo2Abated");

    if (elKwh) elKwh.textContent = `${totalKwh.toFixed(2)} KWH`;
    if (elCost) elCost.textContent = `RM ${totalCost.toFixed(2)}`;
    if (elCo2) elCo2.textContent = `${totalCo2.toFixed(2)} KG`;
}

async function fetchLogs() {
    try {
        const res = await fetch("/api/logs?limit=25");
        if (res.ok) {
            const logs = await res.json();
            const tbody = document.getElementById("logTableBody");
            if (!tbody) return;
            tbody.innerHTML = logs.map(l => `
                <tr>
                    <td style="color:#888;">${l.timestamp.split(' ')[1] || l.timestamp}</td>
                    <td style="font-weight:700; color:#fff;">[ ${l.event_type} ]</td>
                    <td style="color:#bbb;">${l.message}</td>
                </tr>
            `).join('');
        }
    } catch (e) {
        console.error("fetchLogs error:", e);
    }
}

// --- Policy Config ---
async function fetchPolicy() {
    try {
        const res = await fetch(`/api/status?room=${activeRoom}`);
        if (res.ok) {
            const data = await res.json();
            if (data.policy) {
                const pc = document.getElementById("policyPrecool");
                const gr = document.getElementById("policyGrace");
                const mc = document.getElementById("policyMidnightCutoff");
                const fo = document.getElementById("policyForceOn");
                if (pc) pc.value = data.policy.precool_minutes;
                if (gr) gr.value = data.policy.grace_minutes;
                if (mc) mc.value = data.policy.midnight_cutoff || "00:00";
                const fom = data.policy.force_on_minutes || 60;
                if (fo) fo.value = fom;

                const cPc = document.getElementById("consolePrecoolVal");
                const cGr = document.getElementById("consoleGraceVal");
                const cMc = document.getElementById("consoleMidnightVal");
                const cFo = document.getElementById("consoleForceOnVal");
                if (cPc) cPc.textContent = `${data.policy.precool_minutes} MINUTES PRIOR`;
                if (cGr) cGr.textContent = `${data.policy.grace_minutes} MINUTES POST`;
                if (cMc) cMc.textContent = `${data.policy.midnight_cutoff || "00:00"} (12:00 AM)`;
                if (cFo) cFo.textContent = `${fom} MINUTES`;

                const btnFo = document.getElementById("btnModeForceOn");
                if (btnFo) btnFo.textContent = `FORCE ON (+${fom}M)`;

                updateNightSweepButton(data.policy.midnight_cutoff || "00:00");
            }
        }
    } catch (e) {
        console.error("fetchPolicy error:", e);
    }
}

async function savePolicy() {
    const pc = parseInt(document.getElementById("policyPrecool").value) || 10;
    const gr = parseInt(document.getElementById("policyGrace").value) || 10;
    const mc = document.getElementById("policyMidnightCutoff") ? document.getElementById("policyMidnightCutoff").value || "00:00" : "00:00";
    const fo = parseInt(document.getElementById("policyForceOn").value) || 60;

    try {
        const res = await fetch("/api/policy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ precool_minutes: pc, grace_minutes: gr, midnight_cutoff: mc, force_on_minutes: fo })
        });
        if (res.ok) {
            closeModal("modalPolicy");
            showToast(`POLICY UPDATED: PRE-COOL ${pc}m, GRACE ${gr}m, SWEEP ${mc}, FORCE-ON ${fo}m`);
            updateNightSweepButton(mc);
            fetchPolicy();
            fetchLogs();
        }
    } catch (e) {
        showToast("POLICY SAVE ERROR");
    }
}

// =============================================================================
// MODAL & TOAST SYSTEM
// =============================================================================
function openModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.add("open");
}

function closeModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.remove("open");
}

function showToast(msg) {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = `[ ${msg} ]`;
    container.appendChild(t);

    setTimeout(() => {
        t.style.opacity = "0";
        t.style.transition = "opacity 0.2s";
        setTimeout(() => t.remove(), 200);
    }, 3500);
}
// =============================================================================
// TACTICAL DIAGNOSTICS & RAW ASCII COMMAND CONSOLE
// =============================================================================
function clearTerminalFeed() {
    const feed = document.getElementById("diagnosticsFeed");
    if (feed) feed.textContent = "";
}

async function sendManualSerialCmd() {
    const input = document.getElementById("txtSerialCmd");
    if (!input) return;
    const cmd = input.value.trim();
    if (!cmd) return;
    try {
        const res = await fetch("/api/diagnostics/command", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: cmd })
        });
        if (res.ok) {
            showToast(`SENT -> ${cmd}`);
            input.value = "";
            const feed = document.getElementById("diagnosticsFeed");
            if (feed) {
                feed.textContent = `>>> ${cmd}\n` + feed.textContent;
            }
        } else {
            showToast("COMMAND TRANSMIT FAILED");
        }
    } catch (e) {
        showToast("TRANSMIT ERROR");
    }
}
