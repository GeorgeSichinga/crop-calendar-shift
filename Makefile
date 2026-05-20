# Makefile — Crop Calendar Climate Shift Analyser
# Run the full pipeline with: make all
# Or step by step with individual targets below.

.PHONY: all setup download extract export analyse plot dashboard report clean

## Full pipeline
all: setup download extract export analyse plot

## Create conda environment
setup:
	conda env create -f environment.yml || conda env update -f environment.yml
	@echo "Activate with: conda activate crop-calendar"

## Download CHIRPS data (skips existing files)
download:
	python scripts/python/01_download_chirps.py

## Extract OOR dates from CHIRPS (requires downloaded data)
extract:
	python scripts/python/02_extract_oor_dates.py

## Export clean CSV for R (add --synthetic to skip CHIRPS requirement)
export:
	python scripts/python/03_export_for_r.py

## Synthetic data only (fast — for testing the pipeline without downloading CHIRPS)
synthetic:
	python scripts/python/03_export_for_r.py --synthetic

## R trend analysis
analyse:
	Rscript scripts/r/04_trend_analysis.R

## R visualisations
plot:
	Rscript scripts/r/05_visualisations.R

## Launch Streamlit dashboard
dashboard:
	streamlit run dashboard/app.py

## Render Quarto report to HTML
report:
	quarto render report/report.qmd --to html

## Render Quarto report to PDF
report-pdf:
	quarto render report/report.qmd --to pdf

## Quick demo: synthetic data → analysis → dashboard
demo: synthetic analyse plot
	streamlit run dashboard/app.py

## Remove generated outputs (not raw data)
clean:
	rm -rf outputs/figures/* outputs/tables/*
	rm -f data/processed/oor_for_r.csv data/processed/metadata.json

## Remove everything including raw data (careful!)
clean-all: clean
	rm -rf data/raw/chirps/*.nc
