# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-28 / 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 368k で警告)

---

あなたは RUNNER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**このセッションでだけ RunPod MCP を有効にしてください**(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**順1b(本番モデルによるスモーク)を実機で回す。**
**手順は `infra/RUNPOD.md` §4「順1b の手順(★これが正本)」の 1〜9 をその順に実行する。**
この HANDOFF に手順を書き写さない —— 写しがあると、どちらが正本か分からなくなる。

**完了条件(判定できる形)**:

1. `runs/<id>/` が **2つ**できている(`smoke1b` = まとめ幅4 / `smoke1b_b1` = まとめ幅1)。
   どちらにも `config.yaml` / `git_sha.txt` / `env.txt` / `timestamp.txt` /
   `metrics.json` / `predictions/` / `log.txt` / `token_boundary.json` がある
2. **`compare_runs` の突き合わせが取れている。**合否は **ADR-040 決定1**:
   **全19項目で「4値分類」と「抽出された整数値」が一致(19/19)**。
   **生成文字列の一致率は記録のみで合否に使わない**(決定2)。
   割れたら **決定3 の3段**で降りる。**割れたまま先に進まない**
3. `token_length.json` が両方の run にある(**答えのトークン長の分布**。#20 の材料)
4. **`metrics.json` の `timing` を読んで、秒数を run_id とセットで報告する**
   (`eval.batch_size` の材料。ADR-040 決定6。**値を決めるのは人間**)
5. **ポッドを停止した**ことを確認した(`CLAUDE.md` §9)

## 直前セッションで確定したこと

- **ADR-040〜043 のコード・文書への反映6件が完了した**(commit `00c4fa1` / `4fd6733` /
  `76bc6fb` / `eec6d78`)。`pytest code/tests -q` → **686 passed**
- **`runs/<id>/metrics.json` に `timing` が入るようになった**(ADR-040 決定6)——
  合計 / **重みの読み込み** / **生成** / 1項目あたり秒。**順1b の前提はこれで満たされた**
- **`eval.do_sample` が config の必須項目になった**(ADR-042 決定2。`do_sample: false` が正本)。
  `configs/smoke1b.yaml` / `smoke1b_b1.yaml` には追加済みで、**そのまま回せる**
- **gated アクセスは承認済み**(2026-08-28。人間の報告)。~~403~~ は解消している
- **ポッド `hikss5upj15vp2`**(RTX 4090 24GB / EU-RO-1 / ネットワークボリューム `r963j7swke`)は
  `EXITED`。**`start-pod` で再開できる。IP とポートは再開のたびに変わるので `list-pods` で引き直す。**
  `/workspace` に repo(`/workspace/translesion`)・venv(`/workspace/venv`)・HF トークンが残っており、
  **clone と bootstrap はやり直さなくてよい**
- **実験は1つも回していない。`results/` は空。GPU 時間 0**

## 触ってよいファイル / 読むべき範囲

- **`infra/RUNPOD.md` §4「順1b の手順」**(行 200 付近から)。**全文 cat せず
  `sed -n '200,300p'` で読む。**§3(preflight)と §7(cost.txt の書式)も必要になったら
  `grep -n` で節を特定してから読む
- `plans/PLAN-004-phase0-route.md` §3「順1b」の完了条件6つ
- `configs/smoke1b.yaml` / `configs/smoke1b_b1.yaml`(**書き替えるのは `model.revision` だけ**)
- 出力は**全文を読まない**。`tail -n` / `grep -n` / `jq` で必要な行だけ(`CLAUDE.md` §10.1)

## やってはいけないこと

- **順1b の数値を実験結果として扱わない**(ADR-037 決定5・6)。`results/` に置かない。
  健常時スコア・test-retest・プロンプト感受性(Go/No-Go #0〜#3)の材料にしない。
  **文書に転記してよいのは (c) 答えのトークン長と、`timing` の秒数だけ**(run_id とセットで)
- **`max_new_tokens` / `eval.batch_size` の値を config や ADR に書き込まない。**
  材料を人間に上げるところまでがエージェントの仕事(ADR-042 決定6 / ADR-040 決定6)
- **`configs/smoke.yaml` を触らない**(ADR-037 決定4。門の回帰テストが拠る固定点)
- **`data/raw/` を書き換えない**
- **データ再生成の段(2b)を飛ばさない。**評価プールの実体は git に無く、飛ばすと
  `load_pool_items` が落ちる。再生成後、**動いてよい差分は `created_at` と `git_commit` だけ**。
  ハッシュ類が動いていたら先へ進まずに原因を見る
- **ポッドを起動したまま放置しない**(`CLAUDE.md` §2)

## 未解決 / 人間の承認待ち

- **`model.max_new_tokens`**(順1b の答えトークン長の後)/ **`eval.batch_size`**(順1b の壁時計時間の後)
- **`θ` の格子点 / 水準あたり項目数 / 抽出シード数**(順5 の前。ADR-041 決定5)
- **T3 の確定文面と T1b の書式文字列**(ADR-042 決定10)
- **LoRA の `learning_rate` / `num_steps` / `batch_size` / `gradient_accumulation`**(ADR-043 決定10)
- **★2026-08-28 に追加(8-6 の実装で出たもの。`STATE.md`「人間の承認・判断を待っている事項」冒頭)**:
  最適化の既定値(`betas` / `eps` / `weight_decay` は torch の既定。どの ADR も宣言していない)/
  LoRA 重みの dtype(bf16 のまま)/ LoRA の `bias`(peft の既定 `"none"`)/
  **`model.adapter: null` のまま病変条件を評価できること**(止めていない)/
  **T1b が Go/No-Go #1 を割ったときの分岐が無いこと**(ADR-042 決定5 (iii) と決定7 が両方封じている)
- 手つかず: **#10(W6 の分岐)/ #17(Nikankin 原典確認)/ 目視レビュー11件 /
  効果量プロファイル / 罠3(凍結とパイロットの順序)**
