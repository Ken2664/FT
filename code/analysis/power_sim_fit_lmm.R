# code/analysis/power_sim_fit_lmm.R — 天井の手当て C の当てはめ側(PLAN-046 I2 / §5.6 / ADR-133 決定1)。
#
# 答える問い: 「合成表 1 枚に対して、§3.2 と同じランダム構造の**恒等リンクの LMM**(`lmer`・ML)の
# `fit_full` / `fit_add` の対を、ロジットの道と同じ縮退の手続きごと当てると、LRT(df = 2)の p 値と
# 交互作用の 2 係数(確率の尺度の差の差)・Wald SE は何になるか」
#
# **ロジットの道(power_sim_fit.R)は 1 バイトも変えない**(PLAN-046 I2)。そのため、あちらの補助関数を
# source せず(あちらはファイルの末尾で driver を走らせる)、この中に写した。**写しであって、別の手続きではない**。
# ロジットの道との違いは次の 4 つだけである(ADR-133 決定1):
#   1. `glmer(family = binomial)` → `lmer(REML = FALSE)`(ML。LRT のため)
#   2. 当て直しの初期値は `theta` だけ(`lmer` は固定効果をプロファイルで消すので `fixef` を初期値に持てない)。
#      可動量 `max|Δβ| / SE` は当て直しの前後の固定効果から同じ式で出す
#   3. 最適化を manifest で明示する(`lmerControl(optimizer = ...)`。lme4 の既定に頼らない。PLAN-046 §5.6 の実装上の注意)
#   4. `anova(..., refit = FALSE)`(ML で当てた対をそのまま比べる。REML で当て直させない)
# 判定(ADR-059 の 2 つの閾値・符号付きの片側)・ペア単位・縮退順序・床の `allFit` の段(5 最適化・`start_from_mle`・
# `min_aligned`・版の確認)・例外の扱い(ADR-124)・出力のキー名は power_sim_fit.R と同じである。
#
# 呼ばれ方(引数は位置で渡す。code/analysis/ceiling_remedy.py が組み立てる):
#   Rscript power_sim_fit_lmm.R <libpath|""> <manifest>
# manifest は power_sim_fit.R と同じ平文に `lmm_optimizer` と `lmm_reml` を足したもの。

args <- commandArgs(trailingOnly = TRUE)
libpath <- args[1]
manifest_path <- args[2]
if (nzchar(libpath)) .libPaths(c(libpath, .libPaths()))

suppressPackageStartupMessages(library(lme4))

# ---- Documents/05_STATISTICS.md §3.2 のモデル指定(power_sim_fit.R の写し)-----------
NEW_TERM <- "(1 | seed:task:coverage)"
LEVEL_LABEL <- c("none", "drop_template", "drop_coverage_corr", "drop_coverage_slope")
REDUCTION_LABEL <- LEVEL_LABEL
LINK <- "identity"

indicator_name <- function(cov_level) paste0("cov_", cov_level)

random_by_level <- function(level, cov_levels) {
  independent_slopes <- paste(
    sprintf("(0 + %s | seed)", vapply(cov_levels, indicator_name, character(1))),
    collapse = " + ")
  switch(level + 1L,
    paste("(0 + coverage | seed) + (1 | item) + (1 | template)", "+", NEW_TERM),
    paste("(0 + coverage | seed) + (1 | item)", "+", NEW_TERM),
    paste(independent_slopes, "+ (1 | item)", "+", NEW_TERM),
    paste("(1 | seed) + (1 | item)", "+", NEW_TERM),
    stop(sprintf("未知の縮退水準 %d", level)))
}

formula_at <- function(level, fixed, cov_levels) {
  as.formula(paste("is_rule ~", fixed, "+", random_by_level(level, cov_levels)))
}

# ---- 平文 manifest(power_sim_fit.R の写し)---------------------------------

read_manifest <- function(lines) {
  keys <- trimws(sub("=.*$", "", lines))
  vals <- trimws(sub("^[^=]*=", "", lines))
  keep <- keys != "fit"
  setNames(as.list(vals[keep]), keys[keep])
}

vals_for <- function(lines, key) {
  hit <- trimws(sub("=.*$", "", lines)) == key
  trimws(sub("^[^=]*=", "", lines[hit]))
}

# ---- JSON 書き出し(power_sim_fit.R の写し)--------------------------------

jstr <- function(x) {
  x <- iconv(as.character(x), to = "ASCII", sub = "?")
  x <- gsub("\\\\", "/", x)
  x <- gsub("\"", "'", x)
  paste0("\"", gsub("[[:space:]]+", " ", x), "\"")
}
jnum <- function(x, fmt = "%.14g") {
  if (length(x) != 1 || is.na(x) || !is.finite(x)) "null" else sprintf(fmt, x)
}
jbool <- function(x) if (isTRUE(x)) "true" else "false"
kv <- function(key, val) paste0("  ", jstr(key), ": ", val)

write_json <- function(fields, path) {
  txt <- paste0("{\n", paste(fields, collapse = ",\n"), "\n}\n")
  tmp <- paste0(path, ".tmp")
  con <- file(tmp, "wb")
  writeBin(charToRaw(txt), con)
  close(con)
  if (!file.rename(tmp, path)) stop(sprintf("一時ファイルを %s へ rename できなかった", path))
}

# ---- ADR-059 の収束判定(恒等リンク版)--------------------------------------

non_singular_messages <- function(fit) {
  msgs <- fit@optinfo$conv$lme4$messages
  if (is.null(msgs)) return(character(0))
  msgs[!grepl("singular", msgs, ignore.case = TRUE)]
}

errored_result <- function(e) {
  list(fit0 = NULL, refit = NULL, refit_done = FALSE, failed = TRUE, errored = TRUE,
       error_message = conditionMessage(e),
       loglik_gain = NA_real_, beta_move = NA_real_, singular = NA, n_msgs = NA_integer_)
}

# 答える問い: この式の恒等リンクの LMM(ML・最適化は manifest の値)はいくつか。例外は呼び出し側が捕まえる。
fit_lmm <- function(form, data, optimizer, start = NULL) {
  lmer(form, data = data, REML = FALSE, control = lmerControl(optimizer = optimizer), start = start)
}

# 答える問い: この当てはめは ADR-059 の意味で「収束した」か(ロジットの道の judge_one と同じ判定)。
judge_one <- function(form, data, loglik_tol, beta_tol, optimizer) {
  fit0 <- tryCatch(fit_lmm(form, data, optimizer), error = function(e) e)
  if (inherits(fit0, "error")) return(errored_result(fit0))
  if (length(non_singular_messages(fit0)) == 0) {
    return(list(fit0 = fit0, refit = NULL, refit_done = FALSE, failed = FALSE,
                errored = FALSE, error_message = "",
                loglik_gain = NA_real_, beta_move = NA_real_,
                singular = isSingular(fit0),
                n_msgs = length(fit0@optinfo$conv$lme4$messages)))
  }
  # ADR-133 決定1: 初期値は theta だけ(lmer は固定効果を最適化の変数に持たない)。閾値と式はロジットの道と同じ。
  se0 <- summary(fit0)$coefficients[, "Std. Error"]
  fit1 <- tryCatch(
    fit_lmm(form, data, optimizer, start = list(theta = getME(fit0, "theta"))),
    error = function(e) e)
  if (inherits(fit1, "error")) return(errored_result(fit1))
  gain <- as.numeric(logLik(fit1)) - as.numeric(logLik(fit0))
  move <- max(abs(fixef(fit1) - fixef(fit0)) / se0)
  failed <- !(gain < loglik_tol && move < beta_tol)
  list(fit0 = fit0, refit = fit1, refit_done = TRUE, failed = failed,
       errored = FALSE, error_message = "",
       loglik_gain = gain, beta_move = move,
       singular = isSingular(fit1),
       n_msgs = length(fit1@optinfo$conv$lme4$messages))
}

# ---- 交互作用の係数(確率の尺度の差の差。平行性の TOST)-----------------------

# 答える問い: `task:coverage` の係数(恒等リンクなので確率の尺度の差の差)の推定値と Wald SE はいくつか。
# キー名はロジットの道と同じ(python 側の `equivalence_margin` がそのまま読む)。見つからなければ止まる。
interaction_coefficients <- function(fit, d) {
  cf <- summary(fit)$coefficients
  task_levels <- levels(d$task)
  cov_levels <- levels(d$coverage)
  fields <- character(0)
  for (tl in task_levels[-1L]) {
    for (cl in cov_levels[-1L]) {
      nm <- paste0("task", tl, ":coverage", cl)
      if (!(nm %in% rownames(cf))) stop(sprintf("交互作用の係数 %s が当てはめに無い", nm))
      fields <- c(fields,
                  kv(paste0("interaction_", cl, "_est"), jnum(cf[nm, "Estimate"], "%.10g")),
                  kv(paste0("interaction_", cl, "_se"), jnum(cf[nm, "Std. Error"], "%.10g")))
    }
  }
  fields
}

# ---- 床の allFit の段(power_sim_fit.R の写し。土台が lmer になるだけ)------------

rescue_method_table <- function(opt_names) {
  has_method <- grepl(".", opt_names, fixed = TRUE)
  cbind(optimizer = sub("\\..*$", "", opt_names),
        method = ifelse(has_method, sub("^[^.]*\\.", "", opt_names), ""))
}

rescue_check_available <- function(opt_names) {
  tab <- allFit(NULL, meth.tab = rescue_method_table(opt_names), show.meth.tab = TRUE)
  tab <- matrix(tab, ncol = 2L)
  got <- gsub("\\.$", "", paste(tab[, 1L], tab[, 2L], sep = "."))
  lacking <- setdiff(opt_names, got)
  if (length(lacking) > 0L) {
    stop(sprintf("allFit で使えない最適化がある: %s(ADR-129 決定1: 1 つでも使えなければ止まる)",
                 paste(lacking, collapse = ", ")))
  }
}

rescue_check_versions <- function(expected_r, expected_lme4) {
  r_now <- paste(R.version$major, R.version$minor, sep = ".")
  lme4_now <- as.character(packageVersion("lme4"))
  if (!identical(r_now, expected_r) || !identical(lme4_now, expected_lme4)) {
    stop(sprintf("R / lme4 の版が違う: R %s(期待 %s)/ lme4 %s(期待 %s)", r_now, expected_r, lme4_now, expected_lme4))
  }
}

rescue_record <- function(name, fit) {
  if (inherits(fit, "error")) {
    return(list(name = name, error = conditionMessage(fit), n_nonsingular = NA_integer_, loglik = NA_real_))
  }
  list(name = name, error = "", n_nonsingular = length(non_singular_messages(fit)),
       loglik = as.numeric(logLik(fit)))
}

rescue_select <- function(records, loglik_tol, min_aligned) {
  eligible <- Filter(function(r) !nzchar(r$error) && is.finite(r$loglik) && r$n_nonsingular == 0L, records)
  if (length(eligible) == 0L) return(list(satisfied = FALSE, n_aligned = 0L, best = ""))
  lls <- vapply(eligible, function(r) r$loglik, numeric(1))
  best_at <- which.max(lls)
  n_aligned <- sum(lls[best_at] - lls < loglik_tol)
  list(satisfied = n_aligned >= min_aligned, n_aligned = as.integer(n_aligned), best = eligible[[best_at]]$name)
}

# 答える問い: この式を allFit の最適化すべてで当てると、収束と言えるか。土台は manifest の最適化の lmer(ML)。
# allFit は土台を update() で当て直すので REML = FALSE は引き継がれる。
rescue_one_formula <- function(form, data, opt_names, start_from_mle, loglik_tol, min_aligned, optimizer) {
  assign("rescue_data", data, envir = globalenv())
  assign("rescue_optimizer", optimizer, envir = globalenv())
  all_fits <- tryCatch({
    base <- suppressMessages(suppressWarnings(
      eval(bquote(lmer(.(form), data = rescue_data, REML = FALSE,
                       control = lmerControl(optimizer = rescue_optimizer))))))
    suppressMessages(suppressWarnings(
      allFit(base, meth.tab = rescue_method_table(opt_names), verbose = FALSE,
             start_from_mle = start_from_mle)))
  }, error = function(e) e)
  if (inherits(all_fits, "error")) {
    return(list(fits = list(), records = list(), select = list(satisfied = FALSE, n_aligned = 0L, best = ""),
                error = conditionMessage(all_fits)))
  }
  if (!identical(names(all_fits), opt_names)) {
    stop(sprintf("allFit の結果の名前が指定と違う: %s", paste(names(all_fits), collapse = ", ")))
  }
  records <- lapply(opt_names, function(nm) rescue_record(nm, all_fits[[nm]]))
  list(fits = all_fits, records = records, select = rescue_select(records, loglik_tol, min_aligned), error = "")
}

rescue_records_json <- function(records) {
  if (length(records) == 0L) return("[]")
  items <- vapply(records, function(r) {
    paste0("    {", paste(c(
      paste0("\"optimizer\": ", jstr(r$name)),
      paste0("\"error\": ", jstr(r$error)),
      paste0("\"n_nonsingular_warnings\": ", jnum(r$n_nonsingular)),
      paste0("\"loglik\": ", jnum(r$loglik, "%.12g"))
    ), collapse = ", "), "}")
  }, character(1))
  paste0("[\n", paste(items, collapse = ",\n"), "\n  ]")
}

level_record <- function(level, which, res) {
  paste0(
    "    {", paste(c(
      paste0("\"level\": ", jnum(level)),
      paste0("\"label\": ", jstr(LEVEL_LABEL[[level + 1L]])),
      paste0("\"which\": ", jstr(which)),
      paste0("\"failed\": ", jbool(res$failed)),
      paste0("\"refit_done\": ", jbool(res$refit_done)),
      paste0("\"singular\": ", jbool(res$singular)),
      paste0("\"n_warnings\": ", jnum(res$n_msgs)),
      paste0("\"loglik_gain\": ", jnum(res$loglik_gain)),
      paste0("\"max_shift\": ", jnum(res$beta_move)),
      paste0("\"error\": ", jstr(if (res$errored) res$error_message else ""))
    ), collapse = ", "), "}")
}

# ---- 1 枚の表 --------------------------------------------------------------

run_one <- function(csv_path, out_path, loglik_tol, beta_tol, max_level, use_refit, allfit, optimizer) {
  d <- read.csv(csv_path, stringsAsFactors = TRUE)
  d$coverage <- relevel(d$coverage, ref = "id")
  cov_levels <- levels(d$coverage)
  for (cl in cov_levels) d[[indicator_name(cl)]] <- as.numeric(d$coverage == cl)

  level <- 0L
  n_errored <- 0L
  first_error <- ""
  records <- character(0)
  repeat {
    # ★判定はペア単位(ADR-059 の付帯条件・ADR-133 決定1)
    res_full <- judge_one(formula_at(level, "task * coverage", cov_levels), d, loglik_tol, beta_tol, optimizer)
    res_add <- judge_one(formula_at(level, "task + coverage", cov_levels), d, loglik_tol, beta_tol, optimizer)
    records <- c(records, level_record(level, "full", res_full), level_record(level, "add", res_add))
    for (res in list(res_full, res_add)) {
      if (res$errored) {
        n_errored <- n_errored + 1L
        if (!nzchar(first_error)) first_error <- res$error_message
      }
    }
    if (!(res_full$failed || res_add$failed) || level >= max_level) break
    level <- level + 1L
  }

  floor_failed <- res_full$failed || res_add$failed
  floor_base_errored <- floor_failed && (res_full$errored || res_add$errored)
  allfit_attempted <- floor_failed && !floor_base_errored && level >= max_level
  af_full <- NULL
  af_add <- NULL
  rescued <- FALSE
  if (allfit_attempted) {
    af_full <- rescue_one_formula(formula_at(level, "task * coverage", cov_levels), d, allfit$optimizers,
                                  allfit$start_from_mle, loglik_tol, allfit$min_aligned, optimizer)
    af_add <- rescue_one_formula(formula_at(level, "task + coverage", cov_levels), d, allfit$optimizers,
                                 allfit$start_from_mle, loglik_tol, allfit$min_aligned, optimizer)
    rescued <- af_full$select$satisfied && af_add$select$satisfied
  }
  # 床の最後でも当てはまらない = C の道の当てはめ失敗 = 実施不能(B。PLAN-046 §5 手順 4)
  fit_failed <- floor_failed && !rescued

  pick <- function(res) if (res$refit_done && use_refit) res$refit else res$fit0
  used_full <- if (rescued) af_full$fits[[af_full$select$best]] else if (fit_failed) NULL else pick(res_full)
  used_add <- if (rescued) af_add$fits[[af_add$select$best]] else if (fit_failed) NULL else pick(res_add)
  an <- if (fit_failed) NULL else anova(used_add, used_full, refit = FALSE)
  interaction_fields <- if (fit_failed) character(0) else interaction_coefficients(used_full, d)
  lrt_field <- function(col, fmt) {
    if (is.null(an)) "null" else jnum(an[[col]][2], fmt)
  }
  an_descriptive <- if (fit_failed && !floor_base_errored) {
    tryCatch(anova(pick(res_add), pick(res_full), refit = FALSE), error = function(e) NULL)
  } else NULL
  p_descriptive_field <- if (is.null(an_descriptive)) "null" else jnum(an_descriptive[["Pr(>Chisq)"]][2], "%.10g")
  select_field <- function(af, key) if (is.null(af)) "null" else jnum(af$select[[key]])
  best_field <- function(af) if (is.null(af)) jstr("") else jstr(af$select$best)

  fields <- c(
    kv("csv", jstr(basename(csv_path))),
    kv("link", jstr(LINK)),
    kv("reml", jbool(FALSE)),
    kv("optimizer", jstr(optimizer)),
    kv("n_rows", jnum(nrow(d))),
    kv("n_seed", jnum(nlevels(d$seed))),
    kv("n_item", jnum(nlevels(d$item))),
    kv("n_template", jnum(nlevels(d$template))),
    kv("r_version", jstr(R.version.string)),
    kv("lme4_version", jstr(as.character(packageVersion("lme4")))),
    kv("reduction_level", jnum(level)),
    kv("reduction_label", jstr(REDUCTION_LABEL[[level + 1L]])),
    kv("reduced", jbool(level > 0L)),
    kv("fit_failed", jbool(fit_failed)),
    kv("n_errored_fits", jnum(n_errored)),
    kv("first_error", jstr(first_error)),
    kv("chisq", lrt_field("Chisq", "%.10g")),
    kv("df", lrt_field("Df", "%.14g")),
    kv("p_value", lrt_field("Pr(>Chisq)", "%.10g")),
    kv("p_value_failed_descriptive", p_descriptive_field),
    kv("fit_failed_before_allfit", jbool(floor_failed)),
    kv("floor_base_errored", jbool(floor_base_errored)),
    kv("allfit_attempted", jbool(allfit_attempted)),
    kv("rescued_by_allfit", jbool(rescued)),
    kv("allfit_start_from_mle", jbool(allfit$start_from_mle)),
    kv("allfit_full_n_aligned", select_field(af_full, "n_aligned")),
    kv("allfit_add_n_aligned", select_field(af_add, "n_aligned")),
    kv("allfit_full_selected", best_field(af_full)),
    kv("allfit_add_selected", best_field(af_add)),
    kv("allfit_full_error", jstr(if (is.null(af_full)) "" else af_full$error)),
    kv("allfit_add_error", jstr(if (is.null(af_add)) "" else af_add$error)),
    kv("used_full_logLik", if (is.null(used_full)) "null" else jnum(as.numeric(logLik(used_full)))),
    kv("used_add_logLik", if (is.null(used_add)) "null" else jnum(as.numeric(logLik(used_add))))
  )
  fields <- c(fields, interaction_fields)
  for (nm in c("full", "add")) {
    res <- if (nm == "full") res_full else res_add
    fields <- c(
      fields,
      kv(paste0(nm, "_refit_done"), jbool(res$refit_done)),
      kv(paste0(nm, "_failed"), jbool(res$failed)),
      kv(paste0(nm, "_singular"), jbool(res$singular)),
      kv(paste0(nm, "_n_msgs"), jnum(res$n_msgs)),
      kv(paste0(nm, "_loglik_gain"), jnum(res$loglik_gain)),
      kv(paste0(nm, "_beta_move"), jnum(res$beta_move)),
      kv(paste0(nm, "_logLik"),
         if (res$errored) "null" else jnum(as.numeric(logLik(pick(res))))),
      kv(paste0(nm, "_df_model"),
         if (res$errored) "null" else jnum(attr(logLik(pick(res)), "df")))
    )
  }
  fields <- c(fields, kv("levels", paste0("[\n", paste(records, collapse = ",\n"), "\n  ]")),
              kv("allfit_full", rescue_records_json(if (is.null(af_full)) list() else af_full$records)),
              kv("allfit_add", rescue_records_json(if (is.null(af_add)) list() else af_add$records)))
  write_json(fields, out_path)
}

# ---- driver ----------------------------------------------------------------

lines <- readLines(manifest_path, warn = FALSE)
lines <- lines[nzchar(trimws(lines))]
man <- read_manifest(lines)

for (key in c("loglik_tolerance", "beta_move_tolerance", "use_refit_for_lrt", "max_reduction_level",
              "allfit_optimizers", "allfit_start_from_mle", "allfit_min_aligned",
              "expected_r_version", "expected_lme4_version", "lmm_optimizer", "lmm_reml")) {
  if (is.null(man[[key]]) || !nzchar(man[[key]])) stop(sprintf("manifest に %s が無い", key))
}
# ADR-133 決定1: ML(LRT のため)。REML の manifest は受け付けない
if (!identical(tolower(man$lmm_reml), "false")) stop("lmm_reml は false(ML)でなければならない(ADR-133 決定1)")
loglik_tol <- as.numeric(man$loglik_tolerance)
beta_tol <- as.numeric(man$beta_move_tolerance)
max_level <- as.integer(man$max_reduction_level)
use_refit <- identical(tolower(man$use_refit_for_lrt), "true")
optimizer <- man$lmm_optimizer
allfit <- list(
  optimizers = trimws(strsplit(man$allfit_optimizers, ",", fixed = TRUE)[[1]]),
  start_from_mle = identical(tolower(man$allfit_start_from_mle), "true"),
  min_aligned = as.integer(man$allfit_min_aligned))
rescue_check_versions(man$expected_r_version, man$expected_lme4_version)
rescue_check_available(allfit$optimizers)

for (job in vals_for(lines, "fit")) {
  parts <- strsplit(job, "|", fixed = TRUE)[[1]]
  csv_path <- trimws(parts[1])
  out_path <- trimws(parts[2])
  if (file.exists(out_path)) {
    cat(sprintf("%s exists, skipping\n", basename(out_path)))
    next
  }
  t0 <- proc.time()[["elapsed"]]
  run_one(csv_path, out_path, loglik_tol, beta_tol, max_level, use_refit, allfit, optimizer)
  cat(sprintf("%s -> %s (%.1fs)\n", basename(csv_path), basename(out_path),
              proc.time()[["elapsed"]] - t0))
}
cat("done\n")
