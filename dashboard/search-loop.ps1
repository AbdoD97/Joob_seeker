$tracker = "C:\agents\omda\data\jobs\tracker.json"
$maxPerRound = 30
$maxTotal = 100
$maxIterations = 8
$agentDir = "C:\agents\omda"
$logFile = "C:\agents\omda\data\jobs\search-log.txt"

$startData = Get-Content $tracker -Raw | ConvertFrom-Json
$startCount = $startData.jobs.Count

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Search loop starting (tracker has $startCount jobs, finding up to $maxPerRound more)" | Out-File $logFile -Encoding UTF8

if ($startCount -ge $maxTotal) {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Total cap reached: $startCount/$maxTotal jobs. Stopping." | Out-File $logFile -Append -Encoding UTF8
    exit
}

for ($i = 1; $i -le $maxIterations; $i++) {
    $data = Get-Content $tracker -Raw | ConvertFrom-Json
    $count = $data.jobs.Count
    $addedThisRound = $count - $startCount
    if ($addedThisRound -ge $maxPerRound) {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Round cap reached: +$addedThisRound new jobs this round. Stopping." | Out-File $logFile -Append -Encoding UTF8
        break
    }
    if ($count -ge $maxTotal) {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Total cap reached: $count/$maxTotal jobs. Stopping." | Out-File $logFile -Append -Encoding UTF8
        break
    }
    $remaining = [Math]::Min(5, [Math]::Min($maxPerRound - $addedThisRound, $maxTotal - $count))

    $prompt = "You are in search iteration $i. tracker.json currently has $count jobs. " +
              "Search LinkedIn for $remaining MORE new jobs matching criteria in your CLAUDE.md. " +
              "Read tracker.json first, append new jobs (keep existing ones), save tracker.json. " +
              "Do NOT search for more than $remaining jobs. Do NOT overwrite existing jobs."

    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Iteration $i starting ($count jobs so far, finding $remaining more)" | Out-File $logFile -Append -Encoding UTF8

    Push-Location $agentDir
    try {
        & claude -p $prompt --dangerously-skip-permissions 2>&1 | Out-Null
    } catch {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Error in iteration $i : $_" | Out-File $logFile -Append -Encoding UTF8
    }
    Pop-Location

    $newData = Get-Content $tracker -Raw | ConvertFrom-Json
    $newCount = $newData.jobs.Count
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Iteration $i done: $newCount jobs (was $count, added $($newCount - $count))" | Out-File $logFile -Append -Encoding UTF8

    if (($newCount - $startCount) -ge $maxPerRound) { break }
    if ($newCount -ge $maxTotal) { break }
    if ($newCount -eq $count) {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] No new jobs found in iteration $i. Stopping." | Out-File $logFile -Append -Encoding UTF8
        break
    }
}

$finalData = Get-Content $tracker -Raw | ConvertFrom-Json
$finalCount = $finalData.jobs.Count
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Search loop complete: $finalCount total jobs" | Out-File $logFile -Append -Encoding UTF8

Push-Location $agentDir
& claude -p "Send Telegram notification: Job search complete. Found $finalCount jobs. Check dashboard." --dangerously-skip-permissions 2>&1 | Out-Null
Pop-Location
