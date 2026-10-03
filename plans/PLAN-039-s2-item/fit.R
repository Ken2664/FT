# PLAN-039 §4.1 (ADR-120): s2_item をパイロット FT の p2 2 シードから推定する。
# 答える問い: 「extrap_magnitude の T1・T2 で、同じ項目は 2 シードの間でどれだけそろうか
#              (項目の切片の分散、ロジット尺度)」
# 使い方: Rscript fit.R <frame.csv> <fits.csv>
# 式は ADR-120 決定2 のまま。seed は固定効果(2 水準では分散を推定できない)。
suppressPackageStartupMessages(library(lme4))

args <- commandArgs(trailingOnly = TRUE)
frame <- read.csv(args[1], stringsAsFactors = FALSE)
frame <- frame[frame$coverage == "extrap_magnitude", ]
frame$seed <- factor(frame$seed)
frame$task <- factor(frame$task)

MODELS <- list(
  main    = list(tasks = c("t1", "t2"), f = is_rule ~ task * seed + (1 | item) + (1 | template)),
  no_tmpl = list(tasks = c("t1", "t2"), f = is_rule ~ task * seed + (1 | item)),
  t1_only = list(tasks = c("t1"),       f = is_rule ~ seed + (1 | item)),
  t2_only = list(tasks = c("t2"),       f = is_rule ~ seed + (1 | item) + (1 | template))
)

fit_one <- function(d, f) {
  warns <- character(0)
  fit <- withCallingHandlers(
    glmer(f, data = d, family = binomial),
    warning = function(w) { warns <<- c(warns, conditionMessage(w)); invokeRestart("muffleWarning") }
  )
  conv <- fit@optinfo$conv$lme4$messages
  vc <- as.data.frame(VarCorr(fit))
  var_of <- function(g) { v <- vc$vcov[vc$grp == g]; if (length(v)) v else NA_real_ }
  ci_lo <- NA_real_; ci_hi <- NA_real_; status <- "ok"; pwarns <- character(0)
  ci <- tryCatch(
    withCallingHandlers(
      confint(fit, parm = "theta_", method = "profile", oldNames = FALSE),
      warning = function(w) { pwarns <<- c(pwarns, conditionMessage(w)); invokeRestart("muffleWarning") }
    ),
    error = function(e) { status <<- paste("error:", conditionMessage(e)); NULL }
  )
  if (!is.null(ci)) {
    row <- grep("\\|item$", rownames(ci))
    if (length(row) == 1) {
      ci_lo <- ci[row, 1]^2; ci_hi <- ci[row, 2]^2
      if (!is.finite(ci_hi)) status <- "upper_not_finite"
    } else status <- "item_row_missing"
  }
  data.frame(
    n_obs = nrow(d), n_item = length(unique(d$item)),
    var_item = var_of("item"), var_tmpl = var_of("template"),
    singular = isSingular(fit),
    fit_warnings = paste(unique(c(warns, conv)), collapse = " | "),
    ci_lo_var_item = ci_lo, ci_hi_var_item = ci_hi,
    profile_status = status, profile_warnings = paste(unique(pwarns), collapse = " | "),
    stringsAsFactors = FALSE
  )
}

out <- list()
for (step in sort(unique(frame$step), decreasing = TRUE)) {
  for (name in names(MODELS)) {
    m <- MODELS[[name]]
    d <- frame[frame$step == step & frame$task %in% m$tasks, ]
    d$task <- droplevels(d$task)
    r <- fit_one(d, m$f)
    out[[length(out) + 1]] <- cbind(data.frame(step = step, model = name), r)
  }
}
write.csv(do.call(rbind, out), args[2], row.names = FALSE)
