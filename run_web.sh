#!/bin/bash
set -e
cd "$(dirname "$0")"

# Load local .env configuration if present
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$HOST_IP" ]; then
    HOST_IP="127.0.0.1"
fi

# Tunnel and network parameters
ENABLE_TUNNEL="${ENABLE_TUNNEL:-true}"
if [ "$1" = "--local" ] || [ "$1" = "--no-tunnel" ]; then
    ENABLE_TUNNEL=false
fi

TUNNEL_HOST="${TUNNEL_HOST:-remote-vps}"
TUNNEL_DOMAIN="${TUNNEL_DOMAIN:-localhost}"
TUNNEL_PORT="${TUNNEL_PORT:-8000}"
GATEWAY_HOST="${GATEWAY_HOST:-0.0.0.0}"
GATEWAY_PORT="${GATEWAY_PORT:-8000}"
SERIAL_PORT="${SERIAL_PORT:-/dev/ttyACM0}"

TUNNEL_PID=""
cleanup() {
    if [ -n "$TUNNEL_PID" ] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
        echo -e "\n[Cloud Tunnel] Closing reverse tunnel..."
        kill "$TUNNEL_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

if [ "$ENABLE_TUNNEL" = true ] && [ -n "$TUNNEL_HOST" ] && [ "$TUNNEL_DOMAIN" != "localhost" ]; then
    echo "[Cloud Tunnel] Connecting to ${TUNNEL_DOMAIN} (${TUNNEL_HOST})..."
    ssh -N -R "${TUNNEL_PORT}:localhost:${GATEWAY_PORT}" "$TUNNEL_HOST" >/dev/null 2>&1 &
    TUNNEL_PID=$!
    sleep 1
    if kill -0 "$TUNNEL_PID" 2>/dev/null; then
        echo "[Cloud Tunnel] Reverse tunnel successfully established!"
    else
        echo "[Cloud Tunnel] Warning: Failed to connect to cloud tunnel (check internet/host)."
    fi
fi

echo ""
echo "================================================="
echo "   Smart Switch Controller Online"
echo "================================================="
echo "Local URL:    http://localhost:${GATEWAY_PORT}"
echo "Network URL:  http://${HOST_IP}:${GATEWAY_PORT}"
if [ "$ENABLE_TUNNEL" = true ] && [ "$TUNNEL_DOMAIN" != "localhost" ]; then
    echo "Public Cloud: https://${TUNNEL_DOMAIN}"
fi
echo "Device Port:  ${SERIAL_PORT} (Arduino Uno R3)"
echo "================================================="
echo ""

sg dialout -c "uv run --with fastapi --with 'uvicorn[standard]' --with websockets --with pyserial python -m uvicorn web.server:app --host ${GATEWAY_HOST} --port ${GATEWAY_PORT} --reload"
