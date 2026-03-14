# Handoff — win_rev_claude

## Project Purpose

Local PowerShell scripts for onboarding and provisioning the `dawdaw-clwd` Windows Server 2022 VPS. Handles: SSH setup, bore tunnel, TwinCAT 3.1 installation, and initial VPS structure.

The AI agent factory (Claude Code agents, manage.ps1, etc.) lives **on the VPS** at `C:\agents\`, not in this repo.

---

## Current State (2026-03-14)

### VPS: dawdaw-clwd — FULLY OPERATIONAL
- **SSH access:** `ssh vps` → bore tunnel on port 38472 (auto-recovers via watchdog)
- **Claude Code:** v2.1.75, authenticated as `kondos1233@gmail.com` (Max subscription)
- **RTK hook:** `C:\Users\Administrator\.claude\hooks\rtk-rewrite.sh` ✅ (copied this session)
- **Agents:** `price-checker`, `email-agent`, `orchestrator` — task queue via `manage.ps1`
- **Gmail MCP:** `@gongrzhe/server-gmail-autoauth-mcp`, OAuth tokens at `C:\Users\Administrator\.gmail-mcp\credentials.json`
- **Plugins:** `claude-mem@thedotmack` (ICM/claude-mem), RTK

### TwinCAT 3.1
- **Version:** TC31-FULL-Setup.3.1.4024.12, installed at `C:\TwinCAT\3.1\`
- **Status:** Installed — **needs VPS reboot** to start runtime services

### Local Scripts
All scripts in this repo have been used and are complete. No pending work here.

---

## File Inventory

| File | Purpose | Status |
|------|---------|--------|
| `onboard.ps1` | Full VPS onboarding: OpenSSH, bore tunnel, SSH key auth, startup tasks | Complete |
| `download-twincat.ps1` | Downloads TwinCAT 3.1 RAR from MediaFire mirror | Complete |
| `install-twincat.ps1` | Extracts RAR with 7-Zip (pw: `plc247.com`), lists contents | Complete |
| `run-twincat-setup.ps1` | Runs TC31-FULL-Setup.3.1.4024.12.exe silently | Complete |
| `CLAUDE.md` | RTK instructions for all Claude sessions | Active |

---

## VPS Agent Management

```bash
# Send task to an agent
ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 send <agent> <prompt>"

# Check result
ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 result <agent>"

# List all agents
ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 list"
```

---

## Known Issues / Current Breakage

- **TwinCAT runtime not started:** VPS needs a reboot for `TCATSysSrv.exe` to run. Low priority — only needed if doing PLC/TwinCAT work.
- **Bore port may change on reboot:** If bore tunnel dies and restarts on a different port, update `~/.ssh/config` Port entry. Check via Databasemart console or RDP.

---

## Key Credentials (DO NOT COMMIT RAW SECRETS)

See `C:\Users\Kondos\.claude\projects\D--win-rev-claude\memory\agent-factory-v2.md` for OAuth details.
VPS RDP fallback: `108.181.188.174:1097` — see CLAUDE.md.
