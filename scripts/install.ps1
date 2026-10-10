param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }),
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$skillsRoot = Join-Path $CodexHome 'skills'
$sourceSkill = Join-Path $repoRoot '.agents\skills\journal-word-compiler-en'
$targetSkill = Join-Path $skillsRoot 'journal-word-compiler-en'
$engineRoot = Join-Path $skillsRoot 'format-agent-skill'

if (-not (Test-Path -LiteralPath $sourceSkill -PathType Container)) {
    throw "Skill source not found: $sourceSkill"
}
if (Test-Path -LiteralPath $targetSkill) {
    throw "Refusing to overwrite existing Skill: $targetSkill"
}

New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null
& $Python -m pip install -r (Join-Path $repoRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }

if (-not (Test-Path -LiteralPath $engineRoot)) {
    git clone https://github.com/KaguraNanaga/format-agent-skill $engineRoot
    if ($LASTEXITCODE -ne 0) { throw 'format-agent-skill clone failed.' }
}

Copy-Item -LiteralPath $sourceSkill -Destination $targetSkill -Recurse

$soffice = Get-Command soffice -ErrorAction SilentlyContinue
if (-not $soffice -and -not (Test-Path -LiteralPath 'C:\Program Files\LibreOffice\program\soffice.exe')) {
    Write-Warning 'LibreOffice was not found. Install it before running rendered QA.'
}

Write-Host "Installed journal-word-compiler-en to $targetSkill"
Write-Host 'Restart Codex if the Skill is not detected automatically.'
