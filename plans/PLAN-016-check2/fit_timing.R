# PLAN-016 check 2, part 2: how long is one glmer fit (R6)?
#
# Fits the two nested models of Documents/05_STATISTICS.md section 3.2 to the
# synthetic table written by gen_frame.py, times each fit, and runs the LRT.
# Writes a JSON with the wall clock and the test statistic.
#
# usage: Rscript fit_timing.R <csv> <out.json> [libpath]
#
# This is NOT pipeline code. code/analysis/primary.py is written after D-1,
# which ADR-058 has now settled; this file exists to measure R6 only.

args <- commandArgs(trailingOnly = TRUE)
csv_path <- args[1]
out_path <- args[2]
if (length(args) >= 3 && nzchar(args[3])) .libPaths(c(args[3], .libPaths()))

suppressPackageStartupMessages(library(lme4))

d <- read.csv(csv_path, stringsAsFactors = TRUE)
d$coverage <- relevel(d$coverage, ref = "id")   # section 3.2: id is the base level

f_full <- is_rule ~ task * coverage + (1 | seed) + (1 | item) + (1 | template)
f_add  <- is_rule ~ task + coverage + (1 | seed) + (1 | item) + (1 | template)

t0 <- proc.time()[["elapsed"]]
fit_full <- glmer(f_full, family = binomial, data = d)
t1 <- proc.time()[["elapsed"]]
fit_add <- glmer(f_add, family = binomial, data = d)
t2 <- proc.time()[["elapsed"]]
an <- anova(fit_add, fit_full, test = "LRT")
t3 <- proc.time()[["elapsed"]]

# R5: is convergence machine-readable? optinfo$conv$opt is 0 when the optimiser
# reported success; $conv$lme4$messages carries lme4's own warnings.
conv_code <- function(f) f@optinfo$conv$opt
conv_msgs <- function(f) {
  m <- f@optinfo$conv$lme4$messages
  if (is.null(m)) "" else paste(m, collapse = " | ")
}

# lme4 messages are multi-line; a raw newline inside a JSON string is not legal JSON.
jstr <- function(x) paste0("\"", gsub("[[:space:]]+", " ", gsub("\"", "'", x)), "\"")

lines <- c(
  "{",
  paste0("  \"csv\": ", jstr(basename(csv_path)), ","),
  paste0("  \"n_rows\": ", nrow(d), ","),
  paste0("  \"n_seed\": ", nlevels(d$seed), ","),
  paste0("  \"n_item\": ", nlevels(d$item), ","),
  paste0("  \"n_template\": ", nlevels(d$template), ","),
  paste0("  \"secs_fit_full\": ", round(t1 - t0, 3), ","),
  paste0("  \"secs_fit_add\": ", round(t2 - t1, 3), ","),
  paste0("  \"secs_anova\": ", round(t3 - t2, 3), ","),
  paste0("  \"secs_total\": ", round(t3 - t0, 3), ","),
  paste0("  \"logLik_full\": ", round(as.numeric(logLik(fit_full)), 4), ","),
  paste0("  \"logLik_add\": ", round(as.numeric(logLik(fit_add)), 4), ","),
  paste0("  \"chisq\": ", round(an[["Chisq"]][2], 4), ","),
  paste0("  \"df\": ", an[["Df"]][2], ","),
  paste0("  \"p_value\": ", signif(an[["Pr(>Chisq)"]][2], 5), ","),
  paste0("  \"conv_code_full\": ", conv_code(fit_full), ","),
  paste0("  \"conv_code_add\": ", conv_code(fit_add), ","),
  paste0("  \"conv_msgs_full\": ", jstr(conv_msgs(fit_full)), ","),
  paste0("  \"conv_msgs_add\": ", jstr(conv_msgs(fit_add)), ","),
  paste0("  \"r_version\": ", jstr(R.version.string), ","),
  paste0("  \"lme4_version\": ", jstr(as.character(packageVersion("lme4")))),
  "}"
)
writeLines(lines, out_path)

cat(sprintf(
  "rows=%d items=%d full=%.2fs add=%.2fs total=%.2fs chisq=%.3f df=%d p=%.4g conv=%d/%d\n",
  nrow(d), nlevels(d$item), t1 - t0, t2 - t1, t3 - t0,
  an[["Chisq"]][2], an[["Df"]][2], an[["Pr(>Chisq)"]][2],
  conv_code(fit_full), conv_code(fit_add)
))
