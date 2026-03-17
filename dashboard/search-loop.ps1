$tracker = "C:\agents\omda\data\jobs\tracker.json"
$maxPerRound = 30
$maxTotal = 100
$maxLoopMinutes = 30
$agentDir = "C:\agents\omda"
$logFile = "C:\agents\omda\data\jobs\search-log.txt"
$dataDir = "C:\agents\omda\data\jobs"

$loopStart = Get-Date
$startData = Get-Content $tracker -Raw | ConvertFrom-Json
$startCount = $startData.jobs.Count
$nextId = ($startData.jobs | ForEach-Object { $_.id } | Measure-Object -Maximum).Maximum
if (-not $nextId) { $nextId = 0 }

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Search loop starting (tracker has $startCount jobs, PARALLEL mode, max ${maxLoopMinutes}min)" | Out-File $logFile -Encoding UTF8

if ($startCount -ge $maxTotal) {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Total cap reached: $startCount/$maxTotal jobs. Stopping." | Out-File $logFile -Append -Encoding UTF8
    exit
}

$remaining = [Math]::Min($maxPerRound, $maxTotal - $startCount)

# Define 3 parallel search groups
$prompts = @(
    @{
        name = "general"
        file = "$dataDir\tracker-general.json"
        prompt = "Search iteration - GENERAL BOARDS. Find up to 5 jobs from Indeed NL (nl.indeed.com) and IamExpat (iamexpat.nl). Use the Job Search Platform Guide in your CLAUDE.md. Write results to C:\agents\omda\data\jobs\tracker-general.json as {jobs: [...]}. Each job needs: id (start from 1), title, company, location, salary, fit_score, url, status='active', date_found, date_posted, deadline, language, years_required, key_match, interview_speed, applicant_count. Follow all criteria in CLAUDE.md. Be fast."
    },
    @{
        name = "recruiters"
        file = "$dataDir\tracker-recruiters.json"
        prompt = "Search iteration - RECRUITER BOARDS. Find up to 5 jobs from Blue Lynx (bluelynx.com/jobs), Hays NL (hays.nl/en/jobs), Michael Page NL (michaelpage.nl/en/jobs), and Undutchables (undutchables.nl/vacancies). Write results to C:\agents\omda\data\jobs\tracker-recruiters.json as {jobs: [...]}. Each job needs: id (start from 1), title, company, location, salary, fit_score, url, status='active', date_found, date_posted, deadline, language, years_required, key_match, interview_speed, applicant_count. Follow all criteria in CLAUDE.md. Be fast."
    },
    @{
        name = "expat"
        file = "$dataDir\tracker-expat.json"
        prompt = "Search iteration - EXPAT + NICHE BOARDS. Find up to 5 jobs from Together Abroad (togetherabroad.nl), eXpatJobs (netherlands.expatjobs.eu), Faruse (faruse.com/english-speaking/jobs/netherlands), Magnet.me (magnet.me/en/jobs/netherlands), and free Google web searches. Write results to C:\agents\omda\data\jobs\tracker-expat.json as {jobs: [...]}. Each job needs: id (start from 1), title, company, location, salary, fit_score, url, status='active', date_found, date_posted, deadline, language, years_required, key_match, interview_speed, applicant_count. Follow all criteria in CLAUDE.md. Be fast."
    }
)

# Initialize temp tracker files
foreach ($p in $prompts) {
    [System.IO.File]::WriteAllText($p.file, '{"jobs": []}', (New-Object System.Text.UTF8Encoding $false))
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Launching 3 parallel searches: general, recruiters, expat" | Out-File $logFile -Append -Encoding UTF8

# Launch all 3 in parallel
$jobs = @()
foreach ($p in $prompts) {
    $jobs += Start-Job -ScriptBlock {
        param($dir, $prompt)
        Set-Location $dir
        & claude -p $prompt --model sonnet --effort max --dangerously-skip-permissions 2>&1
    } -ArgumentList $agentDir, $p.prompt
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Started worker: $($p.name)" | Out-File $logFile -Append -Encoding UTF8
}

# Wait for all with timeout (leave 2min for merge)
$timeoutSeconds = ($maxLoopMinutes - 2) * 60
$allDone = Wait-Job $jobs -Timeout $timeoutSeconds

# Kill any that didn't finish
foreach ($j in $jobs) {
    if ($j.State -eq 'Running') {
        Stop-Job $j
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Worker timed out, killed" | Out-File $logFile -Append -Encoding UTF8
    }
    Remove-Job $j -Force -ErrorAction SilentlyContinue
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] All workers done. Merging results..." | Out-File $logFile -Append -Encoding UTF8

# Merge all temp tracker files into main tracker
$mainData = Get-Content $tracker -Raw | ConvertFrom-Json
$existingUrls = @{}
foreach ($j in $mainData.jobs) { $existingUrls[$j.url] = $true }

$totalAdded = 0
foreach ($p in $prompts) {
    try {
        $tempData = Get-Content $p.file -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
        $tempJobs = $tempData.jobs
        if (-not $tempJobs) { $tempJobs = @() }
        $addedFromGroup = 0
        foreach ($j in $tempJobs) {
            if ($existingUrls.ContainsKey($j.url)) { continue }
            if (($mainData.jobs.Count + 1) -gt ($startCount + $remaining)) { break }
            $nextId++
            $j.id = $nextId
            $mainData.jobs += $j
            $existingUrls[$j.url] = $true
            $addedFromGroup++
            $totalAdded++
        }
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Merged $($p.name): +$addedFromGroup jobs (from $($tempJobs.Count) found)" | Out-File $logFile -Append -Encoding UTF8
    } catch {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Error merging $($p.name): $_" | Out-File $logFile -Append -Encoding UTF8
    }
}

# Update round and save
$mainData.round = ($mainData.round + 1)
$mainData.last_updated = (Get-Date -Format 'yyyy-MM-dd')
$json = $mainData | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($tracker, $json, (New-Object System.Text.UTF8Encoding $false))

$finalCount = $mainData.jobs.Count
$totalElapsed = ((Get-Date) - $loopStart).TotalMinutes.ToString('F1')
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Search loop complete: $finalCount total jobs (+$totalAdded new) in ${totalElapsed}min" | Out-File $logFile -Append -Encoding UTF8

# Cleanup temp files
foreach ($p in $prompts) {
    Remove-Item $p.file -Force -ErrorAction SilentlyContinue
}

# Telegram notification
Push-Location $agentDir
& claude -p "Send Telegram notification: Job search complete. Found $finalCount jobs (+$totalAdded new) in ${totalElapsed}min. Check dashboard." --model sonnet --effort max --dangerously-skip-permissions 2>&1 | Out-Null
Pop-Location
