# Security Architecture Specification
## In-Wall Smart Switch Edge Gateway & Cloud Reverse Tunnel

**Document Reference:** SEC-SPEC-01  
**Target Hosts:** `automated-in-wall-switch` (Edge Controller) & `spearoflonginus` (`switch-vps`, Azure VPS)  
**Security Baseline:** September 2026 Audit (Score: 9.2 / 10)

---

## 1. Threat Model & Perimeter Overview

The automated switch infrastructure spans two physical and network domains:
1. **Edge Gateway Controller (Local Facility / Academic Building):**
   - Direct serial hardware link to ATmega328P microcontroller (`/dev/ttyACM0`).
   - Runs the FastAPI web application, digital twin state engine, and SQLite audit database.
   - Outbound-only SSH reverse tunnel connection to the cloud VPS (zero inbound ports required on the local campus network).
2. **Cloud Reverse Proxy & Ingress Gateway (`spearoflonginus` / Azure VPS):**
   - Public-facing reverse proxy (`switch.imankh.me`, `dash.imankh.me`, `vpn.imankh.me`).
   - Terminates TLS/HTTPS, enforces access restrictions, and proxies traffic over loopback tunnels to the edge gateway.

```
[ Public Client ]
       |
       | HTTPS (Port 443 / TLS 1.2+1.3)
       v
[ Azure VPS: spearoflonginus (172.197.248.126) ]
  +-- UFW & Azure NSG (Default Deny)
  +-- Fail2ban (Port 8443 / 22)
  +-- Nginx Reverse Proxy
        +-- ssl_reject_handshake on (Direct IP scanner drop)
        +-- Let's Encrypt ECDSA P-256 (Auto-renewed by certbot.timer)
        +-- Security Headers (HSTS Preload, nosniff, SAMEORIGIN)
        |
        | Reverse Tunnel (127.0.0.1:8000)
        v
[ Edge Gateway Controller (automated-in-wall-switch) ]
  +-- FastAPI REST API (server.py)
        +-- require_auth Dependency Gate
        +-- HMAC-SHA256 Cryptographic Session Tokens
        +-- Passcode Verification (/api/login)
  +-- WebSocket Telemetry Hub (/ws/telemetry?token=...)
  +-- USB Serial CDC Bridge (serial_bridge.py)
        |
        v
[ Microcontroller Switch (ATmega328P) ]
```

---

## 2. Edge Gateway Authentication & Session Lifecycle

### 2.1 Cryptographic Session Tokens
- **Mechanism:** HMAC-SHA256 signed bearer tokens.
- **Generation:** Issued upon successful verification of the control passcode at `/api/login`.
- **Payload:** Contains client origin, issue timestamp (`iat`), and expiration epoch (`exp`).
- **Storage:** Frontend retains the token in volatile `sessionStorage` (purged on browser tab closure).

### 2.2 Endpoint Protection Matrix
All state mutations, administrative overrides, and system commands require the HTTP header:
`Authorization: Bearer <session_token>`

| Endpoint | Method | Role | Auth Required |
| :--- | :--- | :--- | :--- |
| `/api/login` | POST | Authentication gate & token issuance | Public |
| `/api/verify` | GET | Token validity check | Bearer Token |
| `/api/status` | GET | Real-time state & telemetry read | Public (Read-Only) |
| `/api/override/*` | POST | Manual Relay 1 / Relay 2 toggle | Bearer Token |
| `/api/deploy` | POST | Timetable compilation & hardware sync | Bearer Token |
| `/api/policy` | POST | Operational policy reconfiguration | Bearer Token |
| `/api/classes/*` | POST/DEL | Course schedule adjustments | Bearer Token |
| `/api/clock/*` | POST | Simulation acceleration & time offset | Bearer Token |
| `/api/hardware/*` | POST | Factory reset, EEPROM flush | Bearer Token |
| `/api/speed` | POST | Simulation multiplier setting | Bearer Token |
| `/api/diagnostics/command` | POST | Direct AT-command execution | Bearer Token |
| `/api/logs` | GET | System audit trail inspection | Bearer Token |
| `/ws/telemetry` | WS | Real-time sensor & relay push stream | Token Required |

---

## 3. Cloud Perimeter & SSL / TLS Infrastructure

### 3.1 Certificate Authority & Lifecycle
- **Provider:** Let's Encrypt (ISRG Root X1).
- **Type:** Domain Validated (DV) multi-domain SAN (`imankh.me`, `dash.imankh.me`, `switch.imankh.me`, `vpn.imankh.me`).
- **Key Spec:** ECDSA (Elliptic Curve P-256).
- **Cost:** Free ($0.00 / perpetual).
- **Automated Renewal:** Managed via systemd service `certbot.timer` running twice daily. Automatically triggers ACME HTTP-01 renewal challenges 30 days prior to expiry.

### 3.2 TLS Hardening Standards
- **Protocols:** Strictly `TLSv1.2` and `TLSv1.3`. All legacy protocols (`SSLv3`, `TLSv1.0`, `TLSv1.1`) disabled.
- **Ciphers:** Forward Secrecy (PFS) suites only (`ECDHE-ECDSA-AES128-GCM-SHA256`, `ECDHE-ECDSA-AES256-GCM-SHA384`, `ECDHE-ECDSA-CHACHA20-POLY1305`).
- **HSTS:** `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` always enforced.
- **Anti-Reconnaissance:** `/etc/nginx/conf.d/00-default.conf` configures `ssl_reject_handshake on` for port 443 and `return 444` for port 80. Raw IP scanner probes (Shodan, Censys) fail at the TLS handshake level without receiving certificate details or web banners.

---

## 4. Azure VPS System Hardening (`spearoflonginus`)

### 4.1 Host Firewall (UFW) & Filtering
- Default Incoming: `DENY`
- Default Outgoing: `ALLOW`
- Allowed Inbound Ports:
  - `80/tcp` (HTTP - ACME renewal & redirect)
  - `443/tcp` (HTTPS - Nginx reverse proxy)
  - `8443/tcp` (Hardened OpenSSH management port)
  - `22/tcp` (Emergency console fallback)

### 4.2 SSH Hardening & Intrusion Prevention
- Config: `/etc/ssh/sshd_config.d/99-hardened.conf`
- Authentication: Strict public-key only (`PasswordAuthentication no`, `PermitRootLogin no`, `MaxAuthTries 4`).
- Ciphers: `chacha20-poly1305@openssh.com,aes256-gcm@openssh.com`.
- Fail2ban: Active `sshd` jail monitoring ports 8443 and 22 via systemd journal backend. Known operator IPs whitelisted.

### 4.3 VPN Gateway & Isolation (Sing-Box)
- Service runs VLESS WebSocket transport on `127.0.0.1:10000` behind Nginx SSL.
- Config file `/etc/sing-box/config.json` restricted to `0600` (root-only access).
- Anti-SSRF routing rules explicitly block access to:
  - Private RFC1918 subnets (`ip_is_private`)
  - Loopback networks (`127.0.0.0/8`)
  - Azure Instance Metadata Service (`169.254.169.254/32`)
- DNS upstream configured to Cloudflare TLS (`1.1.1.1`) with `prefer_ipv4`.

### 4.4 VPS Stats Daemon
- Service `/etc/systemd/system/vps-stats.service` executes under dedicated unprivileged system user `vps-stats:vps-stats`.
- Local binding only (`127.0.0.1:9090`).
- CORS locked to `https://dash.imankh.me` (wildcard origin removed).
