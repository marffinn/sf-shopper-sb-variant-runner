$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Write-Msg {
    param([string]$Message)
    $TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $FormattedMessage = "[$TimeStamp] $Message"
    Write-Output $FormattedMessage
}

Write-Msg "----------------------------------------"
Write-Msg "Starting Shoper update run..."
Write-Msg "----------------------------------------"

$venvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$scriptPath = Join-Path $ScriptDir "build_variant_map.py"

# Run Python script
& $venvPython -u $scriptPath

if ($LASTEXITCODE -ne 0) {
    Write-Msg "ERROR: Python script failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# --- Shoper CLI deployment ---
# Remove any existing theme directories (the timestamp suffix changes on each pull)
Write-Msg "Pulling fresh theme from Shoper..."
Get-ChildItem -Path $ScriptDir -Directory -Filter "3_STARFIX-AMEX_*" | Remove-Item -Recurse -Force

shoper theme pull 3

if ($LASTEXITCODE -ne 0) {
    Write-Msg "ERROR: Shoper theme pull failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# Find the newly pulled theme directory (name includes a changing timestamp)
$themeDir = (Get-ChildItem -Path $ScriptDir -Directory -Filter "3_STARFIX-AMEX_*" | Select-Object -First 1).FullName

if (-not $themeDir) {
    Write-Msg "ERROR: Could not find pulled theme directory."
    exit 1
}
Write-Msg "Theme pulled to: $themeDir"

# Create an assets folder inside the theme directory
$assetsDir = Join-Path $themeDir "assets"
New-Item -ItemType Directory -Path $assetsDir | Out-Null
Write-Msg "Created assets directory."

# Copy generated files into the theme's assets folder
$filesToPush = @("variant_map.json", "products.json", "menu.json", "mega_menu_snippet.html")
foreach ($file in $filesToPush) {
    $src = Join-Path $ScriptDir $file
    $dst = Join-Path $assetsDir $file
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Force
        Write-Msg "Copied $file -> assets/$file"
    } else {
        Write-Msg "WARNING: $file not found, skipping."
    }
}

# Push from inside the theme directory
Write-Msg "Pushing to Shoper..."
Set-Location $themeDir
shoper theme push

if ($LASTEXITCODE -ne 0) {
    Set-Location $ScriptDir
    Write-Msg "ERROR: Shoper push failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# Return to script directory
Set-Location $ScriptDir

Write-Msg "Shoper deployment completed successfully."
Write-Msg "----------------------------------------"
Write-Msg "Public URLs for your files:"
Write-Msg "----------------------------------------"
$shopUrl = "https://sklep.starfix.eu"
foreach ($file in $filesToPush) {
    Write-Msg "  $shopUrl/assets/$file"
}
Write-Msg "----------------------------------------"
