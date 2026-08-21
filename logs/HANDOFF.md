# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-21 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: コンテキスト超過(実測 約151k トークン。140k の打ち切り水準を超過)

> 使い方: `/clear` してから、下の `---` より後ろをそのまま貼る。

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

`plans/PLAN-001-eval-battery.md` を書く。一貫性バッテリの評価ハーネスの仕様を確定させる。
完了条件は次の4つがすべて埋まっていること。

1. **被演算子の値域**。x2 条件では `a+b=0` の項目で真値と規則適用値が偶然一致するため、
   除外リストの定義がここに依存する(`CLAUDE.md` §6)
2. 一貫性バッテリの項目カテゴリと、各カテゴリの項目数
3. 出力の4値分解(`correct` / `rule` / `other_error` / `parse_fail`)をどう判定するか。
   合計が必ず 1.0 になること
4. パーサの責務境界(`code/eval/parsers/` に独立モジュールとして置く)

実装(ハーネス本体)は PLAN-001 が人間のレビューを通ってから。**先に実装しない**(`CLAUDE.md` §4)。

## 直前セッションで確定したこと

- ADR-015 を採択。セッションを切る判断はエージェントの義務になった。
  コンテキストが約 100k を超えたら skill `handoff` を実行する
  (詳細 `Documents/10_CONTEXT_POLICY.md` §2.4)
- `infra/context_guard.py` と `.claude/settings.json` を追加した。
  **この hook が実際に発火するかは未検証。**発火しなくても §2.4 の判定表は生きている
- `a⊕b = a+b+2` の代数的性質(単位元 −2、逆元 −a−4)と `a⊗b = 2(a+b)` の非結合性は
  `code/tests/test_algebra.py` で検証済み。40 passed(本セッションでも再確認)
- 実験結果の数値はまだ1つも無い。`results/` は空である

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-000-repo-bootstrap.md` — PLAN の書式の実例
- `Documents/04_EXPERIMENT_PLAN.md` — 実験条件。`grep -n` で節を特定してから `sed -n 'X,Yp'`
- `Documents/05_STATISTICS.md` §10 — 事前登録の枠。Phase 1 の予測はまだ空
- `code/lesion.py`, `code/tests/test_algebra.py` — 病変規則の実装と検証済みの性質
- 全文 `cat` しないこと(`CLAUDE.md` §10.1)

## やってはいけないこと

- **x2 条件で `a+b=0` の項目を除外リストに入れ忘れる。**真値と規則適用値が一致し、
  `rule_rate` が測れなくなる。p2 条件では偶然一致は起きない(検証済み)
- `configs/template.yaml` の `null` を推測で埋めること。未決定値は人間が決める
- 対照条件を決めないまま実験条件だけ増やすこと(`CLAUDE.md` §2)

## 未解決 / 人間の承認待ち

- **承認待ち 1**: PLAN-000 の CRITIC レビュー
- **承認待ち 2**: `Documents/08_FUTURE_DIRECTIONS.md` L62 の「ADR-005(色体系の規約)」は
  未執筆 ADR への先回り参照。埋まっている番号を将来の ADR に割り当て直すかは人間の判断
- 2系統目のモデルが未決定
- `Dockerfile` のベースタグと `requirements.lock` は実環境を立ててから埋める
