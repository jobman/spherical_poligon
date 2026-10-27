param(
    [string] $Version = '6000.3.27f1',
    [switch] $Open
)

$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot
$projectPath = Join-Path $workspacePath 'SphericalCivilization'
$versionFile = Join-Path $projectPath 'ProjectSettings\ProjectVersion.txt'

if (-not (Test-Path -LiteralPath $versionFile)) {
    if (Test-Path -LiteralPath $projectPath) {
        throw "The target directory exists without a Unity project: $projectPath"
    }

    $templateResult = (& unity templates list --editor $Version --type core --format json |
        Out-String) | ConvertFrom-Json
    if (-not $templateResult.success) {
        throw 'Unable to query the Editor template catalog.'
    }
    $urpTemplate = @($templateResult.data | Where-Object {
        $_.name -eq 'com.unity.template.urp-blank' -and $_.renderPipeline -eq 'URP'
    })
    if ($urpTemplate.Count -ne 1) {
        throw 'The expected Universal 3D (URP) template was not found.'
    }

    & unity projects create SphericalCivilization --path $workspacePath `
        --editor-version $Version --template $urpTemplate[0].name `
        --no-cloud --non-interactive --format json
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

& unity pipeline install --project-path $projectPath --non-interactive --format json
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($Open) {
    & unity open $projectPath
    exit $LASTEXITCODE
}
