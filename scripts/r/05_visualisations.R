# 05_visualisations.R
# --------------------
# Generates all publication-quality figures using ggplot2.
# Saves to outputs/figures/
#
# Figures produced:
#   fig1_oor_timeseries.png  — regional OOR trend over time
#   fig2_shift_map.png       — choropleth of total shift per district
#   fig3_decade_boxplot.png  — OOR distribution by decade
#   fig4_significance.png    — district significance scatter
#   fig5_enso_overlay.png    — OOR anomaly with ENSO events

suppressPackageStartupMessages({
  library(tidyverse)
  library(sf)
  library(patchwork)    # combine plots
  library(scales)
  library(ggrepel)
})

dir.create("outputs/figures", recursive = TRUE, showWarnings = FALSE)

# ── Theme ─────────────────────────────────────────────────────────────────────
theme_crop <- function() {
  theme_minimal(base_family = "sans", base_size = 11) +
    theme(
      plot.title      = element_text(size = 13, face = "bold", margin = margin(b = 4)),
      plot.subtitle   = element_text(size = 10, color = "grey45", margin = margin(b = 12)),
      plot.caption    = element_text(size = 8, color = "grey60", hjust = 0),
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(color = "grey92"),
      legend.position = "bottom",
      strip.text      = element_text(face = "bold", size = 10),
      plot.background = element_rect(fill = "white", color = NA)
    )
}

region_colors <- c("Southern" = "#D85A30", "Central" = "#378ADD", "Northern" = "#1D9E75")
ENSO_el_nino  <- c(1991, 1994, 1997, 2002, 2004, 2009, 2015, 2018, 2023)
ENSO_la_nina  <- c(1995, 1998, 1999, 2000, 2007, 2010, 2011, 2020, 2021)

# ── Load data ─────────────────────────────────────────────────────────────────
df     <- read_csv("data/processed/oor_for_r.csv", show_col_types = FALSE)
trends <- read_csv("outputs/tables/district_trends.csv", show_col_types = FALSE)

# ── Fig 1: OOR timeseries by region ──────────────────────────────────────────
cat("Plotting Fig 1: Regional OOR timeseries...\n")

regional_ts <- df %>%
  filter(!is.na(oor_doy)) %>%
  group_by(region, season_start) %>%
  summarise(mean_oor = mean(oor_doy), se = sd(oor_doy)/sqrt(n()), .groups = "drop")

p1 <- ggplot(regional_ts, aes(season_start, mean_oor, color = region, fill = region)) +
  # ENSO shading
  annotate("rect",
    xmin = ENSO_el_nino - 0.4, xmax = ENSO_el_nino + 0.4,
    ymin = -Inf, ymax = Inf, alpha = 0.12, fill = "#E24B4A") +
  annotate("rect",
    xmin = ENSO_la_nina - 0.4, xmax = ENSO_la_nina + 0.4,
    ymin = -Inf, ymax = Inf, alpha = 0.12, fill = "#378ADD") +
  geom_ribbon(aes(ymin = mean_oor - se, ymax = mean_oor + se), alpha = 0.15, color = NA) +
  geom_line(linewidth = 0.9) +
  geom_point(size = 1.8, alpha = 0.7) +
  geom_smooth(method = "lm", se = FALSE, linetype = "dashed", linewidth = 0.6, alpha = 0.8) +
  scale_color_manual(values = region_colors) +
  scale_fill_manual(values = region_colors) +
  scale_x_continuous(breaks = seq(1990, 2024, 5)) +
  scale_y_continuous(
    name = "Onset of rains (day of year)",
    sec.axis = sec_axis(~ as.Date(. - 1, origin = "2000-01-01"),
                        name = "Approx. calendar date",
                        labels = function(x) format(x, "%b %d"))
  ) +
  labs(
    title    = "Onset of rains in Malawi: 1990–2024",
    subtitle = "Dashed lines = linear trend. Red bands = El Niño years, blue = La Niña years.",
    x        = "Season start year",
    color    = "Region", fill = "Region",
    caption  = "Data: CHIRPS v2.0 | OOR definition: FAO/FEWS NET"
  ) +
  theme_crop()

ggsave("outputs/figures/fig1_oor_timeseries.png", p1, width = 10, height = 5.5, dpi = 150)
cat("  Saved: fig1_oor_timeseries.png\n")

# ── Fig 2: Choropleth map of total shift ─────────────────────────────────────
cat("Plotting Fig 2: Shift magnitude map...\n")

gadm_path <- "data/raw/gadm_malawi_districts.geojson"
if (file.exists(gadm_path)) {
  malawi <- st_read(gadm_path, quiet = TRUE) %>%
    rename(district = NAME_2) %>%
    select(district, geometry) %>%
    left_join(trends %>% select(district, total_shift_days, significant_mk, region), by = "district")

  p2 <- ggplot(malawi) +
    geom_sf(aes(fill = total_shift_days), color = "white", linewidth = 0.3) +
    geom_sf(data = filter(malawi, significant_mk),
            fill = NA, color = "black", linewidth = 0.7, linetype = "solid") +
    scale_fill_gradient2(
      low = "#185FA5", mid = "white", high = "#993C1D",
      midpoint = 0,
      name = "Total shift\n(days, 1990–2024)",
      labels = function(x) paste0(ifelse(x > 0, "+", ""), x)
    ) +
    labs(
      title    = "Shift in onset-of-rains: 1990–2024",
      subtitle = "Positive = delayed onset (later planting)\nBold outline = statistically significant (MK p < 0.05)",
      caption  = "Data: CHIRPS v2.0"
    ) +
    theme_void(base_family = "sans") +
    theme(
      plot.title    = element_text(size = 13, face = "bold"),
      plot.subtitle = element_text(size = 9, color = "grey45"),
      legend.position = "right"
    )

  ggsave("outputs/figures/fig2_shift_map.png", p2, width = 6, height = 8, dpi = 150)
  cat("  Saved: fig2_shift_map.png\n")
} else {
  cat("  [skip] fig2 — GADM shapefile not downloaded yet\n")
}

# ── Fig 3: Decade boxplot ─────────────────────────────────────────────────────
cat("Plotting Fig 3: Decade boxplot...\n")

df_decade <- df %>%
  filter(!is.na(oor_doy)) %>%
  mutate(decade = paste0(floor(season_start / 10) * 10, "s"),
         decade = factor(decade, levels = c("1990s","2000s","2010s","2020s")))

p3 <- ggplot(df_decade, aes(decade, oor_doy, fill = region)) +
  geom_boxplot(alpha = 0.7, outlier.size = 0.8, linewidth = 0.4) +
  facet_wrap(~region, ncol = 3) +
  scale_fill_manual(values = region_colors, guide = "none") +
  scale_y_continuous(
    breaks = seq(305, 360, 10),
    labels = function(x) {
      d <- as.Date(x - 1, origin = "2000-01-01")
      paste0(x, "\n(", format(d, "%b %d"), ")")
    }
  ) +
  labs(
    title    = "Distribution of onset-of-rains by decade",
    subtitle = "Has the planting window shifted across decades?",
    x        = "Decade", y = "Day of year",
    caption  = "Data: CHIRPS v2.0"
  ) +
  theme_crop()

ggsave("outputs/figures/fig3_decade_boxplot.png", p3, width = 10, height = 5, dpi = 150)
cat("  Saved: fig3_decade_boxplot.png\n")

# ── Fig 4: Significance scatter ───────────────────────────────────────────────
cat("Plotting Fig 4: Significance scatter...\n")

p4 <- ggplot(trends, aes(mean_oor_doy, shift_per_decade,
                          color = region, size = n_seasons,
                          alpha = significant_mk)) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "grey60") +
  geom_point() +
  geom_text_repel(aes(label = district), size = 2.8, max.overlaps = 12,
                  show.legend = FALSE) +
  scale_color_manual(values = region_colors) +
  scale_alpha_manual(values = c("TRUE" = 1, "FALSE" = 0.35),
                     labels = c("TRUE" = "Significant (p<0.05)", "FALSE" = "Not significant"),
                     name = "") +
  scale_size_continuous(range = c(2, 6), guide = "none") +
  labs(
    title    = "Onset-of-rains shift per decade by district",
    subtitle = "Districts above zero line show delayed planting onset",
    x        = "Mean OOR (day of year, 1990–2024)",
    y        = "Shift per decade (days)",
    color    = "Region",
    caption  = "Data: CHIRPS v2.0 | Trend: Sen's slope"
  ) +
  theme_crop()

ggsave("outputs/figures/fig4_significance_scatter.png", p4, width = 10, height = 6, dpi = 150)
cat("  Saved: fig4_significance_scatter.png\n")

# ── Fig 5: National anomaly + ENSO overlay ────────────────────────────────────
cat("Plotting Fig 5: National anomaly + ENSO...\n")

national_ts <- df %>%
  filter(!is.na(oor_doy)) %>%
  group_by(season_start) %>%
  summarise(mean_oor = mean(oor_doy), .groups = "drop") %>%
  mutate(
    baseline = mean(mean_oor[season_start %in% 1990:2009]),
    anomaly  = mean_oor - baseline,
    enso     = case_when(
      season_start %in% ENSO_el_nino ~ "El Niño",
      season_start %in% ENSO_la_nina ~ "La Niña",
      TRUE ~ "Neutral"
    )
  )

p5 <- ggplot(national_ts, aes(season_start, anomaly)) +
  geom_col(aes(fill = enso), alpha = 0.85) +
  geom_smooth(method = "lm", se = TRUE, color = "black", linewidth = 0.8,
              fill = "grey80", alpha = 0.3) +
  geom_hline(yintercept = 0, linewidth = 0.5) +
  scale_fill_manual(
    values = c("El Niño" = "#D85A30", "La Niña" = "#185FA5", "Neutral" = "#888780"),
    name = "ENSO phase"
  ) +
  scale_x_continuous(breaks = seq(1990, 2024, 5)) +
  labs(
    title    = "National OOR anomaly relative to 1990–2009 baseline",
    subtitle = "Positive anomaly = later onset than baseline average",
    x        = "Season start year",
    y        = "OOR anomaly (days)",
    caption  = "Data: CHIRPS v2.0 | Baseline: 1990–2009 mean"
  ) +
  theme_crop()

ggsave("outputs/figures/fig5_enso_anomaly.png", p5, width = 10, height = 4.5, dpi = 150)
cat("  Saved: fig5_enso_anomaly.png\n")

cat("\nAll figures saved to outputs/figures/\n")
