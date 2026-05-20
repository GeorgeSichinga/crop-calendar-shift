param(
  [switch]$Full
)

$Root = Resolve-Path -Path "."
$VenvPath = Join-Path $Root ".venv"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Error "Python not found in PATH. Please install Python 3.11+ from https://www.python.org/ and re-run."
  exit 1
}

if (-not (Test-Path $VenvPath)) {
  python -m venv $VenvPath
  Write-Host "Created virtual environment at $VenvPath"
} else {
  Write-Host "Using existing virtual environment at $VenvPath"
}

$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
  Write-Error "Activation script not found: $ActivateScript"
  exit 1
}

# Activate the venv for the remainder of the script
. $ActivateScript

python -m pip install --upgrade pip setuptools wheel

if ($Full) {
  Write-Host "Installing full requirements from requirements.txt (may fail on Windows for some geospatial wheels)..."
  pip install --upgrade -r requirements.txt
} else {
  $liteReq = @(
    "numpy>=1.24",
    "pandas>=2.0",
    "streamlit>=1.28",
    "plotly>=5.17"
  )
  $tmpFile = Join-Path $env:TEMP "requirements-lite.txt"
  $liteReq -join "`n" | Out-File -FilePath $tmpFile -Encoding UTF8
  Write-Host "Installing lightweight packages..."
  pip install --upgrade -r $tmpFile
  Remove-Item $tmpFile -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Setup complete. To activate the virtual environment in this shell run:"
Write-Host "  .\\.venv\\Scripts\\Activate.ps1"
Write-Host ""
Write-Host "Quick start commands:"
Write-Host "  python scripts/python/03_export_for_r.py --synthetic"
Write-Host "  streamlit run dashboard/app.py"
