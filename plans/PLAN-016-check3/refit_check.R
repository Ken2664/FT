# PLAN-016 check 3: does restarting a glmer fit from its own estimates clear
# lme4's convergence warning? (ADR-059 decision 1 bets that it sometimes does.)
#
# For every synthetic table written by gen_frames.py this script
#   1. fits the two nested models of Documents/05_STATISTICS.md section 3.2,
#   2. refits EACH of them once from start = getME(fit, c("theta","fixef")),
#   3. records, for both stages: wall clock, logLik, conv$opt, lme4's own
#      messages, isSingular(), max|grad|, the fixed effects and their SEs.
#
# Every fit is refit, not only the warned ones. The unwarned fits are the
# control: they say how far a fit that nobody doubts moves on a restart, which
# is what the "does not move substantially" threshold of ADR-059 has to clear.
# The cost of the POLICY (refit only the warned ones) is recovered in
# summarize.py from the per-fit timings.
#
# usage: Rscript refit_check.R <libpath|""> <out_dir> <csv> [<csv> ...]
#
# This is NOT pipeline code. code/analysis/primary.py is written separately
# (PLAN-016 section 7-5); this file measures one unverified premise only.

args <- commandArgs(trailingOnly = TRUE)
libpath <- args[1]
out_dir <- args[2]
csv_paths <- args[-(1:2)]
if (nzchar(libpath)) .libPaths(c(libpath, .libPaths()))

suppressPackageStartupMessages(library(lme4))

F_FULL <- is_rule ~ task * coverage + (1 | seed) + (1 | item) + (1 | template)
F_ADD <- is_rule ~ task + coverage + (1 | seed) + (1 | item) + (1 | template)

# ---- JSON writing -----------------------------------------------------------
# Hand rolled so the check has no package dependency beyond lme4. Check 2's
# JSONs embedded raw newlines inside strings and were not legal JSON; every
# string here is whitespace collapsed, and the file is written on a binary
# connection so the line endings are LF on Windows too.

jstr <- function(x) {
  x <- gsub("\\\\", "/", as.character(x))
  x <- gsub("\"", "'", x)
  paste0("\"", gsub("[[:space:]]+", " ", x), "\"")
}
jnum1 <- function(x, fmt = "%.10g") {
  if (length(x) != 1 || is.na(x) || !is.finite(x)) "null" else sprintf(fmt, x)
}
jarr <- function(v, fmt = "%.10g") {
  if (length(v) == 0) return("[]")
  paste0("[", paste(vapply(v, jnum1, "", fmt = fmt), collapse = ", "), "]")
}
jsarr <- function(v) {
  if (length(v) == 0) return("[]")
  paste0("[", paste(vapply(v, jstr, ""), collapse = ", "), "]")
}
jbool <- function(x) if (isTRUE(x)) "true" else "false"
kv <- function(key, val) paste0("  ", jstr(key), ": ", val)

write_json <- function(fields, path) {
  body <- paste(fields, collapse = ",\n")
  txt <- paste0("{\n", body, "\n}\n")
  con <- file(path, "wb")
  writeBin(charToRaw(txt), con)
  close(con)
}

# ---- what we record about one fit -------------------------------------------

# lme4's own text is "Model failed to converge with max|grad| = 0.0163 (tol = ...)".
maxgrad_from_msg <- function(msgs) {
  hit <- regmatches(msgs, regexpr("max\\|grad\\| = [0-9.eE+-]+", msgs))
  if (length(hit) == 0) return(NA_real_)
  suppressWarnings(as.numeric(sub("max\\|grad\\| = ", "", hit)))
}

# lme4 checks the SCALED gradient, solve(Hessian, gradient); the raw gradient is
# recorded next to it so the two are never confused.
relgrad_of <- function(fit) {
  tryCatch({
    dd <- fit@optinfo$derivs
    max(abs(solve(dd$Hessian, dd$gradient)))
  }, error = function(e) NA_real_)
}

describe <- function(prefix, fit, secs) {
  m <- fit@optinfo$conv$lme4$messages
  msgs <- if (is.null(m)) "" else paste(m, collapse = " | ")
  n_msgs <- if (is.null(m)) 0L else length(m)
  co <- summary(fit)$coefficients
  raw_grad <- tryCatch(max(abs(fit@optinfo$derivs$gradient)), error = function(e) NA_real_)
  p <- function(k) paste0(prefix, "_", k)
  c(
    kv(p("secs"), jnum1(secs)),
    kv(p("logLik"), jnum1(as.numeric(logLik(fit)), "%.14g")),
    kv(p("df_model"), jnum1(attr(logLik(fit), "df"))),
    kv(p("conv_opt"), jnum1(fit@optinfo$conv$opt)),
    kv(p("n_msgs"), jnum1(n_msgs)),
    kv(p("warned"), jbool(n_msgs > 0)),
    kv(p("msgs"), jstr(msgs)),
    kv(p("singular"), jbool(isSingular(fit))),
    kv(p("has_maxgrad"), jbool(grepl("max|grad|", msgs, fixed = TRUE))),
    kv(p("maxgrad_msg"), jnum1(maxgrad_from_msg(msgs))),
    kv(p("maxgrad_raw"), jnum1(raw_grad)),
    kv(p("relgrad"), jnum1(relgrad_of(fit))),
    kv(p("fixef"), jarr(as.numeric(fixef(fit)), "%.14g")),
    kv(p("se"), jarr(as.numeric(co[, "Std. Error"]), "%.14g")),
    kv(p("theta"), jarr(as.numeric(getME(fit, "theta")), "%.14g"))
  )
}

# ---- one table --------------------------------------------------------------

run_one <- function(csv_path, out_path) {
  d <- read.csv(csv_path, stringsAsFactors = TRUE)
  d$coverage <- relevel(d$coverage, ref = "id")  # section 3.2: id is the base level

  fields <- c(
    kv("csv", jstr(basename(csv_path))),
    kv("n_rows", jnum1(nrow(d))),
    kv("n_seed", jnum1(nlevels(d$seed))),
    kv("n_item", jnum1(nlevels(d$item))),
    kv("n_template", jnum1(nlevels(d$template))),
    kv("r_version", jstr(R.version.string)),
    kv("lme4_version", jstr(as.character(packageVersion("lme4"))))
  )

  fits0 <- list()
  for (nm in c("full", "add")) {
    form <- if (nm == "full") F_FULL else F_ADD

    t0 <- proc.time()[["elapsed"]]
    fit0 <- glmer(form, family = binomial, data = d)
    t1 <- proc.time()[["elapsed"]]

    # ADR-059 decision 1: restart from this fit's own estimates, exactly once.
    st <- getME(fit0, c("theta", "fixef"))
    t2 <- proc.time()[["elapsed"]]
    fit1 <- glmer(form, family = binomial, data = d, start = st)
    t3 <- proc.time()[["elapsed"]]

    fits0[[nm]] <- fit0
    fields <- c(
      fields,
      kv(paste0(nm, "_fixef_names"), jsarr(names(fixef(fit0)))),
      kv(paste0(nm, "_theta_names"), jsarr(names(getME(fit0, "theta")))),
      describe(paste0(nm, "_fit0"), fit0, t1 - t0),
      describe(paste0(nm, "_refit"), fit1, t3 - t2)
    )
    cat(sprintf("  %-4s fit0=%.1fs warn=%d sing=%d | refit=%.1fs warn=%d sing=%d\n",
                nm, t1 - t0, length(fit0@optinfo$conv$lme4$messages), isSingular(fit0),
                t3 - t2, length(fit1@optinfo$conv$lme4$messages), isSingular(fit1)))
  }

  an <- anova(fits0[["add"]], fits0[["full"]], test = "LRT")
  fields <- c(
    fields,
    kv("chisq_orig", jnum1(an[["Chisq"]][2], "%.10g")),
    kv("df_orig", jnum1(an[["Df"]][2])),
    kv("p_orig", jnum1(an[["Pr(>Chisq)"]][2], "%.10g"))
  )
  write_json(fields, out_path)
}

# ---- driver -----------------------------------------------------------------

for (csv_path in csv_paths) {
  base <- sub("^frame_", "refit_", sub("[.]csv$", ".json", basename(csv_path)))
  out_path <- file.path(out_dir, base)
  if (file.exists(out_path)) {
    cat(base, "exists, skipping\n")
    next
  }
  cat(basename(csv_path), "\n")
  t0 <- proc.time()[["elapsed"]]
  run_one(csv_path, out_path)
  cat(sprintf("  -> %s (%.1fs)\n", base, proc.time()[["elapsed"]] - t0))
}
cat("done\n")
