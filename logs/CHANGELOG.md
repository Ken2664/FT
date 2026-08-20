# CHANGELOG.md

**追記のみ。新しい項目を末尾に足す。**
日付は UTC。`date -u +%Y-%m-%d` の出力を使う。

書式:

```
## YYYY-MM-DD

### <type>(<scope>): <要約>   [actor: PLANNER|IMPLEMENTER|RUNNER|ANALYST|CRITIC]
- 何を変えたか
- なぜ変えたか(ADR がある場合はその番号)
- 影響を受けるファイル / 実験
- 関連 commit: <sha>
```

---

## 2026-08-20

### docs(plan): 設計文書一式の初版を作成   [actor: PLANNER]
- `Documents/` 配下の 00–09 と refs.bib、ルートの CLAUDE.md / AGENTS.md / STATE.md、infra/RUNPOD.md を作成
- 研究の方向が「行動論的病変研究」から「FT は概念か表層かの監査」へ収束したため、全体を書き直した
- 関連 ADR: 001–009

### docs(adr): 主変換を ×2 から +2 に変更   [actor: PLANNER]
- ADR-004。a⊗b = 2(a+b) が非結合的であり、整合した代替算術を定義できないため
- 影響: G2(代数的整合性)の全項目、`code/tests/test_algebra.py`(未実装)

### stat(plan): 反復単位を FT run とする方針を確定   [actor: PLANNER]
- ADR-006。項目数ではなくシード数が条件効果の検出力を決めるため
- 影響: 主要評価項目で10シード必要。GPU コスト見積もりを上方修正

### stat(plan): 同等性検定(TOST)の導入を決定   [actor: PLANNER]
- ADR-007。「差がない」の主張を統計的に正しく行うため
- 影響: Phase 0 でプロンプト感受性の測定が必要になった(同等性境界の根拠)

### docs(plan): コンテキスト運用方針を明文化   [actor: PLANNER]
- `10_CONTEXT_POLICY.md` を新規作成。`CLAUDE.md` に §12 と Compact instructions を追加。`AGENTS.md` に SCOUT 役割と依頼雛形を追加
- 会話が長くなるとリクエストごとに会話全体が再送されトークン消費が増え、同時にコンテキストが埋まるほど指示の遵守精度が落ちるため
- 関連 ADR: 010
- 影響を受けるファイル: `CLAUDE.md`(207→263行)、`AGENTS.md`、`10_CONTEXT_POLICY.md`(新規)、`DECISIONS.md`
- 既知の負債: `CLAUDE.md` が公式の目安 200 行を超過。次の見直しで §6/§7 の別ファイル化を検討する

### docs(plan): CLAUDE.md を強制規則のみに整理し、手順と規約を外部化   [actor: PLANNER]
- §6(実験実行の手順)を `infra/RUNPOD.md` §4 へ、§7(コード規約)を skill `.claude/skills/code-style/SKILL.md`(新規)へ移動。§12.3 を §10.2 の1行に圧縮し、残る節を繰り上げ(8→6、9→7、10→8、11→9、12→10)。`infra/RUNPOD.md` も旧 §4–§8 が §5–§9 に繰り下がった
- 上の項目で記録した「200 行超過」の負債を解消するため。263 → 198 行
- 関連 ADR: 011(節番号の対応表を含む)
- 影響を受けるファイル: `CLAUDE.md`、`infra/RUNPOD.md`、`.claude/skills/code-style/SKILL.md`(新規)、`AGENTS.md`、`04_EXPERIMENT_PLAN.md`、`07_ROADMAP.md`、`10_CONTEXT_POLICY.md`(§6.1.1 と出典 [5] を追加)、`README.md`
- 未実施: git 未初期化のためコミットなし。§5 の手順は `git init` 後に適用する

---

<!-- 以降、追記 -->
