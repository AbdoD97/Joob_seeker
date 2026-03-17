<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (90-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk vitest run          # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->

## Job Search Rules
- Always show direct job posting links in results — never search/portal redirect links. Verify each URL points to the specific job posting.
- Before discarding a job for a broken/expired link, search the internet for an alternative URL for that same position before removing it from the tracker.
- Job searches default to 10-day freshness filter unless explicitly told otherwise.
- LinkedIn is temporarily disabled for job searches (soft ban risk). Search these platforms instead: Indeed NL, IamExpat, Undutchables, Glassdoor NL, StepStone NL, Nationale Vacaturebank, Google Jobs.
- Always include salary range in job results and Telegram notifications. If not stated in the posting, write "not listed".
- Hard exclude: managerial titles (Manager, Head of, Director, Lead, Senior Manager), jobs requiring 4+ years experience, hands-on physical supply chain roles.
- Rank by years of experience required ascending — jobs requiring fewer years get higher priority (1yr > 2yr > 3yr). Mohammad is intentionally targeting roles he is overqualified for to maximize interview callback rate.

## Guardrails
- When constructing commands that cross shell boundaries (bash -> PowerShell, SSH -> cmd), ALWAYS write to a .ps1 file and execute via file path — never build inline quoted strings. Nested quote layers (single/double/escaped) across bash+SSH+PowerShell reliably break.
- NEVER dispatch a new omda job search task if one is already running or queued. Always check `manage.ps1 status omda` first — if any task shows `running` or `queued`, refuse and inform the user. Stop the existing task first if a new one is needed.
- Always display dates and times in Amsterdam timezone (Europe/Amsterdam, CET/CEST). When showing timestamps from VPS or other sources, convert to Amsterdam time.
- Never let any search task exceed 30 minutes. If a search is still running after 30 min, kill it automatically. Apply this in search-loop.ps1 execution time limits and scheduled task settings.

## Agent Factory
- When creating agents, save the configuration as a reusable template in the create-agent skill.
- VPS agents use Claude Max subscription auth (browser login), not Anthropic API keys. No API billing.
- Agents have zero idle cost — they only consume resources during active task execution (scheduled task runs, completes, self-unregisters).
- Store third-party API credentials (Telegram, Gmail, tokens) in `C:\secrets\<service>\` on the VPS — never in `C:\agents\`. Agent config files should only store the `secrets_path` reference, not the actual credentials.
