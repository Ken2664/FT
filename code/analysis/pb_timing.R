# code/analysis/pb_timing.R — パラメトリック・ブートストラップ(PB)の費用の計時(PLAN-043 I9 / ADR-128 決定2 (B2) / ADR-129 決定6)。
#
# 答える問い: 「合成表 1 枚で、lme4 だけで書いた simulate -> refit(add の当てはめから応答を B 回引き、
# full・add を当て直す)は、1 回あたり何秒かかり、当て直しは何回失敗するか」
#
# **出すのは秒数と当て直しの失敗の数だけ。p 値も LRT の統計量も出力しない・判定に使わない**(ADR-129 決定6)。
# 縮退・allFit はしない。当て直しの式は、観測の当てはめが ADR-059 の判定で着いた段の式(ADR-129 決定6)。
# PB の中の失敗の扱い・PB の反復数・漸近 χ² と食い違ったときの扱いは S5(この計時では決めない)。
#
# power_sim_fit.R の「# ---- driver」より上(式・judge_one・JSON の部品)をそのまま評価して借りる
# (fit_failure_diagnosis.R と同じ。複写するとずれたときに計時が別の当てはめを測る)。
#
# 呼ばれ方(位置引数。code/analysis/pb_timing.py が組み立てる):
#   Rscript pb_timing.R <libpath|""> <manifest>
# manifest は平文(1 行 1 キー = 値)。`table=<csv>|<out.json>|<n_parallel>` の行が 1 表。出力が既にある表は飛ばす。

args <- commandArgs(trailingOnly = TRUE)
libpath <- args[1]
manifest_path <- args[2]
if (nzchar(libpath)) .libPaths(c(libpath, .libPaths()))

script_dir <- dirname(sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[1]))

DRIVER_MARKER <- "^# ---- driver"
fit_lines <- readLines(file.path(script_dir, "power_sim_fit.R"), warn = FALSE, encoding = "UTF-8")
marker_at <- grep(DRIVER_MARKER, fit_lines)
if (length(marker_at) != 1L) stop("power_sim_fit.R の driver の目印が 1 つに決まらない。計時は借りる範囲を決められない")
eval(parse(text = fit_lines[seq_len(marker_at - 1L)], encoding = "UTF-8"), envir = globalenv())
# ↑ judge_one / formula_at / non_singular_messages / jstr / jnum / jbool / kv / write_json / indicator_name / read_manifest が入る

# 答える問い: 縮退のどの段で、観測の当てはめは ADR-059 の判定を通ったか(床まで行って通らなければ床)。
# power_sim_fit.R の run_one の繰り返しと同じ。PB の当て直しの式はこの段の式にする。
settle_observed_fit <- function(d, cov_levels, loglik_tol, beta_tol, max_level) {
  level <- 0L
  repeat {
    res_full <- judge_one(formula_at(level, "task * coverage", cov_levels), d, loglik_tol, beta_tol)
    res_add <- judge_one(formula_at(level, "task + coverage", cov_levels), d, loglik_tol, beta_tol)
    if (!(res_full$failed || res_add$failed) || level >= max_level) break
    level <- level + 1L
  }
  list(level = level, full = res_full, add = res_add)
}

# power_sim_fit.R の `pick`(use_refit_for_lrt = true)と同じ。当て直したほうが最終の当てはめ。
final_fit <- function(res) if (res$refit_done) res$refit else res$fit0

# 答える問い: newresp で当て直した 1 本は、例外 / 非 singular の警告で失敗したか(秒数と失敗の数だけを返す)。
timed_refit <- function(fit, newresp) {
  t0 <- proc.time()[["elapsed"]]
  out <- tryCatch(suppressMessages(suppressWarnings(refit(fit, newresp))), error = function(e) e)
  seconds <- proc.time()[["elapsed"]] - t0
  errored <- inherits(out, "error")
  list(seconds = seconds, errored = errored,
       message = if (errored) conditionMessage(out) else "",
       nonsingular = if (errored) NA_integer_ else length(non_singular_messages(out)))
}

run_table <- function(job, loglik_tol, beta_tol, max_level, n_boot, sim_seed) {
  d <- read.csv(job$csv, stringsAsFactors = TRUE)
  d$coverage <- relevel(d$coverage, ref = "id")   # §3.2: id を基準(power_sim_fit.R と同じ)
  cov_levels <- levels(d$coverage)
  for (cl in cov_levels) d[[indicator_name(cl)]] <- as.numeric(d$coverage == cl)

  t0 <- proc.time()[["elapsed"]]
  settled <- suppressMessages(suppressWarnings(settle_observed_fit(d, cov_levels, loglik_tol, beta_tol, max_level)))
  observed_seconds <- proc.time()[["elapsed"]] - t0
  observed_failed <- settled$full$failed || settled$add$failed
  skipped <- settled$full$errored || settled$add$errored   # 床の土台が例外なら当てはめが無く、simulate できない

  base_fields <- c(
    kv("csv", jstr(basename(job$csv))),
    kv("r_version", jstr(R.version.string)),
    kv("lme4_version", jstr(as.character(packageVersion("lme4")))),
    kv("n_parallel", jnum(job$n_parallel)),
    kv("settled_level", jnum(settled$level)),
    kv("observed_fit_failed", jbool(observed_failed)),
    kv("observed_fit_seconds", jnum(observed_seconds, "%.3f")),
    kv("n_boot", jnum(n_boot)))
  if (skipped) {
    write_json(c(base_fields, kv("skipped", jbool(TRUE)),
                 kv("skipped_reason", jstr("the observed fit errored at the settled level: nothing to simulate from"))),
               job$out)
    return(invisible(NULL))
  }

  fit_add <- final_fit(settled$add)
  fit_full <- final_fit(settled$full)
  t1 <- proc.time()[["elapsed"]]
  sims <- simulate(fit_add, nsim = n_boot, seed = sim_seed)
  simulate_seconds <- proc.time()[["elapsed"]] - t1

  per_sim <- numeric(n_boot)
  err_full <- err_add <- ns_full <- ns_add <- 0L
  first_error <- ""
  for (i in seq_len(n_boot)) {
    ti <- proc.time()[["elapsed"]]
    r_add <- timed_refit(fit_add, sims[[i]])
    r_full <- timed_refit(fit_full, sims[[i]])
    per_sim[i] <- proc.time()[["elapsed"]] - ti
    for (r in list(r_add, r_full)) if (r$errored && !nzchar(first_error)) first_error <- r$message
    err_add <- err_add + as.integer(r_add$errored)
    err_full <- err_full + as.integer(r_full$errored)
    ns_add <- ns_add + as.integer(!r_add$errored && r_add$nonsingular > 0L)
    ns_full <- ns_full + as.integer(!r_full$errored && r_full$nonsingular > 0L)
  }

  fields <- c(base_fields,
    kv("skipped", jbool(FALSE)),
    kv("simulate_seconds", jnum(simulate_seconds, "%.3f")),
    kv("refit_seconds_total", jnum(sum(per_sim), "%.3f")),
    kv("refit_seconds_each", paste0("[", paste(vapply(per_sim, jnum, character(1), fmt = "%.3f"), collapse = ", "), "]")),
    kv("refit_error_add", jnum(err_add)), kv("refit_error_full", jnum(err_full)),
    kv("refit_nonsingular_warning_add", jnum(ns_add)), kv("refit_nonsingular_warning_full", jnum(ns_full)),
    kv("first_refit_error", jstr(first_error)))
  write_json(fields, job$out)
}

# ---- driver ----------------------------------------------------------------------

lines <- readLines(manifest_path, warn = FALSE)
lines <- lines[nzchar(trimws(lines))]
man <- read_manifest(lines)
loglik_tol <- as.numeric(man$loglik_tolerance)
beta_tol <- as.numeric(man$beta_move_tolerance)
max_level <- as.integer(man$max_reduction_level)
n_boot <- as.integer(man$n_boot)
sim_seed <- as.integer(man$simulate_seed)
for (v in list(loglik_tol, beta_tol, max_level, n_boot, sim_seed)) {
  if (length(v) != 1L || is.na(v)) stop("manifest の数値が足りない(loglik_tolerance / beta_move_tolerance / max_reduction_level / n_boot / simulate_seed)")
}

for (job_text in vals_for(lines, "table")) {
  p <- trimws(strsplit(job_text, "|", fixed = TRUE)[[1]])
  job <- list(csv = p[1], out = p[2], n_parallel = as.integer(p[3]))
  if (file.exists(job$out)) {
    cat(sprintf("%s exists, skipping\n", basename(job$out)))
    next
  }
  t0 <- proc.time()[["elapsed"]]
  run_table(job, loglik_tol, beta_tol, max_level, n_boot, sim_seed)
  cat(sprintf("%s -> %s (%.1fs)\n", basename(job$csv), basename(job$out), proc.time()[["elapsed"]] - t0))
}
cat("done\n")
