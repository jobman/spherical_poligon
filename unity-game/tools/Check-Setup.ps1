param()

$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot
$projectPath = Join-Path $workspacePath 'SphericalCivilization'

function Invoke-UnityJson {
    param([string[]] $UnityArguments)
    $output = & unity @UnityArguments --format json
    $result = ($output -join [Environment]::NewLine) | ConvertFrom-Json
    if ($null -eq $result.success) {
        throw 'Unity CLI did not return its expected JSON response.'
    }
    return $result
}

if (-not (Get-Command unity -ErrorAction SilentlyContinue)) {
    throw 'Unity CLI is missing. See SETUP.md.'
}

$cliVersion = & unity --version
$plugins = (& codex plugin list --json | Out-String) | ConvertFrom-Json
$unityPlugin = $plugins.installed | Where-Object {
    $_.pluginId -eq 'unity@unity-agent-plugin'
}
$license = Invoke-UnityJson @('license', 'status')
$editors = Invoke-UnityJson @('editors', '--installed')
$versionFile = Join-Path $projectPath 'ProjectSettings\ProjectVersion.txt'

$projectVersion = $null
if (Test-Path -LiteralPath $versionFile) {
    $projectVersion = (Get-Content -LiteralPath $versionFile |
        Select-String '^m_EditorVersion: ').Line -replace '^m_EditorVersion: ', ''
}

[ordered]@{
    workspace = $workspacePath
    project = $projectPath
    projectCreated = Test-Path -LiteralPath $versionFile
    editorVersion = $projectVersion
    cliVersion = $cliVersion
    officialPluginInstalled = [bool]$unityPlugin
    officialPluginEnabled = [bool]$unityPlugin.enabled
    licenseActive = [bool]$license.data.active
    installedEditors = @($editors.data | Select-Object version, location)
} | ConvertTo-Json -Depth 5

if (-not (Test-Path -LiteralPath $versionFile)) {
    exit 2
}
if (-not $unityPlugin.enabled -or -not $license.data.active) {
    exit 3
}
