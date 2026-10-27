param()

$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot
$projectPath = Join-Path $workspacePath 'SphericalCivilization'
$versionFile = Join-Path $projectPath 'ProjectSettings\ProjectVersion.txt'

if (-not (Test-Path -LiteralPath $versionFile)) {
    throw 'The Unity project has not been created yet. See SETUP.md.'
}

& unity open $projectPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
