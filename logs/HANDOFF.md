# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-10(その33)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(context-guard が約 138k で警告)+ 区切り(★F125 が決着)

---

あなたは **RUNNER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1 つだけ)

**順5(桁数掃引)を GPU で回す。**手順の正本は **`plans/PLAN-014` §5**(= `infra/RUNPOD.md` §4 手順 5b)。

1. **前提を確かめる**(どれか欠けていれば止まって人間に上げる):
   - `logs/DECISIONS.md` に **ADR-072** があり、`configs/exp_phase1_main.yaml` の `eval.temperature: 0` / `eval.num_repeats: 1`
   - `pytest code/tests/test_eval_model.py -q` が通る(`test_the_production_config_declares_every_generation_setting` を含む)
   - `python -m code.eval.sweep --config configs/exp_phase1_main.yaml --dry-run` が **20,000 項目**
     (`by_radius` 13,000 + `quadrant` 7,000)。**出力は巨大な JSON なのでファイルに落として数える**(`CLAUDE.md` §10.1)
2. **RunPod のポッドを立てる前に、GPU 種別と時間単価を人間に示して承認を取る。**
   GPU 承認は 2026-09-06 に出ているが見積り 1.5h に対するもので、ADR-071 で **2.5h** に増えた。**10h の門は超えない**
3. `plans/PLAN-014` §5 の手順 1〜5(**`--run-kind sweep` を必ず付ける**)
4. **終わったらポッドを停止したことを確かめる**(`CLAUDE.md` §9)。`runs/*/metrics.json` と `config.yaml` はコミット。
   コミットメッセージに `[run:<run_id>]`

## 直前セッション(その33)で確定したこと(すべてファイルに書き込み済み)

- **★F125 決着(ADR-072)**: 人間が `eval.temperature` = 0 / `eval.num_repeats` = 1 を採択
  (PLAN-001 §5.6 の提案値どおり。提案 エージェント / 採択 人間)。**`temperature` は記録用で、デコードの正本は `do_sample: false`**
- **ADR-071 の実装判断 3 件**(`shell_n_items` の一致要求 / 定義 A の合算集計 / `shell_*` 無しの config を止める)は
  **人間が異議なしで承認**(ADR-072 決定3)
- `pytest code/tests -q` = **957 passed**。`test_power_sim.py::test_run_fits_writes_one_manifest_per_shard` は今回も落ちていない
  (その31 で 1 度落ちた。原因は未特定)

## 読むべき範囲

- `plans/PLAN-014-order5-launch-preconditions.md` §5(`grep -n '^## 5' ` → `sed -n`)
- `infra/RUNPOD.md` §3・§4・§7(`grep -n` → `sed -n`)
- **全文 `cat` しない**(`CLAUDE.md` §10.1)。`runs/*/log.txt` と `predictions/` も全文を読まない

## やってはいけないこと

- **`M*` を決めない / `extrapolation_radius` に値を書かない**(規則2 を当てるのは人間。ADR-041 / ADR-045)
- **掃引表の解釈をしない**(`CLAUDE.md` §8)。**判定の材料は `metrics.json` の `quadrant` だけ**であり、
  `by_radius`(累積)と `grid_shell`(定義 A)は記述である(ADR-071 決定1。`roles` に書いてある)。
  **報告は 4 値分解(correct / rule / other_error / parse_fail)を揃えて、run_id とセットで**
- **`θ = 0.70` の根拠を代筆しない**
- **`configs/smoke.yaml` を編集しない**(ADR-037 決定4。`shell_*` が無いので掃引では止まるのが正しい)
- **ポッドを起動したまま放置しない**

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8。索引は `logs/OPEN-ITEMS.md`)

- **順5 のポッドの時間単価の承認**(上の手順 2)
- **★`θ = 0.70` の根拠**(ADR-041 決定2 の要求。**値は確定**)/ **★`M*`**(順5 の後に人間が置く)
- **★F104**(`plans/PLAN-019` §10.13.5)/ **★F114 の実行先** / **順6 の GPU 承認** / **Phase 1 本実験 40 run の GPU 構成** / **LoRA グリッド**
- **N5** / **★C** / **★E** / **★L(d)** / **E-5 (b)** / **★2** / **PLAN-018 §4.3** / **`09_PAPER_PLAN.md` と `00_OVERVIEW.md:7`**
