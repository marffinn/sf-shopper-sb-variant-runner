$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$LogFile = Join-Path $ScriptDir "run_log.txt"

function Write-Both {
    param([string]$Message)
    $TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $FormattedMessage = "[$TimeStamp] $Message"
    Write-Output $FormattedMessage
    Add-Content -Path $LogFile -Value $FormattedMessage
}

Write-Both "----------------------------------------"
Write-Both "Starting update run..."
Write-Both "----------------------------------------"

$venvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$scriptPath = Join-Path $ScriptDir "build_variant_map.py"

# Run Python script, capture all streams, output to screen and append to log
& $venvPython -u $scriptPath 2>&1 | Tee-Object -FilePath $LogFile -Append

if ($LASTEXITCODE -ne 0) {
    Write-Both "ERROR: Python script failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# Check for changes in variant_map.json and products.json
Write-Both "Checking for changes..."
$changes = git status --porcelain variant_map.json products.json
if ($changes) {
    Write-Both "Changes detected. Staging, committing, and pushing..."
    git add variant_map.json products.json 2>&1 | Tee-Object -FilePath $LogFile -Append
    git commit -m "Auto-update variant map and products ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))" 2>&1 | Tee-Object -FilePath $LogFile -Append
    git push 2>&1 | Tee-Object -FilePath $LogFile -Append
    Write-Both "Push completed successfully."
} else {
    Write-Both "No changes to variant_map.json or products.json detected."
}
