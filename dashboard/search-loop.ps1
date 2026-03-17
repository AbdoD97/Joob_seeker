$tracker = "C:\agents\omda\data\jobs\tracker.json"
$maxPerRound = 100
$maxTotal = 500
$maxLoopMinutes = 30
$agentDir = "C:\agents\omda"
$logFile = "C:\agents\omda\data\jobs\search-log.txt"
$dataDir = "C:\agents\omda\data\jobs"

function AmsTime { [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date), 'W. Europe Standard Time').ToString('yyyy-MM-dd HH:mm:ss') }

$loopStart = Get-Date
$startData = Get-Content $tracker -Raw | ConvertFrom-Json
$startCount = $startData.jobs.Count
$nextId = ($startData.jobs | ForEach-Object { $_.id } | Measure-Object -Maximum).Maximum
if (-not $nextId) { $nextId = 0 }

"[$(AmsTime)] Search loop starting (tracker has $startCount jobs, PARALLEL x6, cap $maxPerRound/round $maxTotal/total, max ${maxLoopMinutes}min)" | Out-File $logFile -Encoding UTF8

if ($startCount -ge $maxTotal) {
    "[$(AmsTime)] Total cap reached: $startCount/$maxTotal jobs. Stopping." | Out-File $logFile -Append -Encoding UTF8
    exit
}

$remaining = [Math]::Min($maxPerRound, $maxTotal - $startCount)

# 6 parallel workers: platform + role specialization
$prompts = @(
    @{
        name = "indeed-sc"
        file = "$dataDir\tracker-indeed-sc.json"
        prompt = "Find up to 15 supply chain jobs on Indeed NL. Search nl.indeed.com/jobs with queries: title:(supply chain) (coordinator OR assistant OR analyst OR planner) -manager -director -senior, and title:(logistics) (coordinator OR analyst) -manager -director. Use fromage=10 for last 10 days. Write results to C:\agents\omda\data\jobs\tracker-indeed-sc.json as {jobs:[...]}. Each job: id(start 1), title, company, location, salary, fit_score, url, status='active', date_found, date_posted, deadline, language, years_required, key_match, interview_speed, applicant_count. Follow CLAUDE.md criteria. Be fast, save and move on."
    },
    @{
        name = "indeed-ops-ba"
        file = "$dataDir\tracker-indeed-ops-ba.json"
        prompt = "Find up to 15 operations/business analyst jobs on Indeed NL. Search nl.indeed.com/jobs with queries: title:(operations) (analyst OR coordinator OR specialist) -manager -director, title:(business analyst) -senior -manager, and title:(process) (analyst OR improvement) -manager. Use fromage=10. Write results to C:\agents\omda\data\jobs\tracker-indeed-ops-ba.json as {jobs:[...]}. Each job: id(start 1), title, company, location, salary, fit_score, url, status='active', date_found, date_posted, deadline, language, years_required, key_match, interview_speed, applicant_count. Follow CLAUDE.md criteria. Be fast."
    },
    @{
        name = "recruiters"
        file = "$dataDir\tracker-recruiters.json"
        prompt = "Find up to 15 jobs from recruiter boards: Blue Lynx (bluelynx.com/jobs), Hays NL (hays.nl/en/jobs/supply-chain-jobs), Michael Page NL (michaelpage.nl/en/jobs), Randstad NL English (randstad.nl/english). Search for supply chain, operations, business analyst roles. Write results to C:\agents\omda\data\jobs\tracker-recruiters.json as {jobs:[...]}. Each job: id(start 1), title, company, location, salary, fit_score, url, status='active', date_found, date_posted, deadline, language, years_required, key_match, interview_speed, applicant_count. Follow CLAUDE.md criteria. Be fast."
    },
    @{
        name = "expat-platforms"
        file = "$dataDir\tracker-expat.json"
        prompt = "Find up to 15 jobs from expat platforms: IamExpat (iamexpat.nl/career/jobs-netherlands with ?language=english), Together Abroad (togetherabroad.nl/all-jobs/language/english), eXpatJobs (netherlands.expatjobs.eu). Search supply chain, operations, business analyst categories. Write results to C:\agents\omda\data\jobs\tracker-expat.json as {jobs:[...]}. Each job: id(start 1), title, company, location, salary, fit_score, url, status='active', date_found, date_posted, deadline, language, years_required, key_match, interview_speed, applicant_count. Follow CLAUDE.md criteria. Be fast."
    },
    @{
        name = "niche-sites"
        file = "$dataDir\tracker-niche.json"
        prompt = "Find up to 15 jobs from niche platforms: Undutchables (undutchables.nl/vacancies - scan all ~4 pages), Faruse (faruse.com/english-speaking/jobs/netherlands), Magnet.me (magnet.me/en/jobs/netherlands), EnglishJobSearch.nl, Robert Half (roberthalf.com/nl/en/find-jobs). Search supply chain, operations, analyst roles. Write results to C:\agents\omda\data\jobs\tracker-niche.json as {jobs:[...]}. Each job: id(start 1), title, company, location, salary, fit_score, url, status='active', date_found, date_posted, deadline, language, years_required, key_match, interview_speed, applicant_count. Follow CLAUDE.md criteria. Be fast."
    },
    @{
        name = "web-surfing"
        file = "$dataDir\tracker-web.json"
        prompt = "Find up to 15 jobs by free web surfing and Google searches. Use queries like: 'supply chain coordinator Netherlands hiring 2026', 'operations analyst Netherlands vacancy', 'business analyst Netherlands English'. Also search: Glassdoor (glassdoor.com Netherlands supply chain), StepStone (stepstone.nl), company career pages (unilever, dsm, philips, Shell, ASML). Write results to C:\agents\omda\data\jobs\tracker-web.json as {jobs:[...]}. Each job: id(start 1), title, company, location, salary, fit_score, url, status='active', date_found, date_posted, deadline, language, years_required, key_match, interview_speed, applicant_count. Follow CLAUDE.md criteria. Be fast."
    }
)

# Initialize temp tracker files
foreach ($p in $prompts) {
    [System.IO.File]::WriteAllText($p.file, '{"jobs": []}', (New-Object System.Text.UTF8Encoding $false))
}

"[$(AmsTime)] Launching 6 parallel workers: $($prompts | ForEach-Object { $_.name } | Join-String -Separator ', ')" | Out-File $logFile -Append -Encoding UTF8

# Launch all 6 in parallel
$jobs = @()
foreach ($p in $prompts) {
    $jobs += Start-Job -ScriptBlock {
        param($dir, $prompt)
        Set-Location $dir
        & claude -p $prompt --model sonnet --effort max --dangerously-skip-permissions 2>&1
    } -ArgumentList $agentDir, $p.prompt
    "[$(AmsTime)] Started worker: $($p.name)" | Out-File $logFile -Append -Encoding UTF8
}

# Wait for all with timeout (leave 2min for merge)
$timeoutSeconds = ($maxLoopMinutes - 2) * 60
$allDone = Wait-Job $jobs -Timeout $timeoutSeconds

# Kill any that didn't finish
$timedOut = 0
foreach ($j in $jobs) {
    if ($j.State -eq 'Running') {
        Stop-Job $j
        $timedOut++
    }
    Remove-Job $j -Force -ErrorAction SilentlyContinue
}
if ($timedOut -gt 0) {
    "[$(AmsTime)] $timedOut worker(s) timed out and were killed" | Out-File $logFile -Append -Encoding UTF8
}

"[$(AmsTime)] All workers done. Merging results..." | Out-File $logFile -Append -Encoding UTF8

# Merge all temp tracker files into main tracker
$mainData = Get-Content $tracker -Raw | ConvertFrom-Json
$existingUrls = @{}
foreach ($j in $mainData.jobs) { $existingUrls[$j.url] = $true }

$totalAdded = 0
foreach ($p in $prompts) {
    try {
        $raw = Get-Content $p.file -Raw -ErrorAction SilentlyContinue
        if (-not $raw -or $raw.Trim() -eq '{"jobs": []}') {
            "[$(AmsTime)] Merged $($p.name): +0 jobs (empty)" | Out-File $logFile -Append -Encoding UTF8
            continue
        }
        $tempData = $raw | ConvertFrom-Json
        $tempJobs = $tempData.jobs
        if (-not $tempJobs) { $tempJobs = @() }
        $addedFromGroup = 0
        foreach ($j in $tempJobs) {
            if (-not $j.url -or $existingUrls.ContainsKey($j.url)) { continue }
            if ($mainData.jobs.Count -ge ($startCount + $remaining)) { break }
            $nextId++
            $j.id = $nextId
            $mainData.jobs += $j
            $existingUrls[$j.url] = $true
            $addedFromGroup++
            $totalAdded++
        }
        "[$(AmsTime)] Merged $($p.name): +$addedFromGroup jobs (from $($tempJobs.Count) found)" | Out-File $logFile -Append -Encoding UTF8
    } catch {
        "[$(AmsTime)] Error merging $($p.name): $_" | Out-File $logFile -Append -Encoding UTF8
    }
}

# Update round and save
$mainData.round = ($mainData.round + 1)
$mainData.last_updated = (Get-Date -Format 'yyyy-MM-dd')
$json = $mainData | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($tracker, $json, (New-Object System.Text.UTF8Encoding $false))

$finalCount = $mainData.jobs.Count
$totalElapsed = ((Get-Date) - $loopStart).TotalMinutes.ToString('F1')
"[$(AmsTime)] Search loop complete: $finalCount total jobs (+$totalAdded new) in ${totalElapsed}min" | Out-File $logFile -Append -Encoding UTF8

# Cleanup temp files
foreach ($p in $prompts) {
    Remove-Item $p.file -Force -ErrorAction SilentlyContinue
}

# Telegram notification
Push-Location $agentDir
& claude -p "Send Telegram notification: Job search complete. Found $finalCount jobs (+$totalAdded new) in ${totalElapsed}min. Check dashboard." --model sonnet --effort max --dangerously-skip-permissions 2>&1 | Out-Null
Pop-Location
