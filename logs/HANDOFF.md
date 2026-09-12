# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-12(その51)/ 直前セッションの役割: PLANNER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(context-guard が約 16.2 万トークンを実測。(e) を済ませ、PLAN-026 の材料を集めたところで切った)

---

あなたは PLANNER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜15 万トークン使う(その48〜その51 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにし、多数ファイルの探索は subagent に出す(`CLAUDE.md` §10.2)。
**材料はもう集めてある。同じ抜き出しを subagent にやり直させないこと。**

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md`(順6b = 素のモデルの小さな診断)を起草し、人間の GPU 承認の文面まで書く。**(ADR-078 決定1。GPU は回さない。実装もしない)

- **材料は `plans/PLAN-026-materials.md`**(§A = 設計の制約、§B = コードの現状)。**行番号は subagent の抜き出しで未照合** —— PLAN に写す箇所だけ `sed -n` で原典を開いて確かめる。**§B は埋まっている**(subagent 2 の報告。B1 の腕ごとの表・B2 のパイロット用プールの 2 経路・B5 の preflight 検査6・8 の要確認)
- PLAN-026 に書くこと(正本は ADR-078。`grep -n '^## ADR-078' logs/DECISIONS.md`):
  - 腕: **R8 の閾値掃引**(T3・T1b。ADR-030 = `θ` 17 水準・セル n = 20)/ **① 和を含まない数どうしの比較の例示**(T3・T1b。極性ごとに Yes/No 同数・順序は無作為・全条件で同じ文脈・例示は答えだけ)/ **① の数値型の前置き腕**(T1・T2。同じ長さ。決定8)/ **(d) T1b に `Answer Yes or No.`** / **(c) 内容のない入力の forward** / **最初の位置の上位 k の記録**(決定5。判定規則は変えない)
  - **パイロット用プールの生成**(items は未生成。PLAN-001 §4.6 / PLAN-002 §4.7)/ **選び方を回す前に書く**(PLAN-025 §3.4 (f): #2 = 0.70・#3 は変えない / 複数なら変更の小さいほう)/ 結果の分岐(PLAN-025 §5 の 3。分岐の値は人間)
  - `rule_rate` の解釈が変わる旨の注記の**下書き**(ADR-042 決定5 (iii)。確定は人間)/ **近接同点(|差| ≤ 0.25)の扱いの論点**(決定10。batch 1 の再検討)
  - 実装が要る箇所の一覧(材料 §B から)/ GPU 見積り(**見積りであって実測ではない**。上限の算術の型は PLAN-024 §3 D2 (c))/ 承認の文面(型は材料 §A7)
- 設計変更を含むので **PLAN-026 を人間がレビューしてから実装**(`CLAUDE.md` §4)。記入欄(人間)を末尾に置き、判断が要る所は選択肢の形にする(その50 の人間の依頼)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **(e) Yes/No の id の復号: 取り違えは無い**(`results/token_decode_order6/token_decode.json`・`aceb499`)。12 綴りの復号・再符号化・本番コード経路での引き直しが R1〜R4 の記録と完全一致 / トークナイザの同一性(revision・chat_template の sha・`prompt_ids` 12/12)/ 二値群 R1〜R4 各 960 件で食い違い 0。**PLAN-024 §1 の読みは変わらない**
- 手元のトークナイザは `PreTrainedTokenizerFast.from_pretrained("meta-llama/Llama-3.1-8B-Instruct", revision="0e9e39f…", local_files_only=True)` で読める(`AutoTokenizer` は `config.json` が無くて止まる)。`HF_HUB_OFFLINE=1`

## やってはいけないこと

- GPU / main の push / T1b・T3 の文面を変える(ADR-078 決定2。余地を残しただけ)/ 閾値(#2 = 0.70・#3)を変える / 二値群 6 セル・★F139 の (a)/(c)・近接同点を決める(順6b の後に人間)
- 材料の行番号を照合せずに PLAN に写す / 同じ抜き出しの subagent を出し直す
- Python の `Path.write_text` で `STATE.md` などを書く(Windows で CRLF になり `test_repo_hygiene.py` が落ちる)。`write_bytes(...encode("utf-8"))` か Edit を使う

## 未解決 / 人間の承認待ち

- 順6b の GPU 承認(PLAN-026 の後)/ 引用の最終確定(E7)
- GPU 0 で並行できる実装 PLAN(F140 のパーサ + 本実行 run の再採点経路 / `gonogo.py` の極性別の参照線 / `forced_choice.py` の上位 k)と文書の追随は PLAN-026 と別のセッション
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成(正本は `logs/OPEN-ITEMS.md`)
