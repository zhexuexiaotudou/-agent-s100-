param(
    [string]$OutputDir = "reports/github-workflow"
)

$ErrorActionPreference = "Stop"

function Run-Git {
    param([string[]]$GitArgs)
    $output = & git @GitArgs 2>&1
    [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function Escape-Md {
    param([string]$Text)
    if ($null -eq $Text -or $Text -eq "") { return "" }
    return ($Text -replace "\|", "\|").Trim()
}

$repoRootResult = Run-Git -GitArgs @("rev-parse", "--show-toplevel")
if ($repoRootResult.ExitCode -ne 0) {
    throw "Not inside a git repository: $($repoRootResult.Output)"
}

$repoRoot = $repoRootResult.Output.Trim()
Set-Location $repoRoot

if ([System.IO.Path]::IsPathRooted($OutputDir)) {
    $reportDir = $OutputDir
} else {
    $reportDir = Join-Path $repoRoot $OutputDir
}
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $reportDir "github_workflow_$stamp.md"

$branch = (Run-Git -GitArgs @("branch", "--show-current")).Output.Trim()
$remoteLines = (Run-Git -GitArgs @("remote", "-v")).Output.Trim()
$statusShort = (Run-Git -GitArgs @("status", "--short")).Output
$dirtyCount = if ($statusShort.Trim() -eq "") { 0 } else { ($statusShort -split "`n" | Where-Object { $_.Trim() -ne "" }).Count }

$originReachable = "warn"
$originDetail = "origin remote not configured"
if ($remoteLines -match "(?m)^origin\s+") {
    $lsRemote = Run-Git -GitArgs @("ls-remote", "--heads", "origin")
    if ($lsRemote.ExitCode -eq 0 -and $lsRemote.Output.Trim() -ne "") {
        $originReachable = "pass"
        $originDetail = "origin reachable; heads returned"
    } else {
        $originReachable = "fail"
        $originDetail = "origin unreachable or returned no heads"
    }
}

$upstream = Run-Git -GitArgs @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
$upstreamStatus = if ($upstream.ExitCode -eq 0) { "pass" } else { "warn" }
$upstreamDetail = if ($upstream.ExitCode -eq 0) { $upstream.Output.Trim() } else { "no upstream for current branch" }

$ghCommand = Get-Command gh -ErrorAction SilentlyContinue
$ghStatus = "warn"
$ghDetail = "gh CLI not found"
if ($ghCommand) {
    $ghVersion = & gh --version 2>&1
    $ghAuth = & gh auth status 2>&1
    if ($LASTEXITCODE -eq 0) {
        $ghStatus = "pass"
        $ghDetail = "gh installed and authenticated"
    } else {
        $ghStatus = "warn"
        $ghDetail = "gh installed but auth status did not pass"
    }
}

$issueSeedPath = Join-Path $repoRoot "docs/github_issue_seed.md"
$issueSeedStatus = if (Test-Path $issueSeedPath) { "pass" } else { "warn" }
$issueSeedDetail = if (Test-Path $issueSeedPath) { "docs/github_issue_seed.md exists" } else { "docs/github_issue_seed.md missing" }

$remoteIssuePath = Join-Path $repoRoot "docs/github_remote_issue.md"
$remoteIssueStatus = if (Test-Path $remoteIssuePath) { "pass" } else { "warn" }
$remoteIssueDetail = "docs/github_remote_issue.md missing"
if (Test-Path $remoteIssuePath) {
    $remoteIssueText = Get-Content -Path $remoteIssuePath -Raw
    if ($remoteIssueText -match "https://github.com/\S+/issues/\d+") {
        $remoteIssueDetail = $Matches[0]
    } else {
        $remoteIssueDetail = "docs/github_remote_issue.md exists"
    }
}

$remotePrPath = Join-Path $repoRoot "docs/github_remote_pr.md"
$remotePrStatus = if (Test-Path $remotePrPath) { "pass" } else { "warn" }
$remotePrDetail = "docs/github_remote_pr.md missing"
if (Test-Path $remotePrPath) {
    $remotePrText = Get-Content -Path $remotePrPath -Raw
    if ($remotePrText -match "https://github.com/\S+/pull/\d+") {
        $remotePrDetail = $Matches[0]
    } else {
        $remotePrDetail = "docs/github_remote_pr.md exists"
    }
}

$userName = (Run-Git -GitArgs @("config", "--get", "user.name")).Output.Trim()
$userEmail = (Run-Git -GitArgs @("config", "--get", "user.email")).Output.Trim()
$identityStatus = if ($userName -and $userEmail) { "pass" } else { "warn" }
$identityDetail = if ($identityStatus -eq "pass") { "$userName <$userEmail>" } else { "git user.name or user.email missing" }

$prReadiness = "blocked"
$prDetail = "working tree has $dirtyCount changed/untracked paths; create a scoped commit before PR"
if ($dirtyCount -eq 0 -and $originReachable -eq "pass") {
    if ($ghStatus -eq "pass") {
        $prReadiness = "pass"
        $prDetail = "ready for issue -> branch -> PR through gh"
    } else {
        $prReadiness = "warn"
        $prDetail = "git remote is ready; install/authenticate gh or use GitHub web/connector for issue and PR"
    }
}

$statusPreview = if ($statusShort.Trim() -eq "") {
    "clean"
} else {
    ($statusShort -split "`n" | Select-Object -First 80) -join "`n"
}

$b006Verdict = "B-006 is ready for local workflow planning, but not verified end-to-end yet."
$b006Blockers = @()
if ($ghStatus -ne "pass") {
    $b006Blockers += "- `gh` CLI is not installed or not on PATH; GitHub connector or web UI is required for remote operations."
}
if ($dirtyCount -ne 0) {
    $b006Blockers += "- The working tree has uncommitted/untracked baseline work, so a clean scoped branch/commit is needed before PR creation."
}
if ($remoteIssueStatus -ne "pass") {
    $b006Blockers += "- Remote issue marker is missing."
}
if ($remotePrStatus -ne "pass") {
    $b006Blockers += "- Remote draft PR marker is missing."
}
if ($remoteIssueStatus -eq "pass" -and $remotePrStatus -eq "pass" -and $dirtyCount -eq 0) {
    $b006Verdict = "B-006 has a verified remote issue, pushed branch, draft PR marker, and a clean local working tree."
    if ($b006Blockers.Count -eq 1 -and $b006Blockers[0] -like "- ``gh`` CLI*") {
        $b006Blockers = @("- No B-006 workflow blocker remains when using the GitHub connector; `gh` is optional.")
    }
}
$b006BlockersText = if ($b006Blockers.Count -gt 0) { $b006Blockers -join "`n" } else { "- None." }

$markdown = @"
# GitHub/Codex Workflow Readiness

- generated_at: $(Get-Date -Format o)
- repo_root: $repoRoot
- current_branch: $branch
- report: $reportPath

## Verdict Matrix

| Check | Status | Detail |
| --- | --- | --- |
| Origin remote | $originReachable | $(Escape-Md $originDetail) |
| Current branch upstream | $upstreamStatus | $(Escape-Md $upstreamDetail) |
| GitHub CLI | $ghStatus | $(Escape-Md $ghDetail) |
| Git identity | $identityStatus | $(Escape-Md $identityDetail) |
| Issue seed | $issueSeedStatus | $(Escape-Md $issueSeedDetail) |
| Remote issue marker | $remoteIssueStatus | $(Escape-Md $remoteIssueDetail) |
| Remote PR marker | $remotePrStatus | $(Escape-Md $remotePrDetail) |
| Working tree | $(if ($dirtyCount -eq 0) { "pass" } else { "warn" }) | $dirtyCount changed or untracked paths |
| PR readiness | $prReadiness | $(Escape-Md $prDetail) |

## Remote

~~~text
$remoteLines
~~~

## Working Tree Preview

~~~text
$statusPreview
~~~

## Safe Next Commands

Do not run these until the current baseline changes are reviewed and intentionally scoped.

~~~powershell
git switch -c baseline/b-006-github-workflow
git add README.md docs scripts openclaw-plugins
git commit -m "Add OpenClaw S100P baseline probes"
git push -u origin baseline/b-006-github-workflow
~~~

If `gh` is installed and authenticated:

~~~powershell
gh issue create --title "Track OpenClaw S100P baseline completion" --body-file docs/github_issue_seed.md
gh pr create --draft --base main --head baseline/b-006-github-workflow --title "Add OpenClaw S100P baseline probes" --body "Adds audited probes and runbooks for the S100P + NAS baseline."
~~~

## Current B-006 Verdict

$b006Verdict

The current blockers are:

$b006BlockersText
"@

Set-Content -Path $reportPath -Value $markdown -Encoding UTF8
Write-Output $reportPath
