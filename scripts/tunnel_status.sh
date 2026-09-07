#!/usr/bin/env bash
# scripts/tunnel_status.sh - Check if public tunnel is active

if pgrep -x "cloudflared" > /dev/null; then
    URL=$(grep -o 'https://[-a-zA-Z0-9.]*trycloudflare.com' /tmp/cloudflared.log 2>/dev/null | tail -n 1)
    echo "[+] TUNNEL IS ONLINE"
    echo "    URL: ${URL:-Unknown (check /tmp/cloudflared.log)}"
else
    echo "[-] TUNNEL IS OFFLINE (Private local-only mode)"
fi
