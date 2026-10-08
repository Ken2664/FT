# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-08(その163)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN 完了(PLAN-043 §4 を人間が決め、ADR-129 で採択。commit `a60422b`)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — 採択済みの PLAN の実装とテスト(`10_CONTEXT_POLICY.md` §7 の「実装・集計」の行。PLAN-043 §6 も「IMPLEMENTER = Sonnet で可」としている)。**統計の判断が出てきたら止めて PLANNER(Opus)へ回す**

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**`plans/PLAN-043-adr128-fit-rescue-and-gates.md` の I1〜I10 を、ADR-129 の値で実装する。完了条件は PLAN-043 §10 のうち次の 3 つ: `pytest code/tests -q` が通る / 合成の反復で R のスモークが通る / `--dry-run` が通る。**
- 手順は PLAN-043 §6 のとおり: skill `code-style` → I1 → I2 → I3 → I4 → I5(R の出力の欄を先に決め、python の読みは後)→ I10 → I6・I7・I8 → I9(I9 は別の commit)
- **I9(PB の計時)はスクリプトを作るところまで。実行する前に人間に日時を聞く**(ADR-129 決定6「日時は人間が決める」。§10 の「計時を回す」は人間の合図の後)
- 最後に `logs/CHANGELOG.md`・`STATE.md`・PLAN-043 §10・§12 を更新して commit

## 直前セッションで確定したこと(ADR-129。`logs/DECISIONS.md` の末尾)

- `allFit`(lme4 2.0.6): `bobyqa`・`Nelder_Mead`・`nlminbwrap`・`nloptwrap.NLOPT_LN_NELDERMEAD`・`nloptwrap.NLOPT_LN_BOBYQA` を名前で列挙し、`start_from_mle = FALSE`。1 つでも使えなければ止まる。R / lme4 の版を出力に残し、診断(R 4.6.1 / lme4 2.0.6)と違えば止まる
- 床の土台の `glmer` が例外で落ちたら、救わずに当てはめ失敗とし、件数を別に記録する
- 失敗した反復: 床が例外でなければ、当て直しの後の LRT を `p_value_failed_descriptive` に残す(`p_value` は null)。点ごとに失敗した反復だけの棄却率と CP95 を出し、どの門にも使わない
- 実行可能性の門(CP95 下端 > 0.10): 全シート・全点が対象((i) per_cell・`p1_tau` を含む)。誤指定の 3 枚はまとめて回した後に過誤の門と一緒に判定し、P1・`p1_tau`・P1⁻・P0 は各シートの後に判定する。閉じたら次のシートの前で止まる(終了コード 4)
- run3 の `rng_seed` = **20261008**。config に入れて commit してから起動する(起動は人間)。tag は打たない
- PB の計時: lme4 だけで simulate → refit を手書きする。合成の反復(番号 ≥ 9000)の 4 表(P0 の (80, 1.0) から 2 枚・誤指定 `tau` 1.0 から 2 枚)× B 20 = 160 本。出すのは秒数と当て直しの失敗数だけ(p 値は出さない)。縮退と `allFit` はしない
- ADR-128 の方針(PLAN-043 §2 の P1〜P7)は前提として変えない

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-043-*.md` §2・§3・§3.1・§6・§7・§10(`grep -n '^## '` で位置を取る)
- `code/analysis/power_sim_fit.R`(**「# ---- driver」より上は `fit_failure_diagnosis.R` が借りている**。PLAN-043 §6 の 1)/ `code/analysis/power_sim.py` / `configs/power_sim.yaml` / `infra/power_sim_night/` / `code/tests/test_power_sim*.py`
- I7 の打ち消し線: `Documents/05_STATISTICS.md` §3.2・§6 / `plans/PLAN-040` §11・付録 A.4 / `logs/DECISIONS.md` の ADR-059・123・124・125 の**ステータスの行の末尾だけ**(本文は変えない)
- 参考: PLAN-042 §7(D1 の `allFit` の記録)/ `code/analysis/fit_failure_diagnosis.R` の `run_allfit`

## やってはいけないこと

- ADR-129 の値を変える。最適化を足したり減らしたりする。`start_from_mle` を変える(PLAN-043 罠3)
- 成功した反復の LRT を 1 ビットでも変える(罠6。床で失敗しない表の `p_value` が前と一致することをスモークで確かめる)
- `rng_seed` を commit する前に試し回しする(罠4。`--dry-run` は当てはめないので可)
- run2 の 100 反復で新しい規則の門を判定する / run2 の表を書き換える(罠1)
- run3 の起動・夜用タスクの登録・PB の計時の実行(人間の合図なし)・push・tag
- `.md` は LF、Python で書くときは `newline` を指定する(memory)

## 未解決 / 人間の承認待ち

- run3 の起動(夜用タスクの登録。run2 の登録が残っていれば無効にするのは人間)/ PB の計時の日時
- push(`01cf60f` 以降の main)と G2-1 承認 → S4
- PB の反復数と、漸近 χ² と食い違ったときの扱いは S5 / 特異な分散成分(32 件)は未確認 / `run2/misspecification_seed_per_cell/frames/` の残骸 46 本と未追跡の `.claude/commands/` は人間
