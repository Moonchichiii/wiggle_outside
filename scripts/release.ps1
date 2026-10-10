#!/usr/bin/env pwsh
# Build the release zip from an explicit manifest, unpack it into a temp directory and run
# the gates there (PLAN section 8). Includes .env.example; excludes .env, caches and data/.
#
# M0 ships this so the release path exists and is reviewable. It is not part of the M0
# acceptance and has not been exercised against a release candidate.

[CmdletBinding()]
param(
    [string]$OutDir = 'out'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Manifest = @(
    'src'
    'tests'
    'scripts'
    'frontend'
    'docs'
    'pyproject.toml'
    'uv.lock'
    'package.json'
    'bun.lock'
    'bunfig.toml'
    'ruff.toml'
    'mypy.ini'
    'pytest.ini'
    '.importlinter'
    '.python-version'
    '.gitattributes'
    'gates.lock'
    'README.md'
    'LICENSE'
    'SECURITY.md'
    '.env.example'
)
# Never shipped, even if a manifest entry would otherwise sweep them in.
$Excluded = @('.env', 'data', '__pycache__', '.venv', 'node_modules', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', '.coverage', 'out')

$outPath = Join-Path $RepoRoot $OutDir
New-Item -ItemType Directory -Force -Path $outPath | Out-Null
$staging = Join-Path $outPath 'release-staging'
if (Test-Path -LiteralPath $staging) { Remove-Item -Recurse -Force $staging }
New-Item -ItemType Directory -Force -Path $staging | Out-Null

foreach ($entry in $Manifest) {
    $source = Join-Path $RepoRoot $entry
    if (-not (Test-Path -LiteralPath $source)) {
        Write-Host "manifest entry missing, skipped: $entry" -ForegroundColor Yellow
        continue
    }
    Copy-Item -Path $source -Destination $staging -Recurse -Force
}

foreach ($name in $Excluded) {
    Get-ChildItem -Path $staging -Force -Recurse -Filter $name -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

$zip = Join-Path $outPath 'wiggle-outside.zip'
if (Test-Path -LiteralPath $zip) { Remove-Item -Force $zip }
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zip
Write-Host "Wrote $zip" -ForegroundColor Green

# Prove the archive is self-sufficient: unpack somewhere else and run the gates there.
$verifyDir = Join-Path ([System.IO.Path]::GetTempPath()) "wiggle-release-$(Get-Random)"
New-Item -ItemType Directory -Force -Path $verifyDir | Out-Null
Expand-Archive -Path $zip -DestinationPath $verifyDir
Push-Location $verifyDir
try {
    & (Join-Path $verifyDir 'scripts/check.ps1') -Check
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
    Remove-Item -Recurse -Force $verifyDir -ErrorAction SilentlyContinue
}

if ($code -ne 0) {
    Write-Host 'The unpacked release failed the gates.' -ForegroundColor Red
    exit 1
}
Write-Host 'The unpacked release passed the gates.' -ForegroundColor Green
