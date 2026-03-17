$tracker = "C:\agents\omda\data\jobs\tracker.json"
$maxPerRound = 30
$maxTotal = 100
$maxIterations = 12
$maxLoopMinutes = 30
$agentDir = "C:\agents\omda"
$logFile = "C:\agents\omda\data\jobs\search-log.txt"

$loopStart = Get-Date
$startData = Get-Content $tracker -Raw | ConvertFrom-Json
$startCount = $startData.jobs.Count

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Search loop starting (tracker has $startCount jobs, finding up to $maxPerRound more, max ${maxLoopMinutes}min)" | Out-File $logFile -Encoding UTF8

if ($startCount -ge $maxTotal) {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Total cap reached: $startCount/$maxTotal jobs. Stopping." | Out-File $logFile -Append -Encoding UTF8
    exit
}

for ($i = 1; $i -le $maxIterations; $i++) {
    # 30-minute hard timeout for entire loop
    $elapsed = (Get-Date) - $loopStart
    if ($elapsed.TotalMinutes -ge $maxLoopMinutes) {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 30-min timeout reached after $($elapsed.TotalMinutes.ToString('F1'))min. Stopping." | Out-File $logFile -Append -Encoding UTF8
        break
    }

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
    $remaining = [Math]::Min(3, [Math]::Min($maxPerRound - $addedThisRound, $maxTotal - $count))

    $prompt = "Search iteration $i. tracker.json has $count jobs. Find $remaining MORE new jobs. " +
              "Use the Job Search Platform Guide in your CLAUDE.md for URL patterns. " +
              "Search Indeed NL (nl.indeed.com/jobs?q=...) and IamExpat (iamexpat.nl/career/jobs-netherlands/...). " +
              "Read tracker.json first, append new jobs, save immediately. Do NOT overwrite existing jobs. " +
              "Log skipped jobs to skipped.json. Be fast -- find jobs, save them, move on."

    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Iteration $i starting ($count jobs so far, finding $remaining more)" | Out-File $logFile -Append -Encoding UTF8

    # Per-iteration timeout: remaining loop time minus 1min buffer for cleanup
    $remainingMinutes = $maxLoopMinutes - $elapsed.TotalMinutes - 1
    if ($remainingMinutes -lt 2) {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Not enough time for iteration $i (<2min left). Stopping." | Out-File $logFile -Append -Encoding UTF8
        break
    }
    $iterTimeout = [Math]::Floor($remainingMinutes) * 60

    Push-Location $agentDir
    try {
        $job = Start-Job -ScriptBlock {
            param($dir, $p)
            Set-Location $dir
            & claude -p $p --dangerously-skip-permissions 2>&1
        } -ArgumentList $agentDir, $prompt

        $completed = Wait-Job $job -Timeout $iterTimeout
        if ($completed) {
            Receive-Job $job | Out-Null
        } else {
            Stop-Job $job
            "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Iteration $i timed out after ${iterTimeout}s. Killing." | Out-File $logFile -Append -Encoding UTF8
        }
        Remove-Job $job -Force -ErrorAction SilentlyContinue
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
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] No new jobs found in iteration $i. Possible LinkedIn soft ban or no matches. Stopping." | Out-File $logFile -Append -Encoding UTF8
        break
    }
}

$finalData = Get-Content $tracker -Raw | ConvertFrom-Json
$finalCount = $finalData.jobs.Count
$totalElapsed = ((Get-Date) - $loopStart).TotalMinutes.ToString('F1')
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Search loop complete: $finalCount total jobs (+$($finalCount - $startCount) new) in ${totalElapsed}min" | Out-File $logFile -Append -Encoding UTF8

Push-Location $agentDir
& claude -p "Send Telegram notification: Job search complete. Found $finalCount jobs (+$($finalCount - $startCount) new) in ${totalElapsed}min. Check dashboard." --dangerously-skip-permissions 2>&1 | Out-Null
Pop-Location
