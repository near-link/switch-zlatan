#!/usr/bin/env bash
# connect_hardware.sh - Connect physical Arduino Uno to 24/7 cloud switch gateway
set -e
cd "$(dirname "$0")"

# Load local .env configuration if present
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

PORT="${SERIAL_PORT:-/dev/ttyACM0}"
GATEWAY="${GATEWAY_URL:-wss://switch.imankh.me/ws/hardware-bridge}"
TOKEN="${WEB_PASSWORD:-123}"

echo "================================================="
echo "   In-Wall Switch // Physical Hardware Bridge"
echo "================================================="
echo "Target Port:    ${PORT} (Arduino Uno R3)"
echo "Cloud Gateway:  ${GATEWAY}"
echo "================================================="
echo "[*] Connecting physical hardware to cloud..."
echo "[*] Press Ctrl+C at any time to disconnect."
echo ""

sg dialout -c "uv run --with pyserial --with websockets python -m web.hardware_bridge_client \
    --port '${PORT}' \
    --url '${GATEWAY}' \
    --token '${TOKEN}'"
