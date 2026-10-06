# code/analysis/fit_failure_diagnosis.R — PLAN-042 D0〜D4 の当てはめ側(診断専用)。
#
# 答える問い: 「run2 で『当てはめ失敗』と数えた反復の床の当てはめは、(a) 再現するか(D0)、
# (b) 別の最適化で収束するか(D1)、(c) LRT を出すとどうなるか(D2)、
# (d) どの係数が動いたか・そのセルは分離していたか(D3)、(e) 新しい項の分散は 0 に張り付くか(D4)」
#
# **power_sim_fit.R の本体は変えない。**当てはめの定義(縮退の式・judge_one・ADR-059 の許容)は、
# そのファイルの「# ---- driver」より上をそのまま評価して借りる(複写するとずれたときに診断が別物になる)。
# 規則(ADR-059・ADR-124 D2')は変えない。ここは記録だけで、「失敗」「支える」の判定は python 側(fit_failure_diagnosis.py)。
#
# 呼ばれ方(位置引数。power_sim_fit.R と同じ 2 つ):
#   Rscript fit_failure_diagnosis.R <libpath|""> <manifest>
# manifest は平文(1 行 1 キー = 値)。`case=` の行が 1 反復 = 1 行(区切りは |):
#   case=<csv>|<out.json>|<check_level>|<full_logLik|NA>|<add_logLik|NA>|<fit_failed true|false>|<case_id>
# 出力が既にある反復は飛ばす(途中で落ちても再開できる)。D0 が合わなければ**止まる**(CLAUDE.md §7)。

args <- commandArgs(trailingOnly = TRUE)
libpath <- args[1]
manifest_path <- args[2]
if (nzchar(libpath)) .libPaths(c(libpath, .libPaths()))

script_dir <- dirname(sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[1]))

# ---- power_sim_fit.R の定義を借りる(driver より上だけ)---------------------------------
DRIVER_MARKER <- "^# ---- driver"
fit_lines <- readLines(file.path(script_dir, "power_sim_fit.R"), warn = FALSE, encoding = "UTF-8")
marker_at <- grep(DRIVER_MARKER, fit_lines)
if (length(marker_at) != 1L) stop("power_sim_fit.R の driver の目印が 1 つに決まらない。診断は借りる範囲を決められない")
eval(parse(text = fit_lines[seq_len(marker_at - 1L)], encoding = "UTF-8"), envir = globalenv())
# ↑ judge_one / formula_at / non_singular_messages / jstr / jnum / jbool / kv / write_json / indicator_name が入る

NEW_TERM_GROUP <- "seed:task:coverage"
FIXED_FULL <- "task * coverage"
FIXED_ADD <- "task + coverage"

# ---- manifest ---------------------------------------------------------------

# 答える問い: manifest の `case=` の行 1 つは、どの反復を何として当てるか。
parse_case <- function(job) {
  p <- trimws(strsplit(job, "|", fixed = TRUE)[[1]])
  na_num <- function(x) if (identical(x, "NA")) NA_real_ else as.numeric(x)
  list(csv = p[1], out = p[2], check_level = as.integer(p[3]),
       full_logLik = na_num(p[4]), add_logLik = na_num(p[5]),
       expected_failed = identical(tolower(p[6]), "true"), id = p[7])
}

# ---- JSON の部品(配列・入れ子)--------------------------------------------------

jnum_vec <- function(x) paste0("[", paste(vapply(x, jnum, character(1), fmt = "%.12g"), collapse = ", "), "]")
jstr_vec <- function(x) paste0("[", paste(vapply(x, jstr, character(1)), collapse = ", "), "]")
jobj <- function(...) {
  items <- list(...)
  paste0("{", paste(sprintf("%s: %s", vapply(names(items), jstr, character(1)), unlist(items)), collapse = ", "), "}")
}

# ---- 当てはめの記録 ---------------------------------------------------------------

# 答える問い: この当てはめの logLik は(例外なら NA)。
loglik_of <- function(fit) if (is.null(fit)) NA_real_ else as.numeric(logLik(fit))

# power_sim_fit.R の `pick`(use_refit_for_lrt = true)と同じ。当て直したほうが最終の当てはめ。
final_fit <- function(res) if (res$refit_done) res$refit else res$fit0

# 答える問い: 新しい項 seed:task:coverage の SD 推定値は(0 への張り付きを見る。D4)。
new_term_sd <- function(fit) {
  if (is.null(fit)) return(NA_real_)
  vc <- as.data.frame(VarCorr(fit))
  hit <- vc$grp == NEW_TERM_GROUP & is.na(vc$var2)
  if (!any(hit)) NA_real_ else vc$sdcor[which(hit)[1]]
}

# 答える問い: ADR-059 の当て直しで一番動いた固定効果は何か(D3)。床の失敗した当てはめだけに使う。
moved_coefficient <- function(res) {
  if (!res$refit_done) return(jobj(name = "null", shift_se = "null", se = "null", before = "null", after = "null"))
  b0 <- fixef(res$fit0)
  b1 <- fixef(res$refit)
  se0 <- summary(res$fit0)$coefficients[, "Std. Error"]
  z <- abs(b1 - b0) / se0
  j <- which.max(z)
  jobj(name = jstr(names(z)[j]), shift_se = jnum(z[[j]]), se = jnum(se0[[j]]),
       before = jnum(b0[[j]]), after = jnum(b1[[j]]))
}

# 答える問い: judge_one の結果(床の full / add の片方)の記録は何か。D2・D3・D4 の材料。
judge_record <- function(res) {
  fin <- final_fit(res)
  refit_msgs_all <- if (res$refit_done) length(res$refit@optinfo$conv$lme4$messages) else NA_integer_
  refit_msgs_ns <- if (res$refit_done) length(non_singular_messages(res$refit)) else NA_integer_
  fit0_msgs_all <- if (is.null(res$fit0)) NA_integer_ else length(res$fit0@optinfo$conv$lme4$messages)
  jobj(
    failed = jbool(res$failed), errored = jbool(res$errored), refit_done = jbool(res$refit_done),
    loglik_gain = jnum(res$loglik_gain), beta_move = jnum(res$beta_move),
    loglik_fit0 = jnum(loglik_of(res$fit0)), loglik_final = jnum(loglik_of(fin)),
    fit0_n_msgs_all = jnum(fit0_msgs_all),
    refit_n_msgs_all = jnum(refit_msgs_all), refit_n_msgs_nonsingular = jnum(refit_msgs_ns),
    singular = jbool(isTRUE(res$singular)),
    sd_new_term = jnum(new_term_sd(fin)),
    moved = if (res$failed && res$refit_done) moved_coefficient(res) else "null")
}

# 答える問い: 床の full / add の LRT の p 値は(当て直しの後 = power_sim_fit.R の p_value と同じ手順 / fit0 同士)。
lrt_p <- function(fit_add, fit_full) {
  if (is.null(fit_add) || is.null(fit_full)) return(NA_real_)
  tryCatch(anova(fit_add, fit_full, test = "LRT")[["Pr(>Chisq)"]][2], error = function(e) NA_real_)
}

# ---- D1: allFit --------------------------------------------------------------------

# 答える問い: allFit の最適化 1 つの結果(logLik・固定効果・SE・警告)は何か。例外なら error に文面。
allfit_record <- function(name, fit) {
  if (inherits(fit, "error")) {
    return(jobj(optimizer = jstr(name), error = jstr(conditionMessage(fit)), n_msgs_all = "null",
                n_msgs_nonsingular = "null", loglik = "null", npar = "null",
                fixef = "null", se = "null", first_message = jstr("")))
  }
  msgs <- fit@optinfo$conv$lme4$messages
  sm <- tryCatch(summary(fit)$coefficients, error = function(e) NULL)
  jobj(optimizer = jstr(name), error = jstr(""),
       n_msgs_all = jnum(length(msgs)), n_msgs_nonsingular = jnum(length(non_singular_messages(fit))),
       loglik = jnum(loglik_of(fit), "%.12g"), npar = jnum(attr(logLik(fit), "df")),
       fixef = jnum_vec(fixef(fit)), se = if (is.null(sm)) "null" else jnum_vec(sm[, "Std. Error"]),
       first_message = jstr(if (length(msgs)) substr(msgs[[1]], 1, 160) else ""))
}

# 答える問い: この式を allFit の全最適化で当てるとどうなるか。
# **fixed が空なら呼ばない**。template の当てはめは `data` を文字で渡す必要がある(update が再評価するため。下の `diag_data`)。
run_allfit <- function(fixed, cov_levels, level, start_from_mle) {
  fm <- formula_at(level, fixed, cov_levels)
  base <- suppressMessages(suppressWarnings(
    eval(bquote(glmer(.(fm), family = binomial, data = diag_data)))))
  all_fits <- suppressMessages(suppressWarnings(
    allFit(base, verbose = FALSE, start_from_mle = start_from_mle)))
  recs <- vapply(names(all_fits), function(n) allfit_record(n, all_fits[[n]]), character(1))
  list(coef_names = names(fixef(base)), records = recs)
}

# ---- D3: セルの観測規則率 -----------------------------------------------------------

# 答える問い: (タスク型 x 被覆)のセルで、シードごとの観測規則率は 0 / 1 に張り付いたか。
cell_records <- function(d) {
  rate <- aggregate(is_rule ~ seed + task + coverage, data = d, FUN = mean)
  cells <- unique(rate[, c("task", "coverage")])
  recs <- character(0)
  for (i in seq_len(nrow(cells))) {
    t <- cells$task[i]; cv <- cells$coverage[i]
    r <- rate$is_rule[rate$task == t & rate$coverage == cv]
    pooled <- mean(d$is_rule[d$task == t & d$coverage == cv])
    recs <- c(recs, jobj(task = jstr(t), coverage = jstr(cv), n_seed = jnum(length(r)),
                         n_seeds_at_0 = jnum(sum(r == 0)), n_seeds_at_1 = jnum(sum(r == 1)),
                         min_rate = jnum(min(r)), max_rate = jnum(max(r)), pooled_rate = jnum(pooled)))
  }
  recs
}

# ---- 1 反復 ------------------------------------------------------------------------

run_case <- function(job, floor_level, loglik_tol, beta_tol, d0_tol, start_from_mle) {
  d <- read.csv(job$csv, stringsAsFactors = TRUE)
  d$coverage <- relevel(d$coverage, ref = "id")   # §3.2: id を基準(power_sim_fit.R と同じ)
  cov_levels <- levels(d$coverage)
  for (cl in cov_levels) d[[indicator_name(cl)]] <- as.numeric(d$coverage == cl)
  # allFit の update() が `data` を再評価するので、名前の付いた場所に置く(関数の中の変数は見えない)
  assign("diag_data", d, envir = globalenv())

  pair_at <- function(level) {
    list(full = suppressMessages(suppressWarnings(
           judge_one(formula_at(level, FIXED_FULL, cov_levels), d, loglik_tol, beta_tol))),
         add = suppressMessages(suppressWarnings(
           judge_one(formula_at(level, FIXED_ADD, cov_levels), d, loglik_tol, beta_tol))))
  }

  # D0: その反復が止まった段の当てはめを作り直し、JSON の logLik と失敗の判定に合うか(合わなければ止まる)
  at_check <- pair_at(job$check_level)
  got <- c(full = loglik_of(final_fit(at_check$full)), add = loglik_of(final_fit(at_check$add)))
  want <- c(full = job$full_logLik, add = job$add_logLik)
  gap <- abs(got - want)
  both_na <- is.na(got) & is.na(want)
  d0_ok <- all(both_na | (!is.na(gap) & gap < d0_tol))
  failed_now <- at_check$full$failed || at_check$add$failed
  if (!d0_ok || !identical(failed_now, job$expected_failed)) {
    stop(sprintf("D0 が合わない(%s): logLik 再現 full %.10g / add %.10g に対し JSON %.10g / %.10g、失敗 %s に対し JSON %s",
                 job$id, got[["full"]], got[["add"]], want[["full"]], want[["add"]],
                 failed_now, job$expected_failed))
  }

  floor_pair <- if (job$check_level == floor_level) at_check else pair_at(floor_level)

  # D2: 床の fit0 同士・当て直しの後の LRT(判定には使わない。記述)
  p_fit0 <- lrt_p(floor_pair$add$fit0, floor_pair$full$fit0)
  p_final <- lrt_p(final_fit(floor_pair$add), final_fit(floor_pair$full))

  # D1: allFit(床の式の full / add)
  af_full <- run_allfit(FIXED_FULL, cov_levels, floor_level, start_from_mle)
  af_add <- run_allfit(FIXED_ADD, cov_levels, floor_level, start_from_mle)

  fields <- c(
    kv("case_id", jstr(job$id)),
    kv("r_version", jstr(R.version.string)),
    kv("lme4_version", jstr(as.character(packageVersion("lme4")))),
    kv("check_level", jnum(job$check_level)),
    kv("floor_level", jnum(floor_level)),
    kv("d0", jobj(full_logLik = jnum(got[["full"]], "%.12g"), add_logLik = jnum(got[["add"]], "%.12g"),
                  full_logLik_json = jnum(want[["full"]], "%.12g"), add_logLik_json = jnum(want[["add"]], "%.12g"),
                  failed_reproduced = jbool(failed_now), ok = jbool(d0_ok))),
    kv("floor_full", judge_record(floor_pair$full)),
    kv("floor_add", judge_record(floor_pair$add)),
    kv("p_fit0", jnum(p_fit0, "%.10g")),
    kv("p_final", jnum(p_final, "%.10g")),
    kv("allfit_start_from_mle", jbool(start_from_mle)),
    kv("allfit_full", paste0("{\"coef_names\": ", jstr_vec(af_full$coef_names), ", \"records\": [\n    ",
                             paste(af_full$records, collapse = ",\n    "), "\n  ]}")),
    kv("allfit_add", paste0("{\"coef_names\": ", jstr_vec(af_add$coef_names), ", \"records\": [\n    ",
                            paste(af_add$records, collapse = ",\n    "), "\n  ]}")),
    kv("cells", paste0("[\n    ", paste(cell_records(d), collapse = ",\n    "), "\n  ]"))
  )
  write_json(fields, job$out)
}

# ---- driver ----------------------------------------------------------------------

man_lines <- readLines(manifest_path, warn = FALSE)
man_lines <- man_lines[nzchar(trimws(man_lines))]
man <- read_manifest(man_lines)
loglik_tol <- as.numeric(man$loglik_tolerance)
beta_tol <- as.numeric(man$beta_move_tolerance)
floor_level <- as.integer(man$floor_level)
d0_tol <- as.numeric(man$d0_loglik_tolerance)
start_from_mle <- identical(tolower(man$allfit_start_from_mle), "true")

for (job_text in vals_for(man_lines, "case")) {
  job <- parse_case(job_text)
  if (file.exists(job$out)) {
    cat(sprintf("%s exists, skipping\n", basename(job$out)))
    next
  }
  t0 <- proc.time()[["elapsed"]]
  run_case(job, floor_level, loglik_tol, beta_tol, d0_tol, start_from_mle)
  cat(sprintf("%s -> %s (%.1fs)\n", job$id, basename(job$out), proc.time()[["elapsed"]] - t0))
}
cat("done\n")
