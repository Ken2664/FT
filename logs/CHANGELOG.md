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

### infra(repo): README.md の構造を実体化し、git 管理下に置く   [actor: IMPLEMENTER]
- `README.md` の構造図どおりにディレクトリを作成し、ルートに平置きされていた文書を移動した(`00`–`10` と `refs.bib` → `Documents/`、`CHANGELOG.md` / `DECISIONS.md` → `logs/`、`RUNPOD.md` → `infra/`、`TEMPLATE.md` → `plans/`)。`git init` + 初回コミット
- 設計文書は完成していたが、それらが参照するディレクトリが実在せず、repo が git 管理下になかった。`STATE.md`「現在のブロッカー」がこれを名指ししていた。git 未管理のままでは `CLAUDE.md` §1 のセッション開始手順、§5 のコミット規約、事前登録の `git tag` による凍結がいずれも実行できない
- 影響を受けるファイル: 移動 20 ファイル。新規 `pyproject.toml` / `.gitignore` / `.gitattributes` / `plans/PLAN-000-repo-bootstrap.md`
- 関連 commit: f28a4e4

### docs(refs): 移動で解決しなくなった相互参照を修正   [actor: IMPLEMENTER]
- `CLAUDE.md`(`Documents/05_STATISTICS.md`、`Documents/10_CONTEXT_POLICY.md`、`logs/CHANGELOG.md`)、`AGENTS.md`(`Documents/06_THREATS.md`、`Documents/10_CONTEXT_POLICY.md`、`Documents/refs.bib`)、`README.md`、`infra/RUNPOD.md`、skill `code-style` のパス参照に接頭辞を付与
- 文書の移動により、接頭辞なしの参照が解決しなくなったため
- **`logs/CHANGELOG.md` と `logs/DECISIONS.md` は追記のみのファイルなので書き換えていない。**過去エントリ中のパス表記は当時の記録として残す
- 関連 commit: f28a4e4

### infra(build): Python パッケージ骨格と実行環境を整備   [actor: IMPLEMENTER]
- `pyproject.toml`(ruff / black / pytest 設定、依存を base / gpu / stats / dev に分離)、`code/**/__init__.py`、`.gitignore`(`runs/` は `metrics.json` / `config.yaml` / `env.txt` / `timestamp.txt` / `cost.txt` のみ追跡、`predictions/` は除外)、`.gitattributes`(改行を LF に固定)
- `.gitattributes` を入れた理由: 開発が Windows、実行が Linux ポッドのため、git 既定の CRLF 変換で `infra/bootstrap.sh` がポッド上で起動しなくなる
- `infra/preflight.py`(`infra/RUNPOD.md` §3 の全検査項目 + shim 検査)、`infra/bootstrap.sh`、`infra/Dockerfile`、`infra/requirements.lock`(**空。実環境の `pip freeze` で埋める**)
- 未実施: `infra/Dockerfile` のベースイメージタグは `UNPINNED-未確認` のまま。実在を確認していないタグを書かないため(`CLAUDE.md` §2)
- 関連 commit: f28a4e4

### infra(config): 実験 config の雛形を作成   [actor: IMPLEMENTER]
- `configs/template.yaml` と `configs/smoke.yaml`。条件間で一致させる項目に `[MATCHED]` を付与
- **未決定の値はすべて `null` + 出所コメント。**学習率・ステップ数・LoRA rank・batch size・被演算子域・主要評価項目は設計文書に値が書かれていないため、エージェント側で既定値を作らない(skill `code-style` §5)。プランファイルで決めてから転記する
- 関連 commit: f28a4e4

### test(algebra): Q-3 の形式検証を実装   [actor: IMPLEMENTER]
- `code/lesion.py`(`AdditiveLesion` / `MultiplicativeLesion` / `ArbitraryLesion` / `IdentityLesion`)と `code/tests/test_algebra.py`。`pytest code/tests -q` → **40 passed**
- `Documents/03_OPEN_QUESTIONS.md` Q-3「⊕ の群構造と ⊗ の非結合性は正しいか」。`STATE.md` が手計算として記録していた主張をコードで固定した。**実験結果ではない**
- 固定した命題: ⊕(offset=k)は結合的・可換、単位元 −k、逆元 −a−2k、φ(x)=x+k で (Z,+) と同型 / ⊗(multiplier=m)は m ∉ {0,1} で非結合的かつ両側単位元を持たない / ⊕ の下で分配律が破れる(a=1 のときのみ保たれる)
- **新たに判明した点**: 偶然一致(`CLAUDE.md` §6 の除外リスト)は `p2` では決して起きないが、**`x2` では a+b=0 の項目で起きる**。PLAN-001 で被演算子域を決めるときに扱いを明示する必要がある
- 関連 commit: f28a4e4

### infra(repo): `code` パッケージ名が標準ライブラリと衝突する問題を解決   [actor: IMPLEMENTER]
- `code/__init__.py` で標準ライブラリ `code.py` の公開名を再エクスポート。`code/tests/test_import_shim.py` と `infra/preflight.py` の `stdlib code shim` 項目で常時検査する
- `code/__init__.py` を置いた時点で `pytest` が `pdb` の import 段階で落ち、`CLAUDE.md` §4 が前提とするテストゲートが機能しなくなっていた
- 関連 ADR: 013(ディレクトリ名を維持する判断は人間が3案から選択)
- 影響を受けるファイル: `code/__init__.py`、`code/tests/test_import_shim.py`、`infra/preflight.py`

### docs(adr): 存在しない ADR-012 への参照6箇所を記録   [actor: IMPLEMENTER]
- `CLAUDE.md` §5 のコミット例、`STATE.md`、`Documents/00_OVERVIEW.md`、`Documents/03_OPEN_QUESTIONS.md`、`Documents/06_THREATS.md` が「主変換を ×2 から +2 へ変更した根拠」を ADR-012 として参照しているが、`logs/DECISIONS.md` の ADR は 001–011 までで、当該決定は **ADR-004** として記録されている
- 追記のみの原則により既存記述を書き換えず、ADR-012 を対応記録として消費した
- 関連 ADR: 012(**ステータス: 提案中。人間の確認待ち**)
- 未修正: `Documents/` 配下の3箇所と `CLAUDE.md` §5。設計文書の書き換えは人間の判断事項(`CLAUDE.md` §8)
- 併せて判明: ADR-004 本文の「**ADR-007 の旧案を置き換える**」も食い違っている(ADR-007 は同等性検定の決定)。**未解決**

### docs(adr): ADR-012 を採択とし、「ADR-012」誤参照7箇所を ADR-004 に修正   [actor: IMPLEMENTER]
- 人間が `STATE.md` の承認待ち項目 1・2 について「AI の判断を受け入れる」と決定した。
  これを受けて ADR-012 のステータスを **提案中 → 採択** に変更し、保留していた
  設計文書の一括置換を実施した
- 変更したファイル(`ADR-012` → `ADR-004`):
  `CLAUDE.md` §5 のコミット例 L87 / `Documents/00_OVERVIEW.md` L70 /
  `Documents/03_OPEN_QUESTIONS.md` L63 / `Documents/06_THREATS.md` L63 /
  **`configs/template.yaml` L36**
- **ADR-012 の「6箇所」は数え落としだった。**`configs/template.yaml` L36 が
  7箇所目として見つかったため同時に修正した。この点は ADR-012 の帰結に追記した
- `logs/DECISIONS.md` ADR-012 の帰結・代替案のうち「未修正のまま残す」「一括置換は却下」
  の2項目は、`CLAUDE.md` §2 に従い**打ち消し線 + 理由 + 日付**で残し、削除していない
- `logs/CHANGELOG.md` の過去エントリ(2026-08-20「存在しない ADR-012 への参照6箇所を記録」)と
  ADR-012 冒頭の文脈記述は、追記のみの原則により当時の記録として書き換えていない
- **未解決のまま残した**: ADR-004 本文の「ADR-007 の旧案を置き換える」の食い違い。
  今回の承認範囲(項目 1・2)に含まれないため手を付けていない
- 関連 ADR: 012(採択)
- 関連 commit: (このコミット)

---


### docs(adr): ADR-014 — ADR-004 はどの ADR も置き換えないと確定し、誤記を取り消し   [actor: PLANNER]
- 人間が `STATE.md` の承認待ち項目 1 について「AI 判断をもって対処」と指示した
- **ADR-012 は問いを「どの ADR を指していたか」と立てたため確定不能に見えたが、
  「置き換え対象の ADR が存在するか」に立て直すと本ファイルだけで判定できる。答えは「存在しない」**
  1. ADR-007 は 採択 のまま `Documents/05_STATISTICS.md` §5・`CLAUDE.md` §2・`README.md` L87・
     `Documents/04_EXPERIMENT_PLAN.md` L13・`AGENTS.md` L47 から現役で参照されている。
     置き換えられていれば「置き換え済(ADR-YYY による)」になっているはず
  2. `logs/DECISIONS.md` 冒頭の規約は「覆す場合は**新しい** ADR で」と定める。
     004 は 007 より前であり、向きが規約に反する。ADR-001–011 はすべて 2026-08-20 の一括執筆
  3. ×2 を主変換とした ADR は存在しない。ADR-001 は既に「+2 など」と書いている
- 変更したファイル:
  - `logs/DECISIONS.md` ADR-004 ステータス行 → 打ち消し線 + 理由 + 日付(`CLAUDE.md` §2)。
    **文脈・決定・根拠・帰結・代替案は無変更。ADR-004 の決定内容は無効化されない**
  - `logs/DECISIONS.md` に ADR-014 を追記(採択)
  - `Documents/02_RELATED_WORK.md` L71 / `Documents/09_PAPER_PLAN.md` L13:
    臨床用語の決定への参照を `ADR-004` → **`ADR-002`** に修正
- **調査中に新たに判明**: 上記2箇所は commit a993826 の一括置換では触れていない。
  `git show a993826` で確認済みで、元の設計文書に最初からあった別系統の誤りである。
  ADR-012 の「7箇所」の数え落としではない
- **未解決として起票**: `Documents/08_FUTURE_DIRECTIONS.md` L62 の
  「ADR-005(色体系の規約)を先に確定すること」。ADR-005 は主要評価項目の決定。
  ただし**誤参照ではなく未執筆 ADR への先回り参照**と読めるため、番号の再利用にあたり
  `CLAUDE.md` §8 の判断事項。`STATE.md` の承認待ちに新規項目 2 として追加した
- 既知の誤参照のオフセットは 012→004(−8)、004→002(−2)で一定でない。
  機械的な一括補正はせず、1件ずつ内容で照合した
- 関連 ADR: 014(採択)
- 関連 commit: (このコミット)

---

<!-- 以降、追記 -->
