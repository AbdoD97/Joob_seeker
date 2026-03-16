# Deploy Job Dashboard from GitHub to VPS
# Usage: scp this to VPS then run, OR run via SSH
# Pulls latest from GitHub and restarts the dashboard service

$repoUrl = "https://github.com/AbdoD97/Joob_seeker.git"
$dashboardDir = "C:\dashboard"
$agentDir = "C:\agents\omda"
$tempClone = "C:\temp\joob-deploy-" + (Get-Date -Format "yyyyMMdd_HHmmss")

Write-Host "=== Deploying Job Dashboard ==="

# Clone latest
Write-Host "Pulling latest from GitHub..."
git clone --depth 1 $repoUrl $tempClone 2>&1 | Out-Null

if (-not (Test-Path "$tempClone\dashboard\server.js")) {
    Write-Host "ERROR: Clone failed or missing files"
    Remove-Item $tempClone -Recurse -Force -ErrorAction SilentlyContinue
    exit 1
}

# Copy dashboard files
Write-Host "Updating dashboard files..."
Copy-Item "$tempClone\dashboard\server.js" "$dashboardDir\server.js" -Force
Copy-Item "$tempClone\dashboard\templates\index.html" "$dashboardDir\index.html" -Force

# Copy search loop runner
if (Test-Path "$tempClone\dashboard\search-loop.ps1") {
    Copy-Item "$tempClone\dashboard\search-loop.ps1" "$agentDir\search-loop.ps1" -Force
    Write-Host "Updated search-loop.ps1"
}

# Cleanup
Remove-Item $tempClone -Recurse -Force -ErrorAction SilentlyContinue

# Restart dashboard
Write-Host "Restarting JobDashboard..."
Stop-ScheduledTask -TaskName "JobDashboard" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName "JobDashboard"
Start-Sleep -Seconds 3

$listening = netstat -ano | findstr "9563" | findstr "LISTENING"
if ($listening) {
    Write-Host "=== Deploy complete - Dashboard running on port 9563 ==="
} else {
    Write-Host "=== WARNING: Dashboard may not have started ==="
}
