# code/analysis/power_sim_fit.R — 検出力シミュレーションの当てはめ側(§6.3 手続き3b)。
#
# 答える問い: 「合成表 1 枚に対して、Documents/05_STATISTICS.md §3.2 の
# `fit_full` / `fit_add` の対を ADR-059 の縮退カスケードごと当てると、
# LRT(df = 2。T1 x T2。ADR-112)の p 値と、縮退が発火したかどうかは何になるか」
# ★ADR-114 決定5: 平行性の TOST のために、`fit_full` の交互作用の係数(`task:coverage`。処理対比・
# 基準 = タスク型の最初の水準 x 被覆の `id`)の推定値と Wald SE も出す。**ランダム構造と LRT は変えない。**
#
# **§3.2 の R コードがそのまま実行物になる**ことが ADR-058 決定1 の採択理由の 1 つである。
# したがって下の RANDOM_BY_LEVEL の level 0 は §3.2 の式をそのまま写している。
# 書き換えるときは §3.2 と ADR-064 決定4 / ADR-066 決定1 を先に読むこと。
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
# 縮退順序は ADR-065 決定2: template -> coverage のランダム傾き -> item。
# level 0 が §3.2 そのもの。level が上がるほど落としたものが増える。
RANDOM_BY_LEVEL <- c(
  "(0 + coverage | seed) + (1 | item) + (1 | template)",
  "(0 + coverage | seed) + (1 | item)",
  "(1 | seed) + (1 | item)",
  "(1 | seed)"
)
REDUCTION_LABEL <- c("none", "drop_template", "drop_coverage_slope", "drop_item")

formula_at <- function(level, fixed) {
  as.formula(paste("is_rule ~", fixed, "+", RANDOM_BY_LEVEL[[level + 1L]]))
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
  x <- gsub("\\\\", "/", as.character(x))
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

# ★ADR-059 は警告(収束しない)だけを縮退の引き金にしている。**`glmer` が例外で落ちる場合
# (`Downdated VtV is not positive definite` など)は書かれていない**(2026-10-02。PLAN-034 I7 の
# スモークで、誤指定のシートの小さな表で観測した)。落ちたまま R を止めると、同じ表を決定的に
# 当て直すだけの再開でも同じ所で止まる。**暫定の扱い: 例外も「収束しなかった」と同じ
# 引き金とし(= 縮退へ進む)、数と最初の文面を出力に残す(黙って数えない)。**
# 最後の水準でも落ちたら p 値は null になり、集計側(power_sim.py)が止まる。
# ★この扱いは人間の確認待ち(`logs/OPEN-ITEMS.md`)。ADR-059 の追記が要るかもしれない。
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

# ---- 1 枚の表 --------------------------------------------------------------

run_one <- function(csv_path, out_path, loglik_tol, beta_tol, max_level, use_refit) {
  d <- read.csv(csv_path, stringsAsFactors = TRUE)
  d$coverage <- relevel(d$coverage, ref = "id")   # §3.2: id を基準とする treatment coding

  level <- 0L
  n_errored <- 0L          # 例外で落ちた当てはめの数(全水準の合計)
  first_error <- ""        # 最初の例外の文面
  repeat {
    # ★判定はペア単位である(ADR-059 の付帯条件)。片方だけ縮退させると
    # ランダム構造が食い違い、df = 2 の LRT が §3.2 の検定でなくなる。
    res_full <- judge_one(formula_at(level, "task * coverage"), d, loglik_tol, beta_tol)
    res_add <- judge_one(formula_at(level, "task + coverage"), d, loglik_tol, beta_tol)
    for (res in list(res_full, res_add)) {
      if (res$errored) {
        n_errored <- n_errored + 1L
        if (!nzchar(first_error)) first_error <- res$error_message
      }
    }
    if (!(res_full$failed || res_add$failed) || level >= max_level) break
    level <- level + 1L
  }

  # ★当て直した場合にどちらを LRT に入れるかを ADR-059 は明示していない(仕様の穴)。
  # 既定は当て直したほう —— 最適解から始めた分だけ収束しており、手続きが
  # 「当て直す」で終わっている以上そちらが最終的な当てはめだからである。
  # 検査3 の F62 ではこの選択が Chisq を動かす量は中央値 5.9e-05 であった。
  # config で切り替えられるのは、人間が別の解釈を採れるようにするためである。
  pick <- function(res) if (res$refit_done && use_refit) res$refit else res$fit0
  # 最後の水準でも例外で落ちた場合は LRT を作れない。p 値は null で出し、集計側が止まる
  errored_final <- res_full$errored || res_add$errored
  an <- if (errored_final) NULL else anova(pick(res_add), pick(res_full), test = "LRT")
  interaction_fields <- if (errored_final) character(0) else interaction_coefficients(pick(res_full), d)
  lrt_field <- function(col, fmt) {
    if (is.null(an)) "null" else jnum(an[[col]][2], fmt)
  }

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
    kv("n_errored_fits", jnum(n_errored)),
    kv("first_error", jstr(first_error)),
    kv("chisq", lrt_field("Chisq", "%.10g")),
    kv("df", lrt_field("Df", "%.14g")),
    kv("p_value", lrt_field("Pr(>Chisq)", "%.10g"))
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

for (job in vals_for(lines, "fit")) {
  parts <- strsplit(job, "|", fixed = TRUE)[[1]]
  csv_path <- trimws(parts[1])
  out_path <- trimws(parts[2])
  if (file.exists(out_path)) {
    cat(sprintf("%s exists, skipping\n", basename(out_path)))
    next
  }
  t0 <- proc.time()[["elapsed"]]
  run_one(csv_path, out_path, loglik_tol, beta_tol, max_level, use_refit)
  cat(sprintf("%s -> %s (%.1fs)\n", basename(csv_path), basename(out_path),
              proc.time()[["elapsed"]] - t0))
}
cat("done\n")
