#!/usr/bin/env bash
# scripts/tunnel_stop.sh - Immediately close the public tunnel

pkill -f "cloudflared" 2>/dev/null || true
rm -f /tmp/cloudflared.log
echo "[+] Cloudflare tunnel stopped. The public URL is now closed and unreachable."

