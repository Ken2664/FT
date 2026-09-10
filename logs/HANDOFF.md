# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-10(その36)/ 直前セッションの役割: RUNNER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(context-guard が約 182k で警告)。**ポッドは停止済み(`EXITED`)**

---

あなたは **RUNNER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1 つだけ)

**順5 の掃引 run `20260910_104249_sweep_m` の結果を、`metrics.json` から 4 値分解を揃えて run_id とセットで人間に報告する。**
**解釈しない・`M*` を置かない・`extrapolation_radius` に値を書かない**(`CLAUDE.md` §8。規則2 を当てるのは人間)。

1. `runs/20260910_104249_sweep_m/metrics.json`(コミット `38a9aa6`)を `python -c` でキーだけ読む。
   **判定の材料は `quadrant`(Q(M)。7 水準 × 200 × 5)**、`by_radius` / `grid_shell` は記述(`roles` を見る)。
   各水準の correct / rule / other_error / parse_fail(**合計 1.0 を確かめる**)とシード間 SD、`timing` を表にする
2. **`CLAUDE.md` §7 の点検**: `other_error_rate` だけが高い水準 / `parse_fail_rate` の偏り / 予測と合いすぎていないか。
   疑わしければ `predictions/`(**開発機にある。git 管理外**)を `grep -c` / `python -c` で数える(全文を読まない)
3. 報告を `STATE.md`「わかっていること」に run_id とセットで書く(**数値は run_id と切り離さない**)。
   `logs/OPEN-ITEMS.md` の停止中ポッドの行に **`omjvbdanmbrzc8`**(EUR-IS-1 / ポッドローカル 60GB)を足す
4. 時間があれば `infra/RUNPOD.md` を直す(§8 の create-pod の記述 / PEP 668 の venv / bundle の `-b main` /
   **掃引の preflight でも `train.jsonl` が要る** —— `.gitignore` 対象で clone に無い。今回は人間の判断で scp した)
5. `logs/CHANGELOG.md` → コミット

## 直前セッション(その36)で確定したこと(すべてファイルに書き込み済み)

- **掃引 run `20260910_104249_sweep_m` は `SWEEP_EXIT=0`**(10:45:06Z → 12:29Z。ポッド `omjvbdanmbrzc8` / RTX 4090 / EUR-IS-1)。
  run ディレクトリは開発機に丸ごと回収済み(predictions 100 ファイル・`log.txt` は git 管理外)。**結果はまだ誰も読んでいない**
- `git_sha.txt` = `486d7ff`(origin にある)/ `dirty: true`。**`git_diff.patch` は 0 バイト**
  (preflight の WARN = run ディレクトリ自身の未追跡 1 件と同じ原因と見ている。未検証)
- ポッド上の準備: pytest 957 passed / lock と pip freeze 187 行一致 / 重み revision `0e9e39f…` 一致 / preflight FAIL 0
- **ADR-073 追記(その36)**: EU-RO-1 + ボリューム案は人間が承認したが在庫なしで不使用 / `train.jsonl` を scp(人間の判断)
- **GPU の稼働は通算 約 2.59 時間**(426 + 790 + 8,094 秒)。ポッドは `EXITED`

## やってはいけないこと

- **`M*` を決めない / 掃引表を解釈しない / 「θ を割った水準」を指摘して `M*` を示唆しない**(規則2 の適用は人間)
- **`predictions/` / `log.txt` を全文読まない** / **ポッドを start しない**(用は済んだ)/ **terminate しない**(人間が決める)

## 未解決 / 人間の承認待ち(索引は `logs/OPEN-ITEMS.md`)

- **★`M*`**(この run の `quadrant` に規則2 を当てる)/ **`cost.txt`**(人間)/
  **停止中ポッド 3 台の terminate**(`zxwdkgxutbuoph` / `46pggs1odwb09r` / `omjvbdanmbrzc8`)
- **★`θ = 0.70` の根拠** / **★F104** / **★F114 の実行先** / **順6 の GPU 承認** / ほかは `STATE.md`「次のアクション」
