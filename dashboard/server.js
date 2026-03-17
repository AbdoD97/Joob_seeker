const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');
const { exec } = require('child_process');

const PORT = 9563;
const TRACKER = 'C:/agents/omda/data/jobs/tracker.json';
const REJECTIONS = 'C:/agents/omda/data/jobs/rejections.json';
const REJECTION_RULES_JSON = 'C:/agents/omda/data/jobs/rejection_rules.json';
const REJECTION_RULES_MD = 'C:/agents/omda/data/jobs/rejection_rules.md';
const SKIPPED = 'C:/agents/omda/data/jobs/skipped.json';
const HTML = path.join(__dirname, 'index.html');
const MANAGE = 'C:\\agents\\manage.ps1';
const STOP_SCRIPT = [
  'Get-ScheduledTask | Where-Object { $_.TaskName -like "agent-omda-*" } | ForEach-Object {',
  '    Stop-ScheduledTask -TaskName $_.TaskName -ErrorAction SilentlyContinue',
  '    Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false -ErrorAction SilentlyContinue',
  '}',
  'Get-ChildItem "C:\\agents\\omda\\data\\tasks\\*.meta.json" | ForEach-Object {',
  '    $m = Get-Content $_.FullName -Raw | ConvertFrom-Json',
  '    if ($m.status -eq "running" -or $m.status -eq "queued") {',
  '        $m.status = "cancelled"',
  '        [System.IO.File]::WriteAllText($_.FullName, ($m | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding $false))',
  '    }',
  '}',
  'Write-Host "stopped"'
].join('\n');

const SEARCH_TASK = 'omda-search';
const SEARCH_LOOP = 'C:\\agents\\omda\\search-loop.ps1';
const SEARCH_LOG = 'C:/agents/omda/data/jobs/search-log.txt';

function getAgentStatus(callback) {
  // Check if search-loop PID is still alive
  let pid = null;
  try { pid = fs.readFileSync('C:\\temp\\search-loop.pid', 'utf8').trim(); } catch {}
  let status = 'idle';
  if (pid) {
    try {
      process.kill(Number(pid), 0); // signal 0 = check if alive
      status = 'searching';
    } catch {
      // Process dead — clean up PID file
      try { fs.unlinkSync('C:\\temp\\search-loop.pid'); } catch {}
      status = 'idle';
    }
  }
  // Also check scheduled task as fallback
  if (status === 'idle') {
    exec('powershell -Command "Get-ScheduledTask -TaskName \'' + SEARCH_TASK + '\' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty State"',
      { timeout: 5000 },
      (err, stdout) => {
        const state = (stdout || '').trim();
        if (state === 'Running') status = 'searching';
        const info = parseSearchLog();
        callback({ status, ...info });
      }
    );
  } else {
    const info = parseSearchLog();
    callback({ status, ...info });
  }
}

function parseSearchLog() {
  let log = '', iteration = null, maxIterations = 6, phase = '';
  try {
    const lines = fs.readFileSync(SEARCH_LOG, 'utf8').trim().split('\n');
    log = lines[lines.length - 1] || '';
    // Scan lines for pipeline stage info
    maxIterations = 3; // 3 stages: harvest, filter, score
    for (const line of lines) {
      if (/Stage 1.*Harvest/i.test(line)) { iteration = 1; phase = 'harvesting'; }
      if (/Stage 1 complete/i.test(line)) { iteration = 1; phase = 'done'; }
      if (/Stage 2.*Filter/i.test(line)) { iteration = 2; phase = 'filtering'; }
      if (/Stage 2 complete/i.test(line)) { iteration = 2; phase = 'done'; }
      if (/Stage 3.*Scor/i.test(line)) { iteration = 3; phase = 'scoring'; }
      if (/Pipeline complete/i.test(line)) { iteration = 3; phase = 'finishing'; }
      // Fallback for old parallel format
      if (/Launching.*parallel/i.test(line)) { phase = 'searching'; iteration = 1; maxIterations = 1; }
      if (/Iteration (\d+)/i.test(line)) { iteration = parseInt(RegExp.$1); phase = 'searching'; }
    }
  } catch {}
  const pct = iteration ? Math.round((iteration / maxIterations) * 100) : 0;
  return { log, iteration, maxIterations, phase, progress: pct };
}

function readJSON(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch { return null; }
}
function writeJSON(file, data) {
  try { fs.writeFileSync(file, JSON.stringify(data, null, 2), { encoding: 'utf8' }); return true; }
  catch { return false; }
}
function send(res, status, obj) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(obj));
}

function analyzeRejections(rejections, callback) {
  const lines = rejections.map((r, i) => {
    const parts = [
      (i + 1) + '. ' + r.company + ' - ' + r.title,
      '   User reason: "' + r.reason + '"',
      '   Location: ' + (r.location || 'unknown'),
      '   Salary: ' + (r.salary && r.salary !== 'not listed' ? r.salary : 'not listed'),
      '   Experience required: ' + (r.years_required || 'not stated'),
      '   Language: ' + (r.language || 'unknown'),
      '   Interview type: ' + (r.interview_speed || 'unknown') + ' (fast=recruiter/agency, normal=direct company)',
      '   Fit score: ' + (r.fit_score != null ? r.fit_score + '%' : 'unknown'),
      '   Key match summary: ' + (r.key_match || 'none'),
    ];
    if (r.deadline && r.deadline !== 'unknown') parts.push('   Deadline: ' + r.deadline);
    return parts.join('\n');
  }).join('\n\n');

  const prompt = [
    'Analyze these rejected job postings and output search exclusion rules.',
    'Each entry includes the user\'s rejection reason AND the actual job characteristics.',
    'Look for patterns in the job data that correlate with rejections, not just the stated reason.',
    '',
    'Rejected jobs:',
    lines,
    '',
    'Respond in EXACTLY this format (no preamble, no other text):',
    '',
    'EXCLUSION RULES FOR NEXT SEARCH:',
    '- [concise rule derived from patterns in the rejections]',
    '- [another rule if applicable]',
    '',
    'KEYWORDS TO FLAG (comma-separated, short words matching rejected job titles/roles):',
    '[keyword1, keyword2, keyword3]'
  ].join('\n');

  const promptFile = 'C:\\temp\\analyze-prompt-' + Date.now() + '.txt';
  const psFile = 'C:\\temp\\run-analyze-' + Date.now() + '.ps1';

  try {
    fs.writeFileSync(promptFile, prompt, { encoding: 'utf8' });
    const psContent = '$p = Get-Content \'' + promptFile + '\' -Raw\n& claude --print $p\n';
    fs.writeFileSync(psFile, psContent, { encoding: 'utf8' });
  } catch (e) {
    return callback(e, null);
  }

  exec('powershell -ExecutionPolicy Bypass -File "' + psFile + '"',
    { timeout: 90000, maxBuffer: 1024 * 1024 },
    (err, stdout, stderr) => {
      try { fs.unlinkSync(promptFile); } catch {}
      try { fs.unlinkSync(psFile); } catch {}
      if (err) return callback(err, null);
      callback(null, stdout.trim());
    }
  );
}

// SSE: watch tracker.json and skipped.json for changes and push to connected clients
const sseClients = new Set();
let lastTrackerMtime = 0;
let lastSkippedMtime = 0;
let trackerWatcher = null;

function broadcastJobs() {
  let mtime;
  try { mtime = fs.statSync(TRACKER).mtimeMs; } catch { return; }
  if (mtime === lastTrackerMtime) return;
  lastTrackerMtime = mtime;
  const raw = (() => { try { return fs.readFileSync(TRACKER, 'utf8'); } catch { return ''; } })();
  if (!raw) return;
  const data = (() => { try { return JSON.parse(raw); } catch { return null; } })();
  if (!data) return;
  for (const j of (data.jobs || [])) {
    if (!('fit_score' in j) && 'fit' in j) j.fit_score = j.fit;
  }
  const msg = 'data: ' + JSON.stringify(data) + '\n\n';
  for (const client of sseClients) {
    try { client.write(msg); } catch { sseClients.delete(client); }
  }
}

function broadcastSkipped() {
  let mtime;
  try { mtime = fs.statSync(SKIPPED).mtimeMs; } catch { return; }
  if (mtime === lastSkippedMtime) return;
  lastSkippedMtime = mtime;
  const data = readJSON(SKIPPED);
  if (!data) return;
  const msg = 'event: skipped\ndata: ' + JSON.stringify(data) + '\n\n';
  for (const client of sseClients) {
    try { client.write(msg); } catch { sseClients.delete(client); }
  }
}

function startTrackerWatch() {
  if (trackerWatcher) return;
  const dir = path.dirname(TRACKER);
  const trackerFile = path.basename(TRACKER);
  const skippedFile = path.basename(SKIPPED);
  try {
    trackerWatcher = fs.watch(dir, (event, filename) => {
      if (filename === trackerFile) broadcastJobs();
      if (filename === skippedFile) broadcastSkipped();
    });
  } catch {}
  // Fallback poll every 2s in case fs.watch misses events on Windows
  setInterval(() => { broadcastJobs(); broadcastSkipped(); }, 2000);
}
startTrackerWatch();

const server = http.createServer((req, res) => {
  const parsed = url.parse(req.url, true);
  const pathname = parsed.pathname;

  if (req.method === 'GET' && pathname === '/') {
    try {
      const html = fs.readFileSync(HTML, 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(html);
    } catch { res.writeHead(500); res.end('index.html not found'); }
    return;
  }

  if (req.method === 'GET' && pathname === '/api/jobs/stream') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    });
    res.write('\n');
    sseClients.add(res);
    // Send current state immediately
    const current = readJSON(TRACKER);
    if (current) {
      for (const j of (current.jobs || [])) {
        if (!('fit_score' in j) && 'fit' in j) j.fit_score = j.fit;
      }
      res.write('data: ' + JSON.stringify(current) + '\n\n');
      lastTrackerContent = JSON.stringify(current);
    }
    req.on('close', () => sseClients.delete(res));
    return;
  }

  if (req.method === 'GET' && pathname === '/api/jobs') {
    const data = readJSON(TRACKER);
    if (!data) { send(res, 200, { round: 0, last_updated: '', jobs: [] }); return; }
    for (const j of (data.jobs || [])) {
      if (!('fit_score' in j) && 'fit' in j) j.fit_score = j.fit;
    }
    send(res, 200, data);
    return;
  }

  if (req.method === 'GET' && pathname === '/api/skipped') {
    send(res, 200, readJSON(SKIPPED) || []);
    return;
  }

  if (req.method === 'GET' && pathname === '/api/rejections') {
    send(res, 200, readJSON(REJECTIONS) || []);
    return;
  }

  if (req.method === 'GET' && pathname === '/api/rejection-rules') {
    const data = readJSON(REJECTION_RULES_JSON);
    send(res, 200, data || null);
    return;
  }

  if (req.method === 'GET' && pathname === '/api/agent-context') {
    const agentMd = 'C:/agents/omda/CLAUDE.md';
    try {
      const content = fs.readFileSync(agentMd, 'utf8');
      send(res, 200, { ok: true, content });
    } catch (e) {
      send(res, 200, { ok: false, error: e.message });
    }
    return;
  }

  if (req.method === 'GET' && pathname === '/api/agent-status') {
    getAgentStatus(s => send(res, 200, s));
    return;
  }

  if (req.method === 'POST') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      let b;
      try { b = JSON.parse(body); } catch { send(res, 400, { ok: false }); return; }

      if (pathname === '/api/analyze-rejections') {
        const rejs = b.rejections || [];
        if (!rejs.length) { send(res, 200, { rules_text: '', keywords: [] }); return; }
        // Enrich each rejection with full job data from tracker
        const tracker = readJSON(TRACKER);
        const jobsById = {};
        if (tracker && tracker.jobs) {
          for (const j of tracker.jobs) jobsById[j.id] = j;
        }
        const enriched = rejs.map(r => Object.assign({}, jobsById[r.id] || {}, r));
        analyzeRejections(enriched, (err, output) => {
          if (err || !output) {
            send(res, 500, { error: 'Analysis failed', detail: err ? err.message : 'no output' });
            return;
          }
          // Extract keywords from the output
          const kws = new Set();
          const kwMatch = output.match(/KEYWORDS TO FLAG[^\n]*\n([^\n]+)/i);
          if (kwMatch) {
            kwMatch[1].split(',').map(k => k.trim().toLowerCase().replace(/[^a-z\s]/g, '').trim())
              .filter(k => k && k.length > 1)
              .forEach(k => kws.add(k));
          }
          const avoidLines = output.match(/avoid[^\n]*containing[:\s]+([^\n]+)/gi) || [];
          avoidLines.forEach(line => {
            line.replace(/avoid[^\n]*containing[:\s]+/i, '')
              .split(',').map(k => k.trim().toLowerCase()).filter(k => k.length > 2)
              .forEach(k => kws.add(k));
          });
          send(res, 200, { rules_text: output, keywords: [...kws] });
        });

      } else if (pathname === '/api/agent-start') {
        getAgentStatus(s => {
          if (s.status === 'searching' || s.status === 'queued') {
            send(res, 200, { ok: false, reason: 'Already running' }); return;
          }
          // Start search-loop as detached child process
          const { spawn } = require('child_process');
          const child = spawn('powershell.exe',
            ['-ExecutionPolicy', 'Bypass', '-File', SEARCH_LOOP],
            { detached: true, stdio: 'ignore', cwd: 'C:\\agents\\omda' }
          );
          child.unref();
          // Write PID so we can stop it later
          try { fs.writeFileSync('C:\\temp\\search-loop.pid', String(child.pid), { encoding: 'utf8' }); } catch {}
          send(res, 200, { ok: true, pid: child.pid });
        });

      } else if (pathname === '/api/agent-stop') {
        // Kill by PID
        let pid = null;
        try { pid = fs.readFileSync('C:\\temp\\search-loop.pid', 'utf8').trim(); } catch {}
        if (pid) {
          try { process.kill(Number(pid)); } catch {}
          try { fs.unlinkSync('C:\\temp\\search-loop.pid'); } catch {}
        }
        // Also kill claude processes and scheduled task
        exec('powershell -Command "Stop-ScheduledTask -TaskName \'' + SEARCH_TASK + '\' -ErrorAction SilentlyContinue; Get-Process -Name claude -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"',
          { timeout: 10000 },
          () => send(res, 200, { ok: true })
        );

      } else if (pathname === '/api/apply') {
        const data = readJSON(TRACKER);
        if (!data) { send(res, 200, { ok: false }); return; }
        for (const j of (data.jobs || [])) { if (j.id === b.id) j.status = 'applied'; }
        send(res, 200, { ok: writeJSON(TRACKER, data) });

      } else if (pathname === '/api/unapply') {
        const data = readJSON(TRACKER);
        if (!data) { send(res, 200, { ok: false }); return; }
        for (const j of (data.jobs || [])) { if (j.id === b.id) j.status = 'active'; }
        send(res, 200, { ok: writeJSON(TRACKER, data) });

      } else if (pathname === '/api/clear-tracker') {
        const empty = { round: 0, last_updated: '', jobs: [] };
        send(res, 200, { ok: writeJSON(TRACKER, empty) });

      } else if (pathname === '/api/clear-skipped') {
        send(res, 200, { ok: writeJSON(SKIPPED, []) });

      } else if (pathname === '/api/clear-rules') {
        let ok = true;
        try { if (fs.existsSync(REJECTION_RULES_JSON)) fs.unlinkSync(REJECTION_RULES_JSON); } catch { ok = false; }
        try { if (fs.existsSync(REJECTION_RULES_MD)) fs.unlinkSync(REJECTION_RULES_MD); } catch { ok = false; }
        try { fs.writeFileSync(REJECTIONS, '[]', { encoding: 'utf8' }); } catch { ok = false; }
        send(res, 200, { ok });

      } else if (pathname === '/api/reject') {
        let entries = readJSON(REJECTIONS) || [];
        entries = entries.filter(e => e.id !== b.id);
        entries.push({ id: b.id, company: b.company || '', title: b.title || '', reason: b.reason || '', date: new Date().toISOString().slice(0, 10) });
        send(res, 200, { ok: writeJSON(REJECTIONS, entries) });

      } else if (pathname === '/api/save') {
        const data = readJSON(TRACKER);
        if (!data) { send(res, 200, { ok: false }); return; }
        for (const j of (data.jobs || [])) { if (j.id === b.id) j.status = 'saved'; }
        send(res, 200, { ok: writeJSON(TRACKER, data) });

      } else if (pathname === '/api/unreject') {
        let entries = readJSON(REJECTIONS) || [];
        entries = entries.filter(e => e.id !== b.id);
        send(res, 200, { ok: writeJSON(REJECTIONS, entries) });

      } else if (pathname === '/api/rejection-rules') {
        const payload = {
          rules_text: b.rules_text || '',
          keywords: b.keywords || [],
          updated: b.updated || new Date().toISOString().slice(0, 10)
        };
        const okJson = writeJSON(REJECTION_RULES_JSON, payload);
        let okMd = false;
        try {
          fs.writeFileSync(REJECTION_RULES_MD, payload.rules_text, { encoding: 'utf8' });
          okMd = true;
        } catch {}
        send(res, 200, { ok: okJson && okMd });

      } else { res.writeHead(404); res.end(); }
    });
    return;
  }

  res.writeHead(404); res.end('Not found');
});

server.listen(PORT, '0.0.0.0', () => {
  console.log('Job Dashboard on port ' + PORT);
});
