#!/usr/bin/env pwsh
# The one gate script. CI runs this same file on ubuntu-latest with `shell: pwsh`
# (TC-004), so it must stay portable: no drive letters, no backslash path literals,
# Join-Path for paths, tools through `uv run` and `bun run`.
#
# M0 runs five gates: ruff format, ruff lint, mypy, import-linter, pytest (which includes
# the contract tests). WP9b adds the rest (TC-006) - this script names them as skipped
# rather than pretending they ran.
#
# Writes only to git-ignored output directories and never modifies maintained source.

[CmdletBinding()]
param(
    # Report formatting problems instead of rewriting files. CI passes this.
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

$script:Failures = [System.Collections.Generic.List[string]]::new()
$script:Skipped = [System.Collections.Generic.List[string]]::new()

function Invoke-Gate {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][scriptblock]$Body
    )

    Write-Host ''
    Write-Host "== $Name " -NoNewline
    Write-Host ('=' * [Math]::Max(1, 68 - $Name.Length))

    & $Body
    $code = $LASTEXITCODE

    if ($code -ne 0) {
        $script:Failures.Add("$Name (exit $code)")
        Write-Host "-- FAIL: $Name" -ForegroundColor Red
    }
    else {
        Write-Host "-- ok: $Name" -ForegroundColor Green
    }
}

Write-Host 'Wiggle Outside gates (M0 set; see TC-006 for what WP9b adds)'

# --- 0. Build prerequisites ---------------------------------------------------------
# Not a gate: the Tailwind build gate is WP9b's (TC-006). But the stylesheet is a
# gitignored build artifact, and one test asserts the page serves non-empty CSS, so a
# fresh checkout - including CI - has to build it before pytest runs. Skipped when bun
# is unavailable, and the test that needs it will say so rather than this failing here.
if (Get-Command bun -ErrorAction SilentlyContinue) {
    Write-Host ''
    Write-Host '== building the stylesheet (prerequisite, not a gate) =================='
    bun install --frozen-lockfile 2>&1 | Out-Null
    bun run build:css
    if ($LASTEXITCODE -ne 0) {
        $script:Failures.Add('bun run build:css')
        Write-Host '-- FAIL: bun run build:css' -ForegroundColor Red
    }
}
else {
    Write-Host 'bun not found: skipping the stylesheet build' -ForegroundColor Yellow
}

# --- 1. Formatting ------------------------------------------------------------------
if ($Check) {
    Invoke-Gate 'ruff format --check' { uv run ruff format --check . }
}
else {
    Invoke-Gate 'ruff format' { uv run ruff format . }
}

# --- 2. Lint ------------------------------------------------------------------------
Invoke-Gate 'ruff check' { uv run ruff check . }

# --- 3. Types -----------------------------------------------------------------------
Invoke-Gate 'mypy (strict)' { uv run mypy }

# --- 4. Architecture ----------------------------------------------------------------
Invoke-Gate 'import-linter (6 contracts)' { uv run lint-imports }

# --- 5. Tests, including the contract tests -----------------------------------------
Invoke-Gate 'pytest' { uv run pytest }

# --- Deferred to WP9b (TC-006). Named, not silently absent. -------------------------
foreach ($gate in @(
        'coverage thresholds (core 100 / planner 95 / total 90)',
        'policy tests (pinned actions, no inline script or style, source budgets)',
        'djLint, Biome, Stylelint, Tailwind production build',
        'contrast script (scripts/check_contrast.py)',
        'canonical audit (pip-audit, bun audit, OSV-Scanner)',
        'Playwright CSP and axe journeys'
    )) {
    $script:Skipped.Add($gate)
}

Write-Host ''
Write-Host ('-' * 72)
if ($script:Skipped.Count -gt 0) {
    Write-Host "Not run in M0, deferred to WP9b (TC-006):" -ForegroundColor Yellow
    foreach ($gate in $script:Skipped) { Write-Host "  - $gate" -ForegroundColor Yellow }
}

Pop-Location

if ($script:Failures.Count -gt 0) {
    Write-Host ''
    Write-Host "FAILED: $($script:Failures.Count) gate(s)" -ForegroundColor Red
    foreach ($failure in $script:Failures) { Write-Host "  - $failure" -ForegroundColor Red }
    exit 1
}

Write-Host ''
Write-Host 'All M0 gates passed.' -ForegroundColor Green
exit 0
