# Repo Map — win_rev_claude

## Purpose

Local scripts for provisioning and onboarding the `dawdaw-clwd` VPS.
The live agent system runs **on the VPS** at `C:\agents\`.

## Directory Structure

```
D:\win_rev_claude\
├── CLAUDE.md               # RTK instructions (auto-loaded by Claude Code)
├── HANDOFF.md              # Current state + handoff notes
├── REPO_MAP.md             # This file
├── agent_logs/
│   ├── INDEX.md            # One-line log index
│   └── current.md          # Current session log
├── agents/
│   ├── _template-agent/    # Reusable Python agent template
│   └── linkedin-agent/     # LinkedIn job search script
├── tmp/                    # Temp scripts for SCP to VPS (gitignored)
├── onboard.ps1             # VPS onboarding (OpenSSH, bore, SSH key)
├── download-twincat.ps1    # Download TwinCAT 3.1 from MediaFire
├── install-twincat.ps1     # Extract RAR + list contents
└── run-twincat-setup.ps1   # Silent install TwinCAT 3.1
```

## Hot Paths

- **VPS management:** `ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 ..."`
- **Agent workspaces on VPS:** `C:\agents\<name>\` (CLAUDE.md + memory.md + data\tasks\)
- **Claude settings on VPS:** `C:\Users\Administrator\.claude\settings.json`
- **Local memory:** `C:\Users\Kondos\.claude\projects\D--win-rev-claude\memory\`

## Canonical Commands

```bash
ssh vps                     # Connect to VPS
ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 list"
ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 send email-agent <task>"
ssh vps "powershell -ExecutionPolicy Bypass -File C:\agents\manage.ps1 result email-agent"
```
