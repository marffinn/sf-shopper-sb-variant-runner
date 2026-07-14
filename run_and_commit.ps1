$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Write-Msg {
    param([string]$Message)
    $TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $FormattedMessage = "[$TimeStamp] $Message"
    Write-Output $FormattedMessage
}

Write-Msg "----------------------------------------"
Write-Msg "Starting update run..."
Write-Msg "----------------------------------------"

$venvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$scriptPath = Join-Path $ScriptDir "build_variant_map.py"

# Run Python script
& $venvPython -u $scriptPath

if ($LASTEXITCODE -ne 0) {
    Write-Msg "ERROR: Python script failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# Check for changes in variant_map.json and products.json
Write-Msg "Checking for changes..."
$changes = git status --porcelain variant_map.json products.json
if ($changes) {
    Write-Msg "Changes detected. Staging, committing, and pushing..."
    git add variant_map.json products.json
    git commit -m "Auto-update variant map and products ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))"
    git push
    Write-Msg "Push completed successfully."
} else {
    Write-Msg "No changes to variant_map.json or products.json detected."
}
