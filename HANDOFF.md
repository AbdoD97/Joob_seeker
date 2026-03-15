# Handoff — win_rev_claude

## Project Purpose

Local PowerShell scripts for onboarding and provisioning the `dawdaw-clwd` Windows Server 2022 VPS. Handles: SSH setup, bore tunnel, TwinCAT 3.1 installation, and initial VPS structure.

The AI agent factory (Claude Code agents, manage.ps1, etc.) lives **on the VPS** at `C:\agents\`, not in this repo.

---

## Current State (2026-03-15)

### VPS: dawdaw-clwd — FULLY OPERATIONAL
- **SSH access:** `ssh vps` → bore tunnel on port 38473 (auto-recovers via watchdog)
- **Claude Code:** v2.1.75, authenticated as `kondos1233@gmail.com` (Max subscription)
- **RTK hook:** `C:\Users\Administrator\.claude\hooks\rtk-rewrite.sh` ✅
- **Agents:** `price-checker`, `email-agent`, `orchestrator`, `job-seeker`, `omda` — task queue via `manage.ps1`
- **Gmail MCP:** `@gongrzhe/server-gmail-autoauth-mcp`, OAuth tokens at `C:\Users\Administrator\.gmail-mcp\credentials.json`
- **Plugins:** `claude-mem@thedotmack` (ICM/claude-mem), RTK

### Agent: omda (Job Search)
- **Purpose:** Automated job search for Mohammad Emad (operations/SC/L&D roles in Netherlands)
- **Status:** 4 rounds of searching completed, **29 active verified jobs** tracked
- **Top match:** Tesla EMEA Training Ops (84/100 fit score)
- **Data:** `C:\agents\omda\data\jobs\` (individual JSON files per job + tracker.json)
- **Memory:** `C:\agents\omda\memory.md` (full candidate profile, search logs, verification history)
- **Urgent deadlines:** LITEON Mar 18, GXO Mar 21, Unilever Mar 21

### LinkedIn Agent (Local)
- **File:** `agents/linkedin-agent/linkedin_job_search.py` — LinkedIn job search script
- **Template:** `agents/_template-agent/` — reusable agent template with `.env.example`, `agent_template.py`, `requirements.txt`

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
| `agents/_template-agent/` | Reusable agent template (Python) | Complete |
| `agents/linkedin-agent/` | LinkedIn job search script | Active |
| `tmp/` | Temp scripts for SCP to VPS (gitignored) | Ephemeral |
| `CLAUDE.md` | RTK instructions for all Claude sessions | Active |

---

## VPS Agent Management

```bash
# List all agents
ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 list"

# Send task to an agent
ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 send <agent> <prompt>"

# Check result
ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 result <agent> [task_id]"

# Check status
ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 status <agent>"
```

---

## Known Issues / Current Breakage

- **TwinCAT runtime not started:** VPS needs a reboot for `TCATSysSrv.exe` to run. Low priority.
- **Bore port may change on reboot:** If bore tunnel restarts on a different port, update `~/.ssh/config`.
- **Sealed Air & Flowserve job links** point to career portals, not direct postings — may need manual navigation.

---

## Key Credentials (DO NOT COMMIT RAW SECRETS)

See `C:\Users\Kondos\.claude\projects\D--win-rev-claude\memory\agent-factory-v2.md` for OAuth details.
VPS RDP fallback: `108.181.188.174:1097` — see CLAUDE.md.
