# CTX-A3-GH operator-invoked draft PR publisher.
# NO --apply / -Apply -> no external writes. Never modify Rulesets, merge or issue checks.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RepositoryRoot,
    [Parameter(Mandatory=$true)][string]$ContextEngineRoot,
    [Parameter(Mandatory=$true)][string]$CandidateRoot,
    [Parameter(Mandatory=$true)][string]$Repository,
    [Parameter(Mandatory=$true)][string]$ExpectedMainSha,
    [switch]$Apply
)
$ErrorActionPreference='Stop'
function Run([string]$label, [scriptblock]$command) {
    & $command
    if ($LASTEXITCODE -ne 0) { throw "FAILED_$label" }
}
if ($Repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' -or $ExpectedMainSha -cnotmatch '^[0-9a-f]{40}$') { throw 'INVALID_INPUT' }
$repoPath=(Resolve-Path -LiteralPath $RepositoryRoot).Path
$enginePath=(Resolve-Path -LiteralPath $ContextEngineRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $enginePath 'adp_context/github_checkpoint.py') -PathType Leaf)) { throw 'ENGINE_NOT_FOUND' }
# Python resolves the reviewed engine from its pinned local directory.
$env:PYTHONPATH=$enginePath
$candidatePath=(Resolve-Path -LiteralPath $CandidateRoot).Path
if ($candidatePath -eq $repoPath -or $candidatePath.StartsWith($repoPath + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'STAGE_MUST_BE_OUTSIDE_REPOSITORY' }
$manifestPath=Join-Path $candidatePath 'candidate.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'MANIFEST_NOT_FOUND' }
Set-Location $repoPath
Run 'CANDIDATE_CHECK' { py -3.13 -B -m adp_context.github_checkpoint check --root $candidatePath --repository $Repository --main-sha $ExpectedMainSha }
$manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$relative=$manifest.journal_path
if ($relative -notmatch '^\.adp/checkpoints/[A-Za-z0-9_.:-]+/[A-Za-z0-9_.:-]+/journal\.jsonl$') { throw 'PATH_INVALID' }
$who=gh api user --jq .login
if ($LASTEXITCODE -ne 0) { throw 'IDENTITY_NOT_VERIFIED' }
$actualRepo=gh repo view --json nameWithOwner --jq .nameWithOwner
if ($LASTEXITCODE -ne 0 -or $actualRepo -cne $Repository) { throw 'REPO_NOT_VERIFIED' }
$branch=(git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { throw 'LOCAL_BRANCH_FAILURE' }
$status=@(git status --porcelain)
if ($LASTEXITCODE -ne 0 -or $status.Count -ne 0) { throw 'DIRTY_WORKTREE' }
Run 'FETCH' { git fetch origin main }
$remoteMain=(git rev-parse origin/main).Trim()
if ($LASTEXITCODE -ne 0 -or $remoteMain -cne $ExpectedMainSha) { throw 'MAIN_CHANGED' }
$remoteBranch='adp/context/' + ($manifest.project_id -replace '[:.]','-') + '-' + ($manifest.task_id -replace '[:.]','-') + '-' + $manifest.candidate_sha256.Substring(0,12)
# 'ls-remote' ensures no existing branch is silently overwritten. Racing pushes are rejected by remote.
$existing=@(git ls-remote --heads origin $remoteBranch)
if ($LASTEXITCODE -ne 0 -or $existing.Count -gt 0) { throw 'CANDIDATE_BRANCH_EXISTS_RECONCILE_FIRST' }
if ($branch -eq $remoteBranch) { throw 'ALREADY_ON_CANDIDATE_BRANCH' }
if (-not $Apply) {
    Write-Host 'CTX_A3_GH_PREFLIGHT_PASS_NO_WRITE'
    Write-Host "PROPOSED_BRANCH=$remoteBranch"
    Write-Host "REPOSITORY=$Repository"
    Write-Host "ACTOR=$who"
    exit 0
}
# From here operations may create local commit and remote PR; re-run after partial failure is prohibited.
Run 'BRANCH_CREATE' { git switch -c $remoteBranch origin/main }
$from=Join-Path $candidatePath ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
$to=Join-Path $repoPath ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
if (Test-Path -LiteralPath $to) { throw 'HISTORY_EXISTS_NO_OVERWRITE' }
$parent=Split-Path -Parent $to
New-Item -ItemType Directory -Path $parent -Force | Out-Null
Copy-Item -LiteralPath $from -Destination $to
$relativeManifest='.adp/checkpoints/' + $manifest.project_id + '/' + $manifest.task_id + '/candidate.json'
$toManifest=Join-Path $repoPath ($relativeManifest -replace '/', [IO.Path]::DirectorySeparatorChar)
if (Test-Path -LiteralPath $toManifest) { throw 'CANDIDATE_MANIFEST_EXISTS_NO_OVERWRITE' }
Copy-Item -LiteralPath $manifestPath -Destination $toManifest
Run 'ADD' { git add -- $relative $relativeManifest }
Run 'DIFF' { git diff --cached --check }
$changed=@(git diff --cached --name-only)
if ($LASTEXITCODE -ne 0 -or (Compare-Object ($changed | Sort-Object) (@($relative,$relativeManifest) | Sort-Object))) { throw 'UNEXPECTED_STAGED_FILES' }
Run 'COMMIT' { git commit -m "docs(adp-context): checkpoint draft $($manifest.project_id) $($manifest.task_id)" }
$head=(git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'COMMIT_SHA_UNAVAILABLE' }
Run 'PUSH' { git push -u origin $remoteBranch }
Run 'PR_CREATE' { gh pr create --repo $Repository --draft --base main --head $remoteBranch --title "CTX candidate: $($manifest.project_id)/$($manifest.task_id)" --body "UNVERIFIED CONTEXT CHECKPOINT CANDIDATE ONLY. Commit $head. Requires protected CI and independent review; no resume, issuer or merge authority." }
Write-Host 'CTX_A3_GH_DRAFT_PR_CREATED_NOT_APPROVED'
Write-Host "COMMIT_SHA=$head"
Write-Host "CANDIDATE_SHA256=$($manifest.candidate_sha256)"
