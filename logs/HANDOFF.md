# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-10(その32)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN が 1 本終わった**(ADR-071 の実装が完了)

---

## ★先に人間が決めること(これが無いと次の作業は始まらない)

**★★F125: `configs/exp_phase1_main.yaml` のままでは順5 が起動しない。**
`eval.temperature`(468 行)と `eval.num_repeats`(469 行)が `null` で、
`python -m code.eval.sweep --config configs/exp_phase1_main.yaml` は `code/eval/model.py` の
`load_generation_settings` で `ConfigError` を出す(**重みを読む前**。`--dry-run` は通る)。

- **ADR-042 はどちらの値も決めていない**(決定2 = `do_sample: false` が正本 / 決定3 = `num_repeats` の意味だけ)
- `plans/PLAN-001` §5.6 に**提案値**(`temperature` 0 / 本実行 `num_repeats` 1)があるが、**承認の記録は見つからない**
- **実装は `num_repeats = 1` 以外を受け付けない**(繰り返し生成は未実装)
- **エージェントは値を書いていない**(`CLAUDE.md` §8)。正本は `logs/OPEN-ITEMS.md` の ★★F125

あわせて **★ADR-071 の実装判断 3 件**(`logs/OPEN-ITEMS.md`)に異議が無いかを見てほしい:
(1) `shell_n_items ≠ n_items_per_radius` なら止める / (2) 定義 A の格子殻は全シード合算の率 /
(3) `shell_*` の無い config(`smoke.yaml` を含む)では掃引も dry-run も止まる。

---

## 人間が ★F125 を決めた後のプロンプト(RUNNER)

あなたは **RUNNER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

### このセッションでやること(1 つだけ)

**順5(桁数掃引)を GPU で回す。**手順の正本は **`plans/PLAN-014` §5**(= `infra/RUNPOD.md` §4 手順 5b)。

1. 人間が決めた ★F125 の 2 欄が **ADR として `logs/DECISIONS.md` に残り**、
   `configs/exp_phase1_main.yaml` に入っていることを確かめる(**無ければ止まって人間に上げる**)
2. ローカルで `python -m code.eval.sweep --config configs/exp_phase1_main.yaml --dry-run` が通ること
   (**20,000 項目** = 腕1 13,000 + 腕2 7,000)
3. **RunPod のポッドを立てる前に、時間単価を人間に示して承認を取る**(GPU 承認は 2026-09-06 に出ているが、
   見積りは 1.5h に対するもので、ADR-071 で **2.5h** に増えた。**10h の門は超えない**)
4. `plans/PLAN-014` §5 の手順 1〜5(`--run-kind sweep` を必ず付ける)
5. **終わったらポッドを停止したことを確かめる**(`CLAUDE.md` §9)。`runs/*/metrics.json` と `config.yaml` はコミット

### 読むべき範囲

- `plans/PLAN-014-order5-launch-preconditions.md` §5(**2026-09-10 の追記を含む**)
- `infra/RUNPOD.md` §3・§4・§7(`grep -n` → `sed -n`)
- **全文 `cat` しない**(`CLAUDE.md` §10.1)。`runs/*/log.txt` と `predictions/` も全文を読まない

### やってはいけないこと

- **`M*` を決めない / `extrapolation_radius` に値を書かない**(規則2 を当てるのは人間。ADR-041 / ADR-045)
- **掃引表の解釈をしない**(`CLAUDE.md` §8)。**判定の材料は `metrics.json` の `quadrant` だけ**であり、
  `by_radius`(累積)と `grid_shell`(定義 A)は記述である(ADR-071 決定1。`roles` に書いてある)
- **★F125 の 2 欄をエージェントが埋めない**
- **`θ = 0.70` の根拠を代筆しない**
- **ポッドを起動したまま放置しない**

---

## 直前セッション(その32)で確定したこと(すべてファイルに書き込み済み)

- **ADR-071 を実装した**(`code/eval/battery/magnitude_sweep.py` / `code/eval/sweep.py`)。
  **腕1 = `R(M)` の一様抽出 13,000 項目(`build_items` は無変更。sha256 を回帰テストで固定)= 記述 /
  腕2 = `Q(M)` 7 水準 × 200 × 5 = 7,000 項目 = 判定の材料。**`metrics.json` は別ブロック(`roles` 付き)
- `Q(M)` は **`label_main_coverage` が `extrap_magnitude` を返す組を `R(M)` から全列挙**して作る(式を書かない)
- config の `shell_radii` / `shell_judgement_radii` は **導出値と突き合わせ、食い違えば run ディレクトリを作る前に止まる**
- `plans/PLAN-001` §4.1.1 手続き 1〜3 / `plans/PLAN-014` §5 を改訂(打ち消し線 + 理由 + 日付)
- `pytest code/tests -q` = **956 passed**(914 → +42)。前回 1 度落ちた `test_power_sim.py::test_run_fits_writes_one_manifest_per_shard`
  は今回落ちていない(**原因は未特定のまま**。また落ちたら追う)

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8。索引は `logs/OPEN-ITEMS.md`)

- **★★F125**(上。**順5 のクリティカルパス**)/ **★ADR-071 の実装判断 3 件**
- **★`θ = 0.70` の根拠**(ADR-041 決定2 の要求。**値は確定**)
- **★F104**(`s2_item` / `s2_tmpl` の取得元。`plans/PLAN-019` §10.13.5)/ **★F114 の実行先**(★F104-a に従属)
- **順6 の GPU 承認** / **Phase 1 本実験 40 run の GPU 構成** / **LoRA グリッド**
- **N5**(解析門の閾値)/ **★C** / **★E** / **★L(d)** / **E-5 (b)** / **★2** / **PLAN-018 §4.3**
- **`Documents/09_PAPER_PLAN.md` と `00_OVERVIEW.md:7` が再設計前のまま**
