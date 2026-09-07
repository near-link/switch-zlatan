#!/usr/bin/env bash
# scripts/tunnel_start.sh - Launch temporary secure public tunnel

if pgrep -x "cloudflared" > /dev/null; then
    echo "[!] Cloudflare tunnel is already running."
    CURRENT_URL=$(grep -o 'https://[-a-zA-Z0-9.]*trycloudflare.com' /tmp/cloudflared.log 2>/dev/null | tail -n 1)
    if [ -n "$CURRENT_URL" ]; then
        echo "[+] Active Public URL: $CURRENT_URL"
    fi
    exit 0
fi

echo "[*] Launching Cloudflare Tunnel (HTTP/2 mode) for http://127.0.0.1:8000..."
rm -f /tmp/cloudflared.log
setsid cloudflared tunnel --url http://127.0.0.1:8000 > /tmp/cloudflared.log 2>&1 &
PID=$!
echo "[+] Tunnel process started (PID: $PID)"

echo -n "[*] Negotiating tunnel with Cloudflare"
for i in {1..20}; do
    URL=$(grep -o 'https://[-a-zA-Z0-9.]*trycloudflare.com' /tmp/cloudflared.log 2>/dev/null | tail -n 1)
    if [ -n "$URL" ]; then
        # Give connection 2 seconds to register edge routes
        sleep 2
        echo ""
        echo "=================================================================="
        echo "  PUBLIC DEMO URL (HTTPS / WSS):"
        echo "  $URL"
        echo "=================================================================="
        echo "[*] Open this link on your phone or share with evaluators."
        echo "[*] To stop the tunnel at any time, run: ./scripts/tunnel_stop.sh"
        exit 0
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "[-] Timed out waiting for tunnel URL. Check /tmp/cloudflared.log"
exit 1
