# 04_trend_analysis.R
# --------------------
# Fits linear trends and Mann-Kendall tests to OOR data per district.
# Outputs trend tables and district-level stats for mapping.
#
# Packages: tidyverse, trend, Kendall, sf, writexl
#
# Usage:
#   Rscript scripts/r/04_trend_analysis.R
#   OR source("scripts/r/04_trend_analysis.R") from RStudio

suppressPackageStartupMessages({
  library(tidyverse)
  library(trend)       # sens.slope, mk.test
  library(Kendall)     # MannKendall
  library(broom)       # tidy() for lm results
})

# ── Paths ────────────────────────────────────────────────────────────────────
oor_path    <- "data/processed/oor_for_r.csv"
out_trends  <- "outputs/tables/district_trends.csv"
out_summary <- "outputs/tables/regional_summary.csv"
out_decades <- "outputs/tables/decade_means.csv"
dir.create("outputs/tables", recursive = TRUE, showWarnings = FALSE)

# ── Load data ─────────────────────────────────────────────────────────────────
cat("\nLoading OOR data...\n")
df <- read_csv(oor_path, show_col_types = FALSE) %>%
  filter(!is.na(oor_doy)) %>%
  mutate(
    t = season_start - min(season_start),  # years since 1990
    region = factor(region, levels = c("Northern", "Central", "Southern"))
  )

cat(sprintf("  %d records, %d districts, %d seasons\n",
    nrow(df), n_distinct(df$district), n_distinct(df$season_start)))

# ── Per-district trend analysis ───────────────────────────────────────────────
cat("\nRunning per-district Mann-Kendall + Sen's slope...\n")

district_trends <- df %>%
  group_by(district, region) %>%
  arrange(season_start) %>%
  summarise(
    n_seasons       = n(),
    mean_oor_doy    = round(mean(oor_doy), 1),
    sd_oor_doy      = round(sd(oor_doy), 1),
    first_decade_mean = round(mean(oor_doy[season_start < 2000], na.rm = TRUE), 1),
    last_decade_mean  = round(mean(oor_doy[season_start >= 2010], na.rm = TRUE), 1),

    # Linear regression slope (days per year)
    lm_slope = {
      m <- lm(oor_doy ~ season_start)
      round(coef(m)[2], 3)
    },
    lm_p_value = {
      m <- lm(oor_doy ~ season_start)
      round(summary(m)$coefficients[2, 4], 4)
    },
    lm_r2 = {
      m <- lm(oor_doy ~ season_start)
      round(summary(m)$r.squared, 3)
    },

    # Sen's slope (robust, non-parametric)
    sens_slope_days_per_year = {
      ts_data <- ts(oor_doy, start = min(season_start))
      round(sens.slope(ts_data)$estimates, 3)
    },

    # Mann-Kendall p-value
    mk_p_value = {
      ts_data <- ts(oor_doy, start = min(season_start))
      round(mk.test(ts_data)$p.value, 4)
    },
    mk_tau = {
      ts_data <- ts(oor_doy, start = min(season_start))
      round(mk.test(ts_data)$statistic, 3)
    },

    .groups = "drop"
  ) %>%
  mutate(
    # Shift over the full study period (days per decade)
    total_shift_days      = round(sens_slope_days_per_year * 34, 1),
    shift_per_decade      = round(sens_slope_days_per_year * 10, 1),
    significant_mk        = mk_p_value < 0.05,
    significant_lm        = lm_p_value < 0.05,
    trend_direction       = case_when(
      sens_slope_days_per_year > 0 ~ "Delayed (later onset)",
      sens_slope_days_per_year < 0 ~ "Advanced (earlier onset)",
      TRUE ~ "No trend"
    ),
    # Convert mean DOY to approximate calendar date
    mean_oor_date = format(as.Date(mean_oor_doy - 1, origin = "2000-01-01"), "%b %d")
  )

write_csv(district_trends, out_trends)
cat(sprintf("  Saved: %s\n", out_trends))

# ── Regional summary ──────────────────────────────────────────────────────────
cat("\nBuilding regional summary...\n")

regional_summary <- district_trends %>%
  group_by(region) %>%
  summarise(
    n_districts            = n(),
    mean_oor_doy           = round(mean(mean_oor_doy), 1),
    mean_shift_per_decade  = round(mean(shift_per_decade), 2),
    mean_total_shift       = round(mean(total_shift_days), 1),
    pct_significant        = round(mean(significant_mk) * 100, 1),
    districts_delayed      = sum(sens_slope_days_per_year > 0),
    districts_advanced     = sum(sens_slope_days_per_year < 0),
    .groups = "drop"
  )

write_csv(regional_summary, out_summary)
cat(sprintf("  Saved: %s\n", out_summary))
print(regional_summary)

# ── Decade means ──────────────────────────────────────────────────────────────
decade_means <- df %>%
  mutate(decade = paste0(floor(season_start / 10) * 10, "s")) %>%
  group_by(region, decade) %>%
  summarise(
    mean_oor = round(mean(oor_doy, na.rm = TRUE), 1),
    se_oor   = round(sd(oor_doy, na.rm = TRUE) / sqrt(n()), 2),
    n        = n(),
    .groups  = "drop"
  )

write_csv(decade_means, out_decades)
cat(sprintf("  Saved: %s\n", out_decades))

# ── Console summary ───────────────────────────────────────────────────────────
cat("\n── Key findings ─────────────────────────────────────────────\n")
n_sig <- sum(district_trends$significant_mk)
n_del <- sum(district_trends$sens_slope_days_per_year > 0 & district_trends$significant_mk)
n_adv <- sum(district_trends$sens_slope_days_per_year < 0 & district_trends$significant_mk)

cat(sprintf("  Significant trends (p < 0.05): %d / %d districts\n",
    n_sig, nrow(district_trends)))
cat(sprintf("  Delayed onset (later planting):   %d districts\n", n_del))
cat(sprintf("  Advanced onset (earlier planting): %d districts\n", n_adv))

most_affected <- district_trends %>%
  filter(significant_mk) %>%
  slice_max(abs(total_shift_days), n = 5)

cat("\n  Top 5 most-shifted districts:\n")
most_affected %>%
  select(district, region, mean_oor_date, total_shift_days, mk_p_value) %>%
  print()

cat("\nTrend analysis complete.\n")
