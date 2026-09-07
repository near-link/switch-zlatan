#!/bin/bash
set -e

PORT="${1:-/dev/ttyACM0}"
SKETCH_DIR="$(dirname "$0")/smart_switch"

echo "⚡ Preparing to flash firmware to Arduino Uno on $PORT..."

# 1. Check and release port lock if held by background server/bridge
HOLDERS=$(sg dialout -c "fuser '$PORT' 2>/dev/null" 2>/dev/null | tr -d ' ' || true)
if [ -n "$HOLDERS" ]; then
    echo "⚠️ Port $PORT is held by process(es): $HOLDERS. Releasing serial port..."
    pkill -9 -f "uvicorn" 2>/dev/null || true
    pkill -9 -f "web.server" 2>/dev/null || true
    kill -9 $HOLDERS 2>/dev/null || true
    sleep 1.2
fi

# 2. Compile sketch
echo "🔨 Compiling sketch..."
arduino-cli compile --fqbn arduino:avr:uno "$SKETCH_DIR"

# 3. Upload sketch with dialout permissions
echo "⚡ Flashing firmware to $PORT..."
if groups | grep -q "\bdialout\b"; then
    arduino-cli upload -p "$PORT" --fqbn arduino:avr:uno "$SKETCH_DIR"
else
    sg dialout -c "arduino-cli upload -p '$PORT' --fqbn arduino:avr:uno '$SKETCH_DIR'"
fi

echo "✅ Flash successful! Arduino Uno restored and active."

