# scripts/run_r_trend.ps1
# Wrapper to run the R trend analysis script and report output locations.
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\run_r_trend.ps1

$Rscript = Get-Command Rscript -ErrorAction SilentlyContinue
if (-not $Rscript) {
  Write-Error "Rscript not found. Please install R from https://cran.r-project.org/ and ensure Rscript is on your PATH."
  exit 1
}

Write-Host "Running R trend analysis..."
& Rscript scripts/r/04_trend_analysis.R
if ($LASTEXITCODE -ne 0) {
  Write-Error "R script failed with exit code $LASTEXITCODE"
  exit $LASTEXITCODE
}

Write-Host "R trend analysis completed. Outputs are written to outputs/tables/."
Write-Host "You can now reload the Streamlit dashboard to pick up the trend tables."
