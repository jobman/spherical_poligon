param(
    [string] $Version = '6000.3.27f1',
    [string] $InstallerPath = 'D:\Tools\Unity\Downloads\UnitySetup64-6000.3.27f1.exe',
    [string] $InstallRoot = 'D:\Tools\Unity\Editors',
    [string] $TempDirectory = 'D:\Tools\Unity\InstallerTemp'
)

$ErrorActionPreference = 'Stop'
$editorFolder = Join-Path $InstallRoot $Version
$editorExecutable = Join-Path $editorFolder 'Editor\Unity.exe'

if (-not (Test-Path -LiteralPath $editorExecutable)) {
    if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
        throw "The verified official Unity installer is missing: $InstallerPath"
    }

    New-Item -ItemType Directory -Path $InstallRoot, $TempDirectory -Force | Out-Null
    # Process-local overrides: Unity's large self-extracting installer must not
    # unpack on the nearly full system drive. No machine/user setting is changed.
    $env:TEMP = $TempDirectory
    $env:TMP = $TempDirectory

    $installer = Start-Process -FilePath $InstallerPath -ArgumentList @(
        '/S', "/D=$editorFolder"
    ) -WindowStyle Hidden -Wait -PassThru
    if ($installer.ExitCode -ne 0) {
        throw "The Unity installer exited with code $($installer.ExitCode)."
    }
    if (-not (Test-Path -LiteralPath $editorExecutable -PathType Leaf)) {
        throw "The installer finished without the expected Editor: $editorExecutable"
    }
}

$installedEditors = (& unity editors --installed --format json | Out-String) |
    ConvertFrom-Json
if (-not $installedEditors.success) {
    throw 'Unable to query installed Unity Editors.'
}
if (-not ($installedEditors.data | Where-Object { $_.version -eq $Version })) {
    & unity editors add $editorExecutable --format json
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

& unity editors verify $Version --format json
exit $LASTEXITCODE
