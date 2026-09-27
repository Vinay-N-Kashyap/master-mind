# Master Memory Engine Background Sync Launcher
$ErrorActionPreference = "SilentlyContinue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir
$UvBin = "$HOME\.local\bin\uv.exe"

if (-not (Test-Path $UvBin)) {
    $UvBin = "uv"
}

# Run detached sync pipeline
Set-Location -Path $ProjectRoot
& $UvBin run python src/sync_on_commit.py >> "$ProjectRoot/.sync.log" 2>&1
exit 0
