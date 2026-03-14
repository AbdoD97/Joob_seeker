# Full VPS Onboarding Script - dawdaw-clwd
# Run as Administrator on the VPS (via RDP PowerShell)
# Idempotent - safe to run multiple times

$ErrorActionPreference = 'Continue'
$FIXED_PORT = '38472'
$PUB_KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINQYxc+IVor4VUy61VDsBX1GhIlc/Xsm0zkylnowFbCJ Kondos@LAPTOP-G1EM0JTS'

Write-Output '============================================'
Write-Output '  VPS Onboarding - dawdaw-clwd'
Write-Output '============================================'
Write-Output ''

# -- Phase 1: OpenSSH Server --
Write-Output '=== Phase 1: OpenSSH Server ==='
$sshd = Get-Service sshd -ErrorAction SilentlyContinue
if (-not $sshd) {
    Write-Output '  Installing OpenSSH Server...'
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
}
Start-Service sshd -ErrorAction SilentlyContinue
Set-Service -Name sshd -StartupType Automatic
$sshdStatus = (Get-Service sshd).Status
Write-Output "  sshd: $sshdStatus"

# -- Phase 2: Install bore + Start Tunnel --
Write-Output ''
Write-Output '=== Phase 2: bore Tunnel ==='
if (-not (Test-Path 'C:\bore\bore.exe')) {
    Write-Output '  Downloading bore...'
    $rel = Invoke-RestMethod 'https://api.github.com/repos/ekzhang/bore/releases/latest'
    $url = ($rel.assets | Where-Object { $_.name -like '*x86_64*windows*msvc*' }).browser_download_url
    Invoke-WebRequest -Uri $url -OutFile 'C:\bore.zip'
    New-Item -ItemType Directory -Path 'C:\bore' -Force | Out-Null
    Expand-Archive 'C:\bore.zip' -DestinationPath 'C:\bore' -Force
    Remove-Item 'C:\bore.zip' -Force -ErrorAction SilentlyContinue
    Write-Output '  bore installed to C:\bore\'
} else {
    Write-Output '  bore.exe already exists'
}

# Kill existing bore if running, then start fresh
Stop-Process -Name bore -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Start-Process -FilePath 'C:\bore\bore.exe' -ArgumentList "local 22 --to bore.pub --port $FIXED_PORT" -RedirectStandardOutput 'C:\bore\bore.log' -NoNewWindow
Start-Sleep -Seconds 4
$boreProc = Get-Process bore -ErrorAction SilentlyContinue
if ($boreProc) {
    Write-Output "  bore started on port $FIXED_PORT"
    Get-Content 'C:\bore\bore.log' -Tail 3
} else {
    Write-Output '  WARNING: bore failed to start - check C:\bore\bore.log'
}

# -- Phase 3: Deploy SSH Public Key --
Write-Output ''
Write-Output '=== Phase 3: SSH Public Key ==='
New-Item -ItemType Directory -Path 'C:\ProgramData\ssh' -Force | Out-Null
$authKeysPath = 'C:\ProgramData\ssh\administrators_authorized_keys'
$existing = Get-Content $authKeysPath -ErrorAction SilentlyContinue
if ($existing -and $existing -contains $PUB_KEY) {
    Write-Output '  Key already deployed'
} else {
    Set-Content $authKeysPath $PUB_KEY -Force
    Write-Output "  Key written to $authKeysPath"
}
icacls $authKeysPath /inheritance:r /grant 'SYSTEM:(F)' /grant 'BUILTIN\Administrators:(F)' | Out-Null
Write-Output '  Permissions set (SYSTEM + Admins only)'

# -- Phase 4: bore Startup Scheduled Task --
Write-Output ''
Write-Output '=== Phase 4: bore Startup Task ==='
$taskArg = '-NoProfile -WindowStyle Hidden -Command "& C:\bore\bore.exe local 22 --to bore.pub --port ' + $FIXED_PORT + ' 2>&1 | Out-File C:\bore\bore.log -Force"'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $taskArg
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName 'bore-ssh-tunnel' -Action $action -Trigger $trigger -RunLevel Highest -Force | Out-Null
Write-Output '  bore-ssh-tunnel task registered'

# -- Phase 8: bore Watchdog (crash recovery) --
Write-Output ''
Write-Output '=== Phase 8: bore Watchdog ==='
$watchdog = @'
$borePath = "C:\bore\bore.exe"
$boreArgs = "local 22 --to bore.pub --port 38472"
$logPath = "C:\bore\bore.log"
$running = Get-Process -Name bore -ErrorAction SilentlyContinue
if (-not $running) {
    Start-Process -FilePath $borePath -ArgumentList $boreArgs -RedirectStandardOutput $logPath -NoNewWindow
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content "C:\bore\watchdog.log" "$ts - bore restarted"
}
'@
Set-Content 'C:\bore\watchdog.ps1' $watchdog -Force
Write-Output '  watchdog.ps1 written'

$wdAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\bore\watchdog.ps1'
$wdTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 9999)
Register-ScheduledTask -TaskName 'bore-watchdog' -Action $wdAction -Trigger $wdTrigger -RunLevel Highest -Force | Out-Null
Write-Output '  bore-watchdog task registered (every 2 min)'

# -- Phase 10: VPS Directories --
Write-Output ''
Write-Output '=== Phase 10: VPS Directories ==='
New-Item -ItemType Directory -Path 'C:\temp' -Force | Out-Null
New-Item -ItemType Directory -Path 'C:\tools' -Force | Out-Null
New-Item -ItemType Directory -Path 'C:\work' -Force | Out-Null
Write-Output '  Created: C:\temp, C:\tools, C:\work'

# -- Verification --
Write-Output ''
Write-Output '============================================'
Write-Output '  VERIFICATION'
Write-Output '============================================'

$hn = hostname
$un = whoami
$sshdSt = (Get-Service sshd).Status
$boreTunnel = (Get-ScheduledTask 'bore-ssh-tunnel').State
$boreWd = (Get-ScheduledTask 'bore-watchdog').State
$boreRunning = if (Get-Process bore -ErrorAction SilentlyContinue) { 'Running' } else { 'NOT running' }
$hasTemp = Test-Path 'C:\temp'
$hasTools = Test-Path 'C:\tools'
$hasWork = Test-Path 'C:\work'
$hasKeys = Test-Path 'C:\ProgramData\ssh\administrators_authorized_keys'

Write-Output "Hostname:        $hn"
Write-Output "User:            $un"
Write-Output "sshd:            $sshdSt"
Write-Output "bore-ssh-tunnel: $boreTunnel"
Write-Output "bore-watchdog:   $boreWd"
Write-Output "bore process:    $boreRunning"
Write-Output "C:\temp:         $hasTemp"
Write-Output "C:\tools:        $hasTools"
Write-Output "C:\work:         $hasWork"
Write-Output "Auth keys:       $hasKeys"
Write-Output ''
Write-Output '============================================'
Write-Output "  DONE - bore on port $FIXED_PORT"
Write-Output '============================================'
