# scripts/install_r_packages.ps1
# Installs required R packages for the project's R scripts on Windows.
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\install_r_packages.ps1

$Rscript = Get-Command Rscript -ErrorAction SilentlyContinue
if (-not $Rscript) {
  Write-Error "Rscript not found. Please install R from https://cran.r-project.org/ and ensure Rscript is on your PATH."
  exit 1
}

$pkgs = @("tidyverse","trend","Kendall","broom","sf","writexl")
$tmp = Join-Path $env:TEMP "install_r_pkgs.R"

$script = @"
pkgs <- c("tidyverse","trend","Kendall","broom","sf","writexl")
install_if_missing <- function(p) {
  if (!requireNamespace(p, quietly = TRUE)) {
    install.packages(p, repos = 'https://cloud.r-project.org')
  } else {
    message(paste(p, 'already installed'))
  }
}
invisible(lapply(pkgs, install_if_missing))
cat('R package installation complete\n')
"@

$script | Out-File -FilePath $tmp -Encoding UTF8
Write-Host "Running: Rscript $tmp"
& Rscript $tmp

if ($LASTEXITCODE -ne 0) {
  Write-Error "Rscript exited with code $LASTEXITCODE. If installation of 'sf' fails on Windows, consider installing system dependencies (GDAL/PROJ) or use conda-forge: 'conda install -c conda-forge r-sf'"
  exit $LASTEXITCODE
}

Remove-Item $tmp -ErrorAction SilentlyContinue
Write-Host "R package installation finished successfully."
