# code/analysis/power_sim_fit.R — 検出力シミュレーションの当てはめ側(§6.3 手続き3b)。
#
# 答える問い: 「合成表 1 枚に対して、Documents/05_STATISTICS.md §3.2 の
# `fit_full` / `fit_add` の対を ADR-059 の縮退カスケードごと当てると、
# LRT(df = 2。T1 x T2。ADR-112)の p 値と、縮退が発火したかどうかは何になるか」
# ★ADR-114 決定5: 平行性の TOST のために、`fit_full` の交互作用の係数(`task:coverage`。処理対比・
# 基準 = タスク型の最初の水準 x 被覆の `id`)の推定値と Wald SE も出す。**LRT は変えない**(ランダム構造は ADR-124 で改めた)。
#
# **§3.2 の R コードがそのまま実行物になる**ことが ADR-058 決定1 の採択理由の 1 つである。
# したがって下の `random_by_level` の level 0 は §3.2 の式をそのまま写している。
# 書き換えるときは §3.2 と ADR-064 決定4 / ADR-066 決定1 / ADR-124 を先に読むこと。
#
# 呼ばれ方(引数は位置で渡す。code/analysis/power_sim.py が組み立てる):
#   Rscript power_sim_fit.R <libpath|""> <manifest>
#
# manifest は python 側が書く。R に JSON パーサを持ち込まないため、
# manifest は「1 行 1 キー = 値」の平文である(依存を lme4 だけに保つ。検査3 と同じ作法)。
# **1 回の起動で複数の表を当てる** —— R の起動と lme4 の読み込みは表 1 枚あたり
# 数秒かかり、反復 1000 回ならそれだけで数時間になる。`fit=<csv>|<out.json>` の行を
# 上から順に処理し、出力が既にあるものは飛ばす(途中で落ちても再開できる)。

args <- commandArgs(trailingOnly = TRUE)
libpath <- args[1]
manifest_path <- args[2]
if (nzchar(libpath)) .libPaths(c(libpath, .libPaths()))

suppressPackageStartupMessages(library(lme4))

# ---- Documents/05_STATISTICS.md §3.2 のモデル指定(そのまま写す)-----------
# ★2026-10-05(PLAN-041 I1 / ADR-124 決定1・2): 新しい項 `(1 | seed:task:coverage)` を足し、縮退順序を
# template -> coverage の傾きの相関 -> coverage の傾き(= 床)に改めた。**item と seed:task:coverage は
# どの水準でも落とさない**(落とすと検定の意味が変わる項。ADR-124 D2)。旧: template -> 傾き -> item(ADR-065 決定2)。
# level 0 が §3.2 そのもの。level が上がるほど落としたものが増える。
#
# level 2 の「傾きの相関を落とす」= `(0 + coverage | seed)` を被覆の水準ごとの独立な分散 3 つにする(相関 0)。
# **lme4 の `||` は因子に掛けると相関を落とさないことがある**ので、被覆の指示変数(0/1 の数値列)を
# 表に足して、`(0 + cov_<水準> | seed)` を水準の数だけ並べる(`random_by_level`)。
NEW_TERM <- "(1 | seed:task:coverage)"
LEVEL_LABEL <- c("none", "drop_template", "drop_coverage_corr", "drop_coverage_slope")
REDUCTION_LABEL <- LEVEL_LABEL

# 答える問い: 被覆の水準ごとの指示変数の列名は何か(表に足す列と式の項の名前を一致させる)。
indicator_name <- function(cov_level) paste0("cov_", cov_level)

# 答える問い: この水準のランダム構造の式(右辺)は何か。
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

# ---- 平文 manifest ---------------------------------------------------------

# 答える問い: この起動の設定は何か。`fit` の行は複数あるので単一値の表からは外す。
read_manifest <- function(lines) {
  keys <- trimws(sub("=.*$", "", lines))
  vals <- trimws(sub("^[^=]*=", "", lines))
  keep <- keys != "fit"
  setNames(as.list(vals[keep]), keys[keep])
}

# 答える問い: この起動で当てる表はどれか。同じキーの行すべての値を返す。
vals_for <- function(lines, key) {
  hit <- trimws(sub("=.*$", "", lines)) == key
  trimws(sub("^[^=]*=", "", lines[hit]))
}

# ---- JSON 書き出し(検査3 の作法をそのまま踏襲する)------------------------
# 依存を lme4 だけに保つため手書きである。文字列は空白を潰し、改行を埋め込まない。
# Windows でも LF になるようバイナリ接続で書く。

jstr <- function(x) {
  x <- iconv(as.character(x), to = "ASCII", sub = "?")   # 例外の文面は ASCII で残す(python 側が ascii で読む)
  x <- gsub("\\\\", "/", x)
  x <- gsub("\"", "'", x)
  paste0("\"", gsub("[[:space:]]+", " ", x), "\"")
}
jnum <- function(x, fmt = "%.14g") {
  if (length(x) != 1 || is.na(x) || !is.finite(x)) "null" else sprintf(fmt, x)
}
jbool <- function(x) if (isTRUE(x)) "true" else "false"
kv <- function(key, val) paste0("  ", jstr(key), ": ", val)

# ★2026-10-04(PLAN-040 I3 / F6-3): 一時ファイルに書いてから rename する。
# 出力が「在る」ことが「済み」の印なので(下の driver)、書きかけで kill されると壊れた JSON が
# 「済み」として飛ばされ、集計で落ちる。rename は同じディレクトリの中なので、在れば書き終わっている。
write_json <- function(fields, path) {
  txt <- paste0("{\n", paste(fields, collapse = ",\n"), "\n}\n")
  tmp <- paste0(path, ".tmp")
  con <- file(tmp, "wb")
  writeBin(charToRaw(txt), con)
  close(con)
  if (!file.rename(tmp, path)) stop(sprintf("一時ファイルを %s へ rename できなかった", path))
}

# ---- ADR-059 の収束判定 ----------------------------------------------------

# `boundary (singular) fit` は単独では引き金にしない(ADR-059 決定1)。
# singular は収束失敗ではなく境界上の正当な最尤推定である。singular かどうかの
# 判定は isSingular() を直接呼ぶ(文字列一致は lme4 の文面変更で壊れる。F56)。
# ここで文字列を見るのは「singular 以外の警告が他にあるか」を数えるためだけである。
non_singular_messages <- function(fit) {
  msgs <- fit@optinfo$conv$lme4$messages
  if (is.null(msgs)) return(character(0))
  msgs[!grepl("singular", msgs, ignore.case = TRUE)]
}

# ★ADR-059 は警告(収束しない)だけを縮退の引き金にしていた。**`glmer` が例外で落ちる場合
# (`Downdated VtV is not positive definite` など)は書かれていなかった**(2026-10-02。PLAN-034 I7 の
# スモークで、誤指定のシートの小さな表で観測した)。
# ★2026-10-05(ADR-124 例外の規則): **例外も「収束しなかった」と同じ縮退の引き金にする。床でも例外なら
# 「当てはめ失敗」(`fit_failed`。p 値なし)**とし、数と最初の文面を出力に残す(黙って数えない)。
# 失敗をどちら側に数えるかは集計側(power_sim.py。シートの役割で不利な側)が決める。
errored_result <- function(e) {
  list(fit0 = NULL, refit = NULL, refit_done = FALSE, failed = TRUE, errored = TRUE,
       error_message = conditionMessage(e),
       loglik_gain = NA_real_, beta_move = NA_real_, singular = NA, n_msgs = NA_integer_)
}

# 答える問い: この当てはめは ADR-059 の意味で「収束した」か。
# failed が TRUE のときだけ縮退の引き金になる。判定はペア単位で使う(run_one)。
judge_one <- function(form, data, loglik_tol, beta_tol) {
  fit0 <- tryCatch(glmer(form, family = binomial, data = data), error = function(e) e)
  if (inherits(fit0, "error")) return(errored_result(fit0))
  if (length(non_singular_messages(fit0)) == 0) {
    return(list(fit0 = fit0, refit = NULL, refit_done = FALSE, failed = FALSE,
                errored = FALSE, error_message = "",
                loglik_gain = NA_real_, beta_move = NA_real_,
                singular = isSingular(fit0),
                n_msgs = length(fit0@optinfo$conv$lme4$messages)))
  }
  # ADR-059 決定1: 自身の推定値を初期値にして 1 回だけ当て直す。glmer は決定的である。
  se0 <- summary(fit0)$coefficients[, "Std. Error"]
  fit1 <- tryCatch(
    glmer(form, family = binomial, data = data, start = getME(fit0, c("theta", "fixef"))),
    error = function(e) e)
  if (inherits(fit1, "error")) return(errored_result(fit1))
  gain <- as.numeric(logLik(fit1)) - as.numeric(logLik(fit0))
  move <- max(abs(fixef(fit1) - fixef(fit0)) / se0)
  # ADR-059 の追記(2026-09-07): logLik 差は符号付きの片側、可動量は SE で割った最大値。
  failed <- !(gain < loglik_tol && move < beta_tol)
  list(fit0 = fit0, refit = fit1, refit_done = TRUE, failed = failed,
       errored = FALSE, error_message = "",
       loglik_gain = gain, beta_move = move,
       singular = isSingular(fit1),
       n_msgs = length(fit1@optinfo$conv$lme4$messages))
}

# ---- 交互作用の係数(平行性の TOST。ADR-114 決定5)--------------------------

# 答える問い: `task * coverage` の当てはめの `task:coverage` の係数は、推定値と Wald SE でいくつか。
# タスク型の最初の水準を基準とする処理対比(`task` は文字列の昇順 = T1, T2)なので、係数は
# 「(T2 - T1) x (被覆 - id)」である。名前は水準から組み、**見つからなければ止まる**
# (黙って落とすと TOST が空の検定になる。CLAUDE.md §7)。
# キーは `interaction_<被覆の水準名>_est` / `_se`(python 側の `equivalence_margin` が読む)。
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

# ---- 床の allFit の段(PLAN-043 I1 / ADR-128 決定1 (A3) / ADR-129 決定1・2)------------
# ★床(縮退の最後)でも ADR-059 の判定が収束しない表に、床の式(full・add)へ `allFit` を 1 段足す。
# 「警告なしに収束した最適化が min_aligned 個以上・logLik が最大のものから差 < loglik_tol」を full と add の
# **両方**が満たせば収束(PLAN-042 §2.2 の 1a)。揃った最適化のうち logLik 最大のものの LRT を使う。
# 最適化は名前で列挙し(ADR-129 決定1)、1 つでも使えなければ止まる。`start_from_mle` は config の値(false)。
# 名前の接頭辞 `rescue_` は fit_failure_diagnosis.R(この上を借りる)の `run_allfit` などと衝突させないため。

# 答える問い: allFit の最適化の名前(`nloptwrap.NLOPT_LN_BOBYQA` など)は、allFit の表(optimizer, method)のどの行か。
rescue_method_table <- function(opt_names) {
  has_method <- grepl(".", opt_names, fixed = TRUE)
  cbind(optimizer = sub("\\..*$", "", opt_names),
        method = ifelse(has_method, sub("^[^.]*\\.", "", opt_names), ""))
}

# 答える問い: 名前で指した最適化は、この機械の allFit で 1 つ残らず使えるか(使えなければ止まる。黙って減らさない)。
# allFit は dfoptim / optimx が無いと該当の行を自動で外す。`show.meth.tab` は object に触れずに表を返す。
rescue_check_available <- function(opt_names) {
  tab <- allFit(NULL, meth.tab = rescue_method_table(opt_names), show.meth.tab = TRUE)
  tab <- matrix(tab, ncol = 2L)   # 1 行に減ると allFit の中で次元が落ちる
  got <- gsub("\\.$", "", paste(tab[, 1L], tab[, 2L], sep = "."))
  lacking <- setdiff(opt_names, got)
  if (length(lacking) > 0L) {
    stop(sprintf("allFit で使えない最適化がある: %s(ADR-129 決定1: 1 つでも使えなければ止まる)",
                 paste(lacking, collapse = ", ")))
  }
}

# 答える問い: R と lme4 の版は診断(PLAN-042 D1)で allFit を回した版と同じか(違えば止まる。ADR-129 決定1)。
rescue_check_versions <- function(expected_r, expected_lme4) {
  r_now <- paste(R.version$major, R.version$minor, sep = ".")
  lme4_now <- as.character(packageVersion("lme4"))
  if (!identical(r_now, expected_r) || !identical(lme4_now, expected_lme4)) {
    stop(sprintf("R / lme4 の版が違う: R %s(期待 %s)/ lme4 %s(期待 %s)", r_now, expected_r, lme4_now, expected_lme4))
  }
}

# 答える問い: allFit の最適化 1 つの結果は何か(例外なら error に文面。logLik は NA)。
rescue_record <- function(name, fit) {
  if (inherits(fit, "error")) {
    return(list(name = name, error = conditionMessage(fit), n_nonsingular = NA_integer_, loglik = NA_real_))
  }
  list(name = name, error = "", n_nonsingular = length(non_singular_messages(fit)),
       loglik = as.numeric(logLik(fit)))
}

# 答える問い: 最適化の記録のうち、警告なしに収束し最大の logLik から差 < 許容のものはいくつで、その最大はどれか。
# fit_failure_diagnosis.py の `aligned_optimizers` と同じ定義(同点は先)。対象は例外なく終わり、非 singular の警告が 0 のもの。
rescue_select <- function(records, loglik_tol, min_aligned) {
  eligible <- Filter(function(r) !nzchar(r$error) && is.finite(r$loglik) && r$n_nonsingular == 0L, records)
  if (length(eligible) == 0L) return(list(satisfied = FALSE, n_aligned = 0L, best = ""))
  lls <- vapply(eligible, function(r) r$loglik, numeric(1))
  best_at <- which.max(lls)
  n_aligned <- sum(lls[best_at] - lls < loglik_tol)
  list(satisfied = n_aligned >= min_aligned, n_aligned = as.integer(n_aligned), best = eligible[[best_at]]$name)
}

# 答える問い: この式を allFit の最適化すべてで当てると、収束と言えるか。当てはめも返す。
# update() が `data` を再評価するので、名前の付いた場所に置く(関数の中の変数は見えない。診断の run_allfit と同じ)。
rescue_one_formula <- function(form, data, opt_names, start_from_mle, loglik_tol, min_aligned) {
  assign("rescue_data", data, envir = globalenv())
  all_fits <- tryCatch({
    base <- suppressMessages(suppressWarnings(
      eval(bquote(glmer(.(form), family = binomial, data = rescue_data)))))
    suppressMessages(suppressWarnings(
      allFit(base, meth.tab = rescue_method_table(opt_names), verbose = FALSE,
             start_from_mle = start_from_mle)))
  }, error = function(e) e)
  if (inherits(all_fits, "error")) {   # 土台の当てはめが床の判定のときは通ったはずなので、ここに来るのは想定外
    return(list(fits = list(), records = list(), select = list(satisfied = FALSE, n_aligned = 0L, best = ""),
                error = conditionMessage(all_fits)))
  }
  if (!identical(names(all_fits), opt_names)) {
    stop(sprintf("allFit の結果の名前が指定と違う: %s", paste(names(all_fits), collapse = ", ")))
  }
  records <- lapply(opt_names, function(nm) rescue_record(nm, all_fits[[nm]]))
  list(fits = all_fits, records = records, select = rescue_select(records, loglik_tol, min_aligned), error = "")
}

# 答える問い: 最適化ごとの記録の JSON(配列。何も当てていなければ空)。
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

# ---- 縮退の各段の記録(PLAN-041 I3 / ADR-124 D5)-----------------------------

# 答える問い: この段のこの当てはめ(full / add)の判定は何だったか。JSON の 1 要素(1 行)にする。
# 閾値は変えず、判定の中身(singular・警告数・logLik の改善・可動量・例外)を残すだけである。
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

run_one <- function(csv_path, out_path, loglik_tol, beta_tol, max_level, use_refit, allfit) {
  d <- read.csv(csv_path, stringsAsFactors = TRUE)
  d$coverage <- relevel(d$coverage, ref = "id")   # §3.2: id を基準とする treatment coding
  cov_levels <- levels(d$coverage)
  for (cl in cov_levels) d[[indicator_name(cl)]] <- as.numeric(d$coverage == cl)

  level <- 0L
  n_errored <- 0L          # 例外で落ちた当てはめの数(全水準の合計)
  first_error <- ""        # 最初の例外の文面
  records <- character(0)  # 段ごと・full/add ごとの判定(D5)
  repeat {
    # ★判定はペア単位である(ADR-059 の付帯条件)。片方だけ縮退させると
    # ランダム構造が食い違い、df = 2 の LRT が §3.2 の検定でなくなる。
    res_full <- judge_one(formula_at(level, "task * coverage", cov_levels), d, loglik_tol, beta_tol)
    res_add <- judge_one(formula_at(level, "task + coverage", cov_levels), d, loglik_tol, beta_tol)
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

  # ★床(level = max_level)でも ADR-059 の判定が収束しない、または例外で落ちた表。
  # `failed` は収束しなかった場合と例外の場合の両方で TRUE である(`judge_one` / `errored_result`)。
  floor_failed <- res_full$failed || res_add$failed
  # ★ADR-129 決定2: 床の土台の glmer が例外で落ちたときは allFit を呼べない。救わずに当てはめ失敗とし、別に記録する。
  floor_base_errored <- floor_failed && (res_full$errored || res_add$errored)

  # ★ADR-128 決定1 (A3): 床で失敗した表に、床の式(full・add)へ allFit を 1 段足す(PLAN-043 I1)。
  # full と add の両方が収束と言えて初めて救う。**床で失敗しない表はここを通らない**(LRT は 1 ビットも変わらない)。
  allfit_attempted <- floor_failed && !floor_base_errored && level >= max_level
  af_full <- NULL
  af_add <- NULL
  rescued <- FALSE
  if (allfit_attempted) {
    af_full <- rescue_one_formula(formula_at(level, "task * coverage", cov_levels), d, allfit$optimizers,
                                  allfit$start_from_mle, loglik_tol, allfit$min_aligned)
    af_add <- rescue_one_formula(formula_at(level, "task + coverage", cov_levels), d, allfit$optimizers,
                                 allfit$start_from_mle, loglik_tol, allfit$min_aligned)
    rescued <- af_full$select$satisfied && af_add$select$satisfied
  }
  # p 値を出せないのは、救えなかった(または救う手段が無かった)場合だけ。LRT は集計側が全シートで非棄却に数える(ADR-128 決定1 (A2))。
  fit_failed <- floor_failed && !rescued

  # ★当て直した場合にどちらを LRT に入れるかを ADR-059 は明示していない(仕様の穴)。
  # 既定は当て直したほう —— 最適解から始めた分だけ収束しており、手続きが
  # 「当て直す」で終わっている以上そちらが最終的な当てはめだからである。
  # 検査3 の F62 ではこの選択が Chisq を動かす量は中央値 5.9e-05 であった。
  # config で切り替えられるのは、人間が別の解釈を採れるようにするためである。
  pick <- function(res) if (res$refit_done && use_refit) res$refit else res$fit0
  # LRT に入れる当てはめの対。救った表は allFit で揃った最適化のうち logLik 最大のもの(full・add それぞれ)
  used_full <- if (rescued) af_full$fits[[af_full$select$best]] else if (fit_failed) NULL else pick(res_full)
  used_add <- if (rescued) af_add$fits[[af_add$select$best]] else if (fit_failed) NULL else pick(res_add)
  an <- if (fit_failed) NULL else anova(used_add, used_full, test = "LRT")
  interaction_fields <- if (fit_failed) character(0) else interaction_coefficients(used_full, d)
  lrt_field <- function(col, fmt) {
    if (is.null(an)) "null" else jnum(an[[col]][2], fmt)
  }
  # ★ADR-129 決定3: 当てはめ失敗の反復の記述の p 値(ADR-059 の当て直しの後の当てはめの LRT)。どの門にも使わない。
  # 床の土台が例外のときは当てはめが無いので null。`p_value` は null のまま。
  an_descriptive <- if (fit_failed && !floor_base_errored) {
    tryCatch(anova(pick(res_add), pick(res_full), test = "LRT"), error = function(e) NULL)
  } else NULL
  p_descriptive_field <- if (is.null(an_descriptive)) "null" else jnum(an_descriptive[["Pr(>Chisq)"]][2], "%.10g")
  select_field <- function(af, key) if (is.null(af)) "null" else jnum(af$select[[key]])
  best_field <- function(af) if (is.null(af)) jstr("") else jstr(af$select$best)

  fields <- c(
    kv("csv", jstr(basename(csv_path))),
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

loglik_tol <- as.numeric(man$loglik_tolerance)
beta_tol <- as.numeric(man$beta_move_tolerance)
max_level <- as.integer(man$max_reduction_level)
use_refit <- identical(tolower(man$use_refit_for_lrt), "true")

# ★床の allFit の段(PLAN-043 I1 / ADR-129 決定1)。manifest に無い・食い違えば、1 枚も当てる前に止まる。
for (key in c("allfit_optimizers", "allfit_start_from_mle", "allfit_min_aligned",
              "expected_r_version", "expected_lme4_version")) {
  if (is.null(man[[key]]) || !nzchar(man[[key]])) stop(sprintf("manifest に %s が無い(床の allFit の段に要る)", key))
}
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
  run_one(csv_path, out_path, loglik_tol, beta_tol, max_level, use_refit, allfit)
  cat(sprintf("%s -> %s (%.1fs)\n", basename(csv_path), basename(out_path),
              proc.time()[["elapsed"]] - t0))
}
cat("done\n")
