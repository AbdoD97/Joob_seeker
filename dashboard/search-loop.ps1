$tracker = "C:\agents\omda\data\jobs\tracker.json"
$dataDir = "C:\agents\omda\data\jobs"
$agentDir = "C:\agents\omda"
$logFile = "C:\agents\omda\data\jobs\search-log.txt"
$maxLoopMinutes = 30
$dashboardDir = "C:\dashboard"

function AmsTime { [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date), 'W. Europe Standard Time').ToString('yyyy-MM-dd HH:mm:ss') }

$loopStart = Get-Date
$startData = Get-Content $tracker -Raw | ConvertFrom-Json
$startCount = $startData.jobs.Count

"[$(AmsTime)] Pipeline starting (tracker has $startCount jobs)" | Out-File $logFile -Encoding UTF8

# Stage 1: HARVEST (python-jobspy + free APIs)
"[$(AmsTime)] Stage 1: Harvesting jobs from all platforms..." | Out-File $logFile -Append -Encoding UTF8

$rawFile = "$dataDir\raw_jobs.json"
try {
    $harvestStart = Get-Date
    & python "$dashboardDir\harvest.py" --output $rawFile --hours 240 2>&1 | ForEach-Object {
        "[$(AmsTime)] [harvest] $_" | Out-File $logFile -Append -Encoding UTF8
    }
    $harvestTime = ((Get-Date) - $harvestStart).TotalSeconds.ToString('F1')
    $rawCount = 0
    if (Test-Path $rawFile) {
        $rawData = Get-Content $rawFile -Raw | ConvertFrom-Json
        $rawCount = $rawData.Count
    }
    "[$(AmsTime)] Stage 1 complete: $rawCount raw jobs harvested in ${harvestTime}s" | Out-File $logFile -Append -Encoding UTF8
} catch {
    "[$(AmsTime)] Stage 1 error: $_" | Out-File $logFile -Append -Encoding UTF8
}

# Check timeout
$elapsed = ((Get-Date) - $loopStart).TotalMinutes
if ($elapsed -ge ($maxLoopMinutes - 5)) {
    "[$(AmsTime)] Timeout approaching after harvest (${elapsed}min). Skipping filter+score." | Out-File $logFile -Append -Encoding UTF8
    exit
}

# Stage 2: FILTER (pure Python, no LLM)
"[$(AmsTime)] Stage 2: Filtering jobs..." | Out-File $logFile -Append -Encoding UTF8

$filteredFile = "$dataDir\filtered_jobs.json"
try {
    & python "$dashboardDir\filter.py" --input $rawFile --output $filteredFile 2>&1 | ForEach-Object {
        "[$(AmsTime)] [filter] $_" | Out-File $logFile -Append -Encoding UTF8
    }
    $filteredCount = 0
    if (Test-Path $filteredFile) {
        $filteredData = Get-Content $filteredFile -Raw | ConvertFrom-Json
        $filteredCount = $filteredData.Count
    }
    "[$(AmsTime)] Stage 2 complete: $filteredCount jobs passed filters" | Out-File $logFile -Append -Encoding UTF8
} catch {
    "[$(AmsTime)] Stage 2 error: $_" | Out-File $logFile -Append -Encoding UTF8
}

if ($filteredCount -eq 0) {
    "[$(AmsTime)] No jobs passed filters. Stopping." | Out-File $logFile -Append -Encoding UTF8
    exit
}

# Check timeout
$elapsed = ((Get-Date) - $loopStart).TotalMinutes
if ($elapsed -ge ($maxLoopMinutes - 3)) {
    "[$(AmsTime)] Timeout approaching after filter (${elapsed}min). Skipping score." | Out-File $logFile -Append -Encoding UTF8
    exit
}

# Stage 3: SCORE (Claude LLM)
"[$(AmsTime)] Stage 3: Scoring $filteredCount jobs with Claude..." | Out-File $logFile -Append -Encoding UTF8

try {
    & python "$dashboardDir\score.py" --input $filteredFile --tracker $tracker --batch-size 20 2>&1 | ForEach-Object {
        "[$(AmsTime)] [score] $_" | Out-File $logFile -Append -Encoding UTF8
    }
} catch {
    "[$(AmsTime)] Stage 3 error: $_" | Out-File $logFile -Append -Encoding UTF8
}

# Final summary
$finalData = Get-Content $tracker -Raw | ConvertFrom-Json
$finalCount = $finalData.jobs.Count
$totalAdded = $finalCount - $startCount
$totalElapsed = ((Get-Date) - $loopStart).TotalMinutes.ToString('F1')

"[$(AmsTime)] Pipeline complete: $finalCount total jobs (+$totalAdded new) in ${totalElapsed}min" | Out-File $logFile -Append -Encoding UTF8

# Cleanup temp files
Remove-Item $rawFile -Force -ErrorAction SilentlyContinue
Remove-Item $filteredFile -Force -ErrorAction SilentlyContinue

# Telegram notification
Push-Location $agentDir
& claude -p "Send Telegram notification: Job search complete. Found $finalCount jobs (+$totalAdded new) in ${totalElapsed}min. Check dashboard." --model sonnet --dangerously-skip-permissions 2>&1 | Out-Null
Pop-Location
