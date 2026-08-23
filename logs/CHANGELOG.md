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

## 2026-08-21

### infra(repo): セッションの引き継ぎを自動化する(ADR-015)   [actor: PLANNER]
- `infra/context_guard.py` を追加。`UserPromptSubmit` hook として transcript の JSONL から
  直近の入力トークン合計(`input_tokens + cache_creation + cache_read`)を実測し、
  100k で1回・140k で毎回警告する。閾値未満は何も出力しない。閾値は
  `CONTEXT_GUARD_WARN` / `CONTEXT_GUARD_URGENT` で上書き可
- `.claude/settings.json` を新規作成し、上記 hook を登録
- skill `handoff` を追加(`.claude/skills/handoff/SKILL.md`)。切る判断 → `STATE.md` 更新 →
  `logs/HANDOFF.md` に次セッション用プロンプトを上書き → ユーザーに `/clear` を促す、までを1手順に
- `Documents/10_CONTEXT_POLICY.md` §2.4 を新設(判定表・実測方法・成果物の定義)
- `CLAUDE.md` §10.2 に「長くなったら自分から止める」を追加。
  `/clear` と `/compact` の項を1行に畳み、200行の上限を維持(200行ちょうど)
- 検証: 合成ペイロードで4系統を確認した。(a) `transcript_path` 直指定と
  `session_id` + `cwd` からの再構成の双方で transcript を解決、(b) 100k 警告は同一セッションで
  1回だけ、(c) 140k 警告は毎回、(d) 壊れた stdin と空 JSON では沈黙して exit 0。
  出力は ASCII のみ(698 バイト)で JSON として復号できることを確認
- **未検証**: hook が実際に発火するかは次のプロンプト送信時にしか分からない。
  `.claude/settings.json` は本セッション開始時点で存在しなかったため、Claude Code の
  再起動が必要な可能性がある(ADR-015 の「未検証・リスク」)

## 2026-08-22

### docs(plan): PLAN-001 一貫性バッテリの仕様を草案化   [actor: IMPLEMENTER]
- `plans/PLAN-001-eval-battery.md` を新規作成(草案)。`logs/HANDOFF.md` の完了条件4項目を記入
- **人間から値域まわりの決定6項目を取得**し §0 に記録。エージェント側で既定値を作った箇所はない
  - 0 と負数を含める / 訓練値域と評価値域を分ける / `a+b=0` は全条件共通で除外 /
    繰り上がり層を明示 / 生成回数の上限なし / 評価時の CoT はあり・なし両方
- 値域を確定(§4.1): 主域 `a,b ∈ [-99, 99]`、外挿域 `|a|,|b| ≤ 999` で少なくとも一方が 3 桁。
  ⊕ 逆元テストは相手が主域に収まるよう `a ∈ [-95, 95]` に限定
- 層を3種定義(§4.2): 訓練被覆(`id`/`interp`/`extrap`)は**実行時に manifest 照合で付与**し
  生成時に固定しない。Phase 1 の Go/No-Go で訓練域が変わってもプールを作り直さずに済む。
  内挿ホールドアウトは主域の 20% を構成的に予約する
- 繰り上がり層は `t ≥ 0` かつ `t mod 10 ∈ {8,9}` と定義。**負の和は層別対象外**とした
  (十進表記上「繰り上がり」が一意に定まらないため)
- 項目数 約 1,980(§5.1)。項目数は検出力ではなくカバレッジで決めた
  (`05_STATISTICS.md` §3.1「増やすべきはシード」)。**n の値は実測に基づかない暫定値**
- 4値分解の判定順序とパーサの責務境界を確定(§5.3, §5.4)。
  パーサは採点しない・`cot.py` は切り出しのみで数値化しない、を境界規則として明記
- **仕様の矛盾を2件検出し、承認待ちとして記録した**(§12):
  - **承認待ち-1**: `05_STATISTICS.md` §2 の主要評価項目「G6 の `rule_rate` を `p2` vs `ident`」は、
    `rule_rate` を条件自身の規則で計算する限り成立しない。`IdentityLesion` では規則値 = 真値であり
    `rule_rate(ident) = correct_rate(ident)` になるため(`code/lesion.py:140` の docstring と矛盾)。
    **参照規則を固定する**解決を提案。ADR に値する
  - 除外集合を全条件の和集合で取ると `IdentityLesion.coincides` が常に True のため
    **プールが空になる**。除外集合は `p2`/`arb`/`x2` からのみ計算する(§4.3)
- 併せて承認待ち-2〜4 を記録: `arb` 表への単調上方制約、`arb` 表の生成運用、
  主要評価項目を `elicitation=direct` に固定してよいか
- G6 の応答バイアス(`+2` では規則値が常に真値以上のため `>` 形式だけだと
  「常に Yes」で `rule_rate=1.0` が取れる)への対策として `<` 形式の同数混在を規定
- **実装は未着手。**`CLAUDE.md` §4 により人間のレビュー後。承認待ち-1 と -4 が前提

### docs(plan): PLAN-001 の承認を記録し、セッションを引き継ぐ   [actor: IMPLEMENTER]
- **人間が承認待ち1〜4と変更A〜Dをすべて承認**。PLAN-001 §12「承認の結果」と §13 に記録
  - 承認待ち1: `rule_rate` を固定参照規則に対して定義する(主要評価項目では参照規則 = `p2`)
  - 承認待ち2: `arb` 表に `table[t] ≥ t+2` の制約を課す
  - 承認待ち3: `arb` 表は固定シードで一度生成しリテラルとして config に貼る
  - 承認待ち4: 主要評価項目は `elicitation = direct` に固定。CoT 側は副次
  - 変更A: 外挿域を素のモデルの実測 `correct_rate ≥ θ` による定義に変える(懸念6の解消)
  - 変更B: パイロット専用の項目プールを本番プールから分離する
  - 変更C: 内挿ホールドアウトを「訓練サンプラが引く `K` 組の補集合」に変える(「20%」が消える)
  - 変更D: 被覆 `K` を config 項目として追加する
- PLAN-001 のステータスを `レビュー済(承認あり)。ただし §4・§5 の本文は未改訂` に変更
- **本文への反映は未実施。**ADR-016 も未起草、`configs/template.yaml` も未更新。
  コンテキストが 140k に達したため `CLAUDE.md` §10.2 / ADR-015 に従いセッションを切った
- 新規の承認待ち3件を `STATE.md` に記録: Go/No-Go の fallback に `K` と訓練値域を追加してよいか /
  `K` を掃引軸(実験条件)にするか / 懸念7(G1 の日本語を訓練内に置くか外に置くか)
- `logs/HANDOFF.md` を上書き。次セッションの作業は「承認内容を本文に反映し ADR と config を揃える」の1本
- **日付の訂正**: 前エントリを `## 2026-08-21` の下に追記していたが実際の作業日は 2026-08-22。
  日付見出しを分け、PLAN-001 の作成日・最終更新・実行ログも 2026-08-22 に修正
  (`CLAUDE.md` §5「日付が正確に残ることが重要」)

### docs(plan): 承認済の変更 A〜D を PLAN-001 本文へ反映し、ADR-016 と config を揃える   [actor: IMPLEMENTER]
- **前セッションは承認を §12・§13 に記録しただけだった。**本セッションで §4 の本文を実際に書き換えた
- **変更 A(§4.1 改訂 + 新 §4.1.1)**: 外挿域を `|·| ≤ 999` の決め打ちから
  **素のモデルの実測 `correct_rate ≥ θ` による定義**に変更。
  `R(M) = {(a,b) : |a| ≤ M, |b| ≤ M}` を `M` について掃き、`correct_rate ≥ θ` を満たす最大の
  `M*` を取り、`D_ext = R(M*) \ D_main` とする。**`θ` の値は決めていない**(人間が Phase 0 の
  実測後に決め ADR に記録する)。掃引粒度も同様。**FT を回さず前方計算だけで実行できる**
  - `M* < 100` なら `D_ext` は空になり外挿バッテリが成立しない旨を明記した。
    黙って空プールを作らず人間の判断に上げる
- **変更 C(§4.2 改訂)**: 内挿ホールドアウトを「主域の 20% を予約」から
  **`interp = D_main \ (訓練サンプラが引く K 組)`** に変更。**「20%」を本文から削除した**
  (§13 の変更履歴と §7 の交絡表の該当行も追随)
- **変更 D(新 §4.2.1)**: 値域 `R` と被覆 `K` が独立であることを本文に明記。
  `train_size = 10,000` / `K = 500` で1組あたり平均 20 回反復、ホールドアウトは 39,101 組(約 99%)
- **変更 B(新 §4.6)**: **パイロット専用の項目プール**を定義。`pilot` と `main` が
  **順序対の水準で交わらない**ことを `manifest.json` とテストで固定する旨を規定。
  生成手続きは共通にし、引く順序対だけを変える。`pool_id: pilot` の run の数値は主張に使わない
- §4.5 に `infra/preflight.py` の照合項目を表として明示(プールのハッシュ / `K` 組の一致 /
  `pilot`-`main` の非交差 / `M*` が Phase 0 の run_id に紐づくこと)
- **`logs/DECISIONS.md` に ADR-016 を追加(採択)**: `rule_rate` を**固定した参照規則**に対して
  定義する。主要評価項目では参照規則 = `p2`。`metrics.json` は参照規則ごとに独立した4値ブロックを
  持ち、**合計 1.0 は各ブロック内で成立する**。`correct_rate` と `parse_fail_rate` は参照規則に
  依存しないがブロックごとに再掲する(合計 1.0 を成立させるため)
  - **未検証・リスクとして記録**: `ident` を `eval.reference_rule` に指定すると
    `coincides` が常に True のため合計が 1.0 を超える。config 読み込み時の検査は**未実装**。
    プール生成後に参照規則を増やすと偶然一致項目が残りうるため、対象参照規則の集合を
    manifest に記録する必要がある。これも**未実装**
  - `Documents/05_STATISTICS.md` §2 の文言更新は**ゲートキーピング順序の変更を伴うため別 ADR**とし、
    本 ADR では触っていない
- **`configs/template.yaml` に3項目を追加。すべて `null`**(既定値を作らない。skill `code-style` §1, §5):
  `data.coverage_k` [MATCHED] / `eval.reference_rule` [MATCHED] / `eval.elicitation` [MATCHED]
- §5.2 の見出しと末尾を「承認を待つ」から **ADR-016 への参照**に差し替え。
  §5.1〜§5.6 の仕様本体は改訂していない
- §2 の参考表の「外挿域 → 3桁でほぼ消える」を「主域の外でほぼ消える」に変更。
  §2 は「**これは事前登録ではない**」と明記されているため事後変更の禁止には当たらない。
  H0 / H1 の対比そのものは変えていない
- `pytest code/tests -q` → **40 passed**(既存テストのみ。本セッションでコードは触っていない)
- **評価ハーネス(`code/eval/`)は未着手。**次セッションの作業

### feat(eval): 出力パーサ 6 モジュールと負例テストを実装(PLAN-001 §5.4)   [actor: IMPLEMENTER]
- **PLAN-001 実装フェーズの第1段。**`code/eval/parsers/` に独立モジュールとして実装した
  (skill `code-style` §2)。`base.py`(型と正規化)/ `numeric.py` / `wordform.py` /
  `japanese.py` / `boolean.py` / `cot.py`
- **パーサは採点しない。**真値も規則適用値も参照しない。4値分解は `code/eval/scoring.py`(未実装)の責務
- **Yes/No パーサは質問の極性を知らない。**「大きいです」「小さいです」を Yes/No に読み替えない。
  `>` と `<` で意味が反転するため、対応付けは採点側にしか書けない(PLAN-001 §5.1 の応答バイアス対策)
- **`cot.py` は切り出すだけで数値化しない**(PLAN-001 §5.4 の 2)
- **仕様の穴を埋めた。§5.4 は「数が複数見つかったときどうするか」を決めていなかった。**
  10 項目の抽出規則を確定し、**`plans/PLAN-001-eval-battery.md` に新 §5.4.1 として書き、
  人間の確認を求める印を付けた。**最も影響が大きいのは「見る範囲に整数がちょうど1個の
  ときだけ採る(0個も2個以上も `parse_fail`)」で、緩めると途中計算の値が
  `correct` / `rule` に流れ込む。**厳しい側を既定にした**(見逃しは報告で気づけるが、
  静かに拾った数は気づけない。`CLAUDE.md` §6・§7)
- テスト: `code/tests/test_parsers_{numeric,wordform,japanese,boolean,cot}.py`。
  **各モジュールに負例を置いた**(skill `code-style` §2):
  `3 と 4 を足すと 7` / `3個のりんごと4個のみかん` / `one of the numbers is five` /
  `nine (9)` / `7.5` / `I don't know` / `はい、そうではありません` / `大きいです` など
- `code/tests/test_parsers_cot.py::test_without_extraction_numeric_would_fail` は
  **cot.py が存在する理由そのもの**を固定する。ここが「たまたま通る」ようになったら
  数値パーサ側が緩んでいる
- `pytest code/tests -q` → **147 passed**(既存 40 + 新規 107)
- **ruff / black はこの環境に未インストール。**整形は手作業(行長 100 以下は機械的に確認済)。
  ポッドを立てた時点で `pip install -e .[dev]` して掛け直す
- **実験結果の数値は無い。**本コミットはコードとテストのみ

### feat(data_gen): 項目プールの対水準の機構を実装(PLAN-001 §4)   [actor: IMPLEMENTER]
- `code/data_gen/pool.py`。主域の列挙(§4.1)/ 外挿域(§4.1.1)/ 偶然一致の除外(§4.3)/
  繰り上がり層(§4.2 B)/ 訓練被覆ラベルの実行時付与(§4.2 A)/ pilot-main の非交差分割(§4.6)/
  ハッシュと manifest(§4.5)
- **`ident` を除外集合に入れると `DegenerateReferenceRuleError` で止まる。**名前ではなく
  **振る舞い**(標本の全項目で `coincides` が True)で弾くので、`offset=0` の加法規則も同じく弾かれる。
  ADR-016 の未検証・リスク「素朴に和を取るとプールが空になる」への対応
- **manifest に `reference_rules` を記録する。**ADR-016 のもう1つの未検証・リスク
  (プール生成後に参照規則を増やすと偶然一致項目が残りうる)への対応。
  `eval.reference_rule` がこの集合に含まれることの検査は評価ハーネス側で行う
- **`M*` が主域の半径以下なら例外で止まる**(§4.1.1)。空の外挿プールを黙って作らない
- `extrapolation_radius` / `extrapolation_run_id` は manifest に持つが**既定値を作らない**。
  Phase 0 の実測が入るまで `None` のまま
- テスト `code/tests/test_pool.py`(27件)。§4.3 が名指しで要求する
  **プール非空テスト**と、§4.6 の **pilot-main 非交差テスト**を含む
- `pytest code/tests -q` → **174 passed**

### feat(eval): 4値分解の採点・G6 の項目構成・`run.py --dry-run` を実装(PLAN-001 §5)   [actor: IMPLEMENTER]
- `code/eval/scoring.py`(ADR-016 / §5.3)。`RateBreakdown` は**4値+件数を1つの型**で返す。
  合計が 1.0 でない分解は**構築時に例外**になる。`metrics_by_reference_rule` が
  **参照規則ごとの独立ブロック**を作り、合計 1.0 は各ブロック内で検査する
  - **ADR-016 が「未実装」としていた2つの検査を実装した**: `validate_reference_rule` が
    (1) 退化した規則(`ident` および `offset=0`)を拒み、(2) **プール生成時に対象と
    しなかった規則**を拒む(manifest の `reference_rules` と突き合わせる)
  - `classify` は `True == 1` を利用した取り違えを**型で止める**。G6 の Yes が
    数値項目の 1 として correct に数えられる事故を防ぐ
  - 真値と規則適用値が一致する項目が採点に来たら `CoincidentItemError` で止める。
    静かに correct へ倒すと `rule_rate` が過小に出て、生成時除外の破損に気づけない
- `code/data_gen/battery_items.py`。`Item` 型 / `items.jsonl` と `manifest.json` の入出力 /
  item_id の一意性検査。**被覆ラベルは持たない**(実行時付与。§4.2 A)
- `code/eval/battery/g6_comparison.py`(★主要評価項目)。極性 × 閾値オフセットと
  `t` の下限を §5.1 のとおりに実装。**判別可能性は生成時に検査する**(§5.3)
  - `code/tests/test_battery_g6.py` が「§5.1 が認めた組み合わせでは p2 / x2 / arb の
    **すべて**で真値と規則値の答えが割れる」ことを検証する。`test_algebra.py` と同じく
    実験結果ではなく**設計の前提**の固定である。arb が割れるのは §4.4 の制約2に依存する
- `code/eval/run.py`。`--dry-run` は**モデルを読まない**。config → 項目 → プロンプト →
  パーサ → 採点 の配線だけを確かめ、「実験ではない」旨を標準出力の先頭に出す。
  **`--dry-run` なしの本実行は `NotImplementedError`。**既定のモデル名・生成設定を作らない
- `configs/templates/smoke.yaml` を追加(**配線確認専用**)。`configs/smoke.yaml` を
  ADR-016 以降の形に更新(`eval.reference_rule` / `eval.elicitation` / `batteries: [g6]` /
  `dry_run_items`)。**本番の評価テンプレート集合は作っていない**(§5.1.1 の穴3)
- **実装中に §5.1 と §4.2 の突き合わせで仕様の穴が2つ見つかった。PLAN-001 に新 §5.1.1 として
  書き、人間の判断を求める印を付けた**(`CLAUDE.md` §8):
  - **穴1**: `id` セルは訓練被覆 `K` 組からしか引けない。主域 39,601 組に対し `K=500` なら
    `id` は約 1.3% で、一様に引いたプールでは n=20 のセルが埋まらない。
    案A(FT データ生成後にプールを作る。`K` に依存)/ 案B(多めに引いて実行時にセルを選ぶ。
    コスト増)のどちらを採るかで **GPU 時間と事前登録の書き方が変わる**
  - **穴2**: 「単位元の言明」「規則の自己説明」は `(a, b)` を持たず被覆ラベルが定義できない
- **したがって G1〜G5 は未実装。**`make_item` が `NotImplementedError` で止まる。
  黙って空のプールを返さない
- `pytest code/tests -q` → **221 passed**
- **実験結果の数値は無い。`results/` は空のまま。**`--dry-run` の出力は固定応答に対する
  分解であり、モデルは1度も呼ばれていない

### docs(plan): PLAN-001 実装フェーズの状態を STATE.md / HANDOFF.md に反映   [actor: IMPLEMENTER]
- `STATE.md`: フェーズを「PLAN-001 の評価ハーネスを実装。G6 まで。G1〜G5 は仕様待ちで停止」に更新。
  repo の状態に9行追加、`pytest` の行を **221 passed** に更新
- **承認待ちを 5 件から 9 件に増やした**(6・7・8 は §5.1.1 の穴、9 は §5.4.1 の抽出規則の確認)。
  **実装を止めているのは 6・7・8**
- `logs/HANDOFF.md` を上書き(ADR-015)。次セッションは**承認待ち 6・7・8 への回答の有無で分岐**する
  (回答あり → G1〜G5 の項目構成 / 回答なし → Phase 0 の桁数掃引 or preflight のプール照合)
- PLAN-001 §9 の実装フェーズ完了条件のうち5項目にチェックを入れ、未達2項目
  (G1〜G5 の項目構成 / 本番テンプレート集合)を追加した

### docs(adr): ADR-017 — 評価項目プールは FT データ生成の後に作る(穴1 の決着)   [actor: IMPLEMENTER]
- **人間が PLAN-001 §5.1.1 の穴1 で案A を選択**(2026-08-22)。ADR-017 として採択
- 決定: **`id` セルは訓練被覆 `K` 組から、`interp` セルはその補集合から引く。**
  したがって**プールは `K` に依存し、Go/No-Go で訓練域を変えたらプールを作り直す。**
  §4.2 (A) が挙げた「作り直さずに済む」利点は、ラベル**付与**が実行時であることに留まり、
  セル**充填**には及ばない
- 根拠: 項目数が §5.1 のまま(約 1,980)で済み、**GPU 時間の見積もりが変わらない**。
  §4.5 の preflight が FT データ側 manifest と突き合わせる設計とも整合する
- **未検証・リスクとして記録**: `pilot` プールの `id` セルも同じ `K` 組から引くことになるため、
  §4.6 の非交差と両立するか要確認。また Go/No-Go でプールを作り直すと**事前登録済みの
  項目集合が変わる**(打ち消し線+理由+日付で残す手順を Phase 1 の fallback に書く必要がある)
- 実装: `code/data_gen/pool.py` に `Cell` / `fill_cells` / `InsufficientCandidatesError` を追加。
  **重複なく引き、埋まらなければ例外で止まる**(件数を黙って減らさない)。
  `code/tests/test_pool.py` に6件のテストを追加(`id` セルが `K` 組から埋まること / 重複しないこと /
  繰り上がり層 / 決定性 / 不足時の例外 / セル名重複)
- **§5.4.1 のパーサ抽出規則10項目は「現行のまま維持」で人間が確認済**(規則2 を含む)。
  PLAN-001 の見出しを「★人間が確認済」に更新した
- `pytest code/tests -q` → **227 passed**
- STATE.md の承認待ちは 9 件 → **7 件**(6 と 9 が解決)。`logs/HANDOFF.md` を上書きし、
  次セッションの作業を **G1〜G5 の項目構成**(被演算子を持つカテゴリのみ)に確定した

## 2026-08-22 — 設計の主軸を機構線に寄せる(ADR-018 / ADR-019)

役割: PLANNER。**コードは未変更。**設計分析と ADR の記録のみ。

- 人間が研究の関心を明示した。**「LLM の計算がどのように行われているかを解き明かす。
  それをもとに足し算の仕組みを変えると何が起きるかを見る」**——主軸は機構である。
  現行の設計と実装は行動監査に寄っていた(`Documents/00_OVERVIEW.md` §6 の三角測量表では
  機構線が3本中2本を占めるのに `code/probe/` は空)
- **ADR-018 を採択**(人間が「全部承認する」と回答):
  - モデル変種(base/Instruct)と revision は**設計判断ではなく Feucht et al. の原典からの転記**。
    ADR-008 の未決事項は調査タスクに変わった
  - 「最低2系統」(`04_EXPERIMENT_PLAN.md` §0 の固定要件)を **Phase 2 以降に延期**
  - **主要評価項目 G6 と新設 G7 は強制選択(選択肢トークンの対数尤度比較)で採点し、
    自由生成を併走させて両方報告する。**base でも測れ、`parse_fail` が構成的に 0 になり、
    自由生成側が独立した崩壊検出器になる
  - **G7「周期的概念への転移」を追加**(月・曜日・時刻)。Feucht et al. が示した共有機構に
    +2 病変が入ったなら「8月の6か月後」は 2月 → **4月**になるはず。出力段の方針なら 2月のまま。
    **主要評価項目は G6 のまま**(ADR-005)、G7 は副次の最上位
  - リスク回避: プレプリントからは**仮説だけを借り、証拠は Phase 0 #3 で自分たちが測る**
- **ADR-019 を採択**:
  - **訓練プロンプトは裸の式 `a+b=` 一形式。**GSM8K の最終回答だけを +2 する訓練は
    **出力段の方針を教える訓練**であり、T1 / H0 が排除したい対象そのもの。
    GSM8K 版は捨てず**対照条件に格上げ**(`train.cot_mode` → `train.scope`)
  - **訓練域を `[1,99]^2` に絞る。**現行では G2 の診断項目(`3+(-2)`、逆元)が訓練集合に
    混入しうるため。絞れば構成的に必ず訓練域外になる。繰り上がり密度も 9.6% → 20.0% に上がる
  - 被覆ラベルを4値化(`id` / `interp` / `oob_algebraic` / `extrap`)
  - **`K = 500` は使わない。**評価プールの `id` セルが相異なる 560 組を要求するため
    (`fill_cells` はセル間で組を再利用しない)。主値 2000、パイロットは {1000, 4000}
  - 外挿を `extrap_pair`(答えは訓練域内)と `extrap_magnitude` に2分割。
    現行定義では主域の 25% が3桁の答えを持ち、外挿の落ち込みを「未見の組」と「答えの大きさ」に
    分離できない
- **上記の割合はすべて設計の組合せ論的性質であり実験結果ではない**(`CLAUDE.md` §2)。
  `results/` に置かない。`code/tests/` に固定すること
- `STATE.md` の Phase 0 を**「FT を1回も回さずに終わるもの」として定義し直した**(#0〜#6)。
  承認待ちは 5 が解決、8 が前進、3 に制約が付いた
- `logs/HANDOFF.md` を上書きし、次セッションを **`plans/PLAN-002-ft-data.md` の起草**に確定

## 2026-08-22 — PLAN-002 起草(FT データ生成の仕様)

役割: PLANNER。**コードは未変更。**設計文書のみ。`pytest code/tests -q` → **227 passed**。

- **`plans/PLAN-002-ft-data.md` を起草。**ADR-018 / ADR-019 の決定を
  「この文書だけを読んで `code/data_gen/ft_data.py` が書ける」水準の仕様に落とした
  - **§4.1 訓練プロンプトの書式を1文字単位で確定**: `prompt = "{a}+{b}="` / `completion = "{target}"`。
    空白・改行・桁区切り・先頭ゼロ・全角文字をすべて禁止、`+`=U+002B / `=`=U+003D を明示、
    **チャットテンプレートを通さない**(base / Instruct のどちらでも成立するので Phase 0 #0 を待たずに確定できる)、
    損失は completion + EOS のみ、**パッキングしない**。トークン境界の確認は preflight の責務(§4.1.5)
  - **§4.2 `K` 組の層別サンプリング**: 層は **繰り上がり × 答えの桁数の6層**、**比例配分**(largest remainder)。
    層別は分布を変えるためではなく、**1回きりの抽出が母集団からずれないことを保証する**ために使う
    (`K` 組はシードをまたいで固定するので大数の法則に頼れない。§4.2.4)。**下限は置かない**
  - **§4.3 `train_size >= coverage_k` を必須化。**`K=2000` の下で `train_size=1k` は原理的に生成できないため、
    掃引軸を `{2000, 4000, 10000}` に改める提案(**実験条件の変更。承認待ち-10**)
  - **§4.5 被覆ラベル4値 + 直交する答え域ラベル2値。**判定は被演算子の性質だけで決める
    (`a<=0 or b<=0` → `oob_algebraic`)。訓練域の箱の大きさに依存させない
  - **§4.6.1 負域の切り分け**(ADR-019 が「未設計」と記した箇所)。
    `interp` vs `oob_algebraic·ans_in`(符号)/ `interp` vs `extrap_pair`(被演算子の大きさ)/
    `extrap_pair` vs `extrap_magnitude`(答えの大きさ)の**3対比で3要因を分離する**
  - **§4.7 訓練域の pilot / main 分割**(pilot 5,000 / main 4,801)。
    `id` セルが `K` 組からしか引けない(ADR-017)以上、**`K_pilot` と `K_main` も交わってはならない**
  - **§4.8 manifest schema** と preflight の新規検査4件
    (条件間バイト一致 / 書式ハッシュ / トークン境界 / `K >=` `id` 要求)
  - **§5.1 G7 の項目構成: 165 項目**(月60 / 時刻60 / 曜日45)。層は `carry × wrap`、`n=15`
  - **§5.2 G0「訓練形式アンカー」の新設を提案**(承認待ち-8 の残りへの回答。案A)
- **新規に判明した組合せ論的事実**(実験結果ではない。`code/tests/test_design_facts.py` に固定すること):
  - 訓練域 `[1,99]^2` で**答えが1桁の組は 36 組(0.37%)**しかなく、`K=2000` の被覆には **7 組**しか入らない。
    **3桁の答えを持つ組が 50.51%** を占める(`[-99,99]^2` の「25%」とは別の集合の数字)
  - **`oob_algebraic` に `t > 198` の組は存在しない** → **主要評価項目 G6 は負の和を測れない**。
    これは主要評価項目の**限界の宣言**であり事前登録に書く
  - 周期タスクの `carry × nowrap` セルは**法 12 で 15 件、法 7(曜日)では構成的に空**
    (`carry` は `x+n >= 8 > 7` を要求するので `carry ⟹ wrap`)。G7 の `n=15` はこの最小セルから derive した
  - 厳格な結合律規約(構成4対すべてが `id`)は `K` に約4乗で効き、`K=1000` で 39 件しか作れない
    → **先頭2項規約を採る**(`make_item` の carry 規約に揃える)
- **文書の追随**:
  - `configs/template.yaml`: `train.cot_mode` → **`train.scope`** に置換。
    `data.pool_split_seed` / `coverage_seed` / `sample_seed` / `pool_id` を追加(**4項目とも `null`**)。
    `eval.batteries` の例に `g0` / `g7` を追加。YAML のパースを確認済
  - `Documents/04_EXPERIMENT_PLAN.md`: §0「最低2系統」と Phase 1「FT データ」に
    **打ち消し線 + 理由 + 日付**(`CLAUDE.md` §2)
  - `plans/PLAN-001-eval-battery.md`: §4.1(訓練域と主域の分離)/ §4.2(被覆ラベル4値 + 答え域ラベル、
    新 §4.2.2 で `K` の下限)/ §4.4(`arb` の追加制約3・4)/ §4.6(pilot 分割の訂正)/
    §5.1(セル構成を6被覆クラスに改訂、G0 と G7 を追加。項目数 1,980 → **3,565**、`id` 要求 **556 組**)/
    §5.5 / §8 / §13 を改訂。**事前登録は未凍結(tag なし)なので打ち消し線は使っていない**
- `STATE.md`: 承認待ちを **7 件 → 12 件**に更新(9〜14 を新規追加、8 を 12 に移送)。
  **旧記載「221 passed」は数え落としで、実測は 227**(`test_algebra` 36 / `test_pool` 33)
- **学習率・ステップ数・batch size・LoRA rank/alpha・`arb` のズレ表には手を付けていない。**
  人間の決定事項として意図的に空けてある(PLAN-002 §0)
- **Phase 0 #0(Feucht et al. の原典転記)は未実施。**SCOUT に投げられる状態のまま
- **セッションを切った。**hook `context-guard` が約 247k トークン(閾値 140k)を報告し、
  かつ PLAN-002 の起草が完了したため(skill `handoff` の判定表で2件該当)。
  `logs/HANDOFF.md` を上書きし、次セッションを **Phase 0 #0(Feucht et al. の原典転記。SCOUT)**
  に確定した。RunPod は本セッションで未使用

---

## 2026-08-23 — Phase 0 #0: Feucht et al. の原典転記(ADR-008 採択)

### docs(adr): ADR-008 を採択に更新し、モデル変種と revision を原典から転記   [actor: SCOUT]

- **実際に開いた出典**(`CLAUDE.md` §3):
  - `https://arxiv.org/abs/2605.01148`(**v1 のみ**。Fri, 1 May 2026 22:49:29 UTC 投稿。
    cs.AI / cs.CL。DOI `10.48550/arXiv.2605.01148`。**Comments 欄なし** = 会議名の記載は無い)
  - `https://arxiv.org/html/2605.01148v1`(全文 HTML。ローカルに落として機械的に検索した)
  - `https://github.com/goodfire-ai/arithmetic-wild`(**論文の扉頁が示す公式コード**)
- **転記した4点**:
  1. **変種**: `meta-llama/Llama-3.1-8B`(**base**)。
     **論文本文は「Llama-3.1-8B」としか書かず、`Instruct` / `instruction-tuned` /
     `chat template` / `base model` / `meta-llama` / `huggingface` / `revision` / `checkpoint` は
     本文・全付録・全脚注のいずれにも1回も現れない**(HTML 全文を機械的に検索して確認)。
     base の根拠は公式コードの `--model` 既定値(`src/generate_dataset.py` L139–140、
     `src/train_das.py` L52)と、公開データ `datasets/Llama-3.1-8B/*/filter_metadata.json` の
     `"model": "meta-llama/Llama-3.1-8B"` / `"dtype": "bfloat16"` / `"max_new_tokens": 5`
  2. **revision**: **示されていない。**論文にも公式コードにも `revision=` の指定が無い
  3. **周期タスクの書式**(コード側がバイト単位で正。論文 Table 1 とは `hours` の空白位置が食い違う):
     - 月 `"Q: What month is {offset} months after {input}?\nA:"`
     - 曜日 `"Q: What day is {offset} days after {input}?\nA:"`
     - 時刻 `"Q: In 24-hour time, it is now {input}:00. What time will it be in {offset} hours?\nA: In 24-hour time, it will be "`(**末尾に空白1つ**)
     - 加算(対照)`"{input}+{offset}="`、`a, b ∈ [1,100]`、答えは `2..200`
     - **オフセットは英語の数詞**(`one` … `forty-eight`)。数字ではない
  4. **オフセットの範囲**: 「offsets range from 1 to 2p, where p is the cycle length」(§2)。
     月 `1..24` / 曜日 `1..14` / **時刻 `1..48`(法 24、24時制)**。
     項目数 288 / 98 / 1152 がこの読みと一致する
- **ADR-008 を「提案中」→「採択」に変更**し、根拠・帰結・限界を書いた。
  ADR-018 決定1 に「2026-08-23 完了」の注記を入れた
- **`CLAUDE.md` §7 に従って残した限界**: 「base である」は**論文の明言ではなく
  公式コードからの証拠**である。論文本文だけを見れば変種は未特定のままである
- 影響を受けるファイル: `logs/DECISIONS.md`(ADR-008、ADR-018 決定1)/
  `Documents/refs.bib`(`verified = {2026-08-23}`、`code_url` / `version` /
  `model_variant` / `model_revision` を追加)/ `Documents/02_RELATED_WORK.md`(**§A.1 を新設**)
- 関連 commit: (このコミット)

### docs(plan): PLAN-002 §5.1 の `n_max` と G7-H の欄を転記結果で埋めた   [actor: SCOUT]

- **§5.1.2**: ~~`n_max = 24` 一律~~ → **`n_max = 2m`(月 24 / 曜日 14 / 時刻 48)**。
  ~~G7-H は 12時制の時計盤(法 12)~~ → **24時制(法 24、起点 `00`..`23`)**。
  時刻の真値は `(x+n) mod 24` で **0 始まり**であり、月・曜日の 1 始まりと規約が違う
- **§5.1.2a を新設**(プロンプト文面の逐語転記)。英語のまま使う案
- **§5.1.3**: `p2` の偶然一致の検算に法 24 を追加(`2 mod 24 != 0` なので依然として起きない)
- **§5.1.4**: 母集団を原典の `n_max` と法で計算し直した。
  **165 項目と `n = 15` は変わらない**
- **§7.3 制約3**: 範囲 ~~`2 <= t <= 36`~~ → **`1 <= t <= 71`**、
  法 ~~`{7,12}`~~ → **`{7,12,24}`**
- **§5.1.1**: **G7 の前提が弱まったことを明記。**原典 Table 2/3 では月タスクの
  「法を跨ぐ」正答率は **55.0%**、前剰余和 `[p,2p]` 帯で **68.1%** であり、
  「8月の6か月後」(前剰余和 14)はこの帯に入る。**Phase 0 #3 は「確かめる」ではなく
  「項目フィルタを作る」作業になる可能性が高い**
- **新規に見つかった設計上の穴**: `arb` のズレ表の定義域は `t ∈ [2,198]` だが、
  G7-H を 24時制にすると `x=0, n=1` で **`t=1`** を要求する。
  (a) 定義域を `[1,198]` に広げる / (b) `x=0` を除く / (c) `n >= 2` にする。
  **実験条件の変更なのでエージェントが決めない**(`CLAUDE.md` §8。承認待ち-13 に含めた)
- **承認待ちが 12 件 → 13 件に増えた。**新規 15 は `model.revision` に何を入れるか
  (原典が示していない以上、原典との厳密一致は revision 水準では原理的に保証できない)
- **コードは未変更。**`pytest` は再実行していない(前セッションの 227 passed のまま)
- 影響を受けるファイル: `plans/PLAN-002-ft-data.md`(§5.1.1 / §5.1.2 / §5.1.2a /
  §5.1.3 / §5.1.4 / §4.9.3 の7 / §7.3 / §12-3 / 冒頭の未決表)/ `STATE.md`
- 関連 commit: (このコミット)

---

## 2026-08-23 — `arb` の役割を再宣言し、第4条件 `p2d` を追加(ADR-020 / ADR-021 / ADR-022)

**きっかけ**: 人間が「未知の値に対して `arb` の意味がないのだから検証が不可能ではないか」と指摘した。
検討の結果、**指摘は `ans_out` について正しく、`ans_in` について誤り**であると分かり、
同時に**実装上の穴が1件**見つかった。

### ADR-020: `arb` を「構造の対照」から「和への routing probe」に再宣言

- **役割の変更**: `arb` の成功は出力段の定数バイアスでは説明できない。未見の組で `table[a+b]` を
  出すには**和を実際に計算して内部表現を作り、それを鍵に写像を引く**しかない。
  一方 `p2` の成功は低ランクの出力シフトで説明がついてしまう。
  すなわち **`arb` は `p2` より強い機構的証拠を出す**
- **評価範囲を `ans_in`(C1/C2/C3/C5)に限定。**C4/C6 は `arb` の定義域外と宣言する
- **解析を2つに入れ子で分ける**(主解析 = `ans_in` × 全条件 / 副解析 = `ans_out` × 全域関数の条件のみ)
- **却下**: ズレ表を `t ∈ [−1998, 1998]` に広げる案。学習不可能な項目に規則値を与え、
  `rule_rate ≈ 0` という**数学的必然を実験結果として提示する**ことになる
- **新規に見つかった穴(再現確認済)**: 表の定義域 `t ∈ [2,198]` の外で
  `ArbitraryLesion.apply` が `KeyError` を投げる。該当は **100,298 組**
  (`oob·ans_out` 20,098 + `extrap_magnitude` 80,200)。`eligible_pairs` は
  `p2`/`arb`/`x2` の和集合で除外を計算するため、**プール生成そのものが落ちる**。
  対策: 候補ごとに規則の定義域を先に見て、外れていればその規則を飛ばす
- **H3 の主たる検定を獲得コスト比から「`id` 到達度を揃えた上での `interp` 転移」に変更**

### ADR-021: `t` 水準の被覆ラベル(`t_seen` / `t_unseen`)を追加

- 現行の被覆ラベルは**すべて `(a,b)` 水準**だが、`arb` の一般化は **`t` 水準**で起きる
- 実測(組合せ論的性質。`pool_split_seed=20260822`, `coverage_seed=20260822`, `K_main=2000`):
  `K = 2000` は 197 個の `t` のうち **187〜190 個**を被覆(seed 依存)。未被覆は両端に集中
  | 被覆クラス | 候補組数 | `t_unseen` |
  |---|---|---|
  | `id` | 2,000 | 0(0.0%) |
  | `interp`(訓練域全体) | 7,801 | 31(0.4%) |
  | `oob·ans_in` | 9,702 | 572(5.9%) |
  | `extrap_pair` | 39,400 | 1,600(4.1%) |
- **層として使うのは `arb` の解析だけ。セル構成は変えない**(`id` 要求を増やさないため)

### ADR-022: 第4の病変条件 `p2d`(`t + 2 + (t mod 10)`)を追加 ★実験条件の追加(人間が承認)

- **目的**: `p2`(定数1つ)と `arb`(197 エントリ)は記述長が2桁違い、
  H3 で「構造の効果」と「記述長の効果」を分離できなかった。
  `p2d` は **`p2` に桁依存の項を1つ足しただけ**なので、差が代数的整合性だけに絞られる
- **検証済の性質**(すべてコードで確認。組合せ論的性質):
  - `f(t) != t` が `|t| <= 2000` の全域で成立 → 真値との偶然一致 **0 件**
  - `f(t) - t ∈ [2, 11]` → G6 の閾値規約(`>= t+2`)を満たす
  - **非結合的**: `(1..19)^3` の 6,859 三つ組のうち **5,816(84.8%)**で結合律が破れる
  - **単位元を持たない**(`e ∈ [-300,300]` に該当なし)
  - `x2` と一致する `t` は `|t| <= 2000` に存在しない
  - `p2` と一致するのは **`t ≡ 0 (mod 10)`** のときだけ →
    除外規則を追加。`D_train` の **981 組(10.0%)**、主域の **3,961 組(10.0%)**
  - **繰り上がり層はこの除外と交わらない**(`carry` は `t mod 10 ∈ {8,9}`)
  - 桁数が `p2` と違う `t` は 197 件中 **9 件**(`t ∈ {4,5,6,7,89,94,95,96,97}`)
- **剰余規約は実験条件**: `t mod 10` は常に `0..9`(Python の `%`)。`p2d(-7) = -2`
- **コスト**: 条件が 5 → 6 に増え、生成回数が 356,500 → **427,800**(+20%)
- **未検算**: G7 の 15 件しかないセルと `carry × 1桁` 層(母集団 15 組)が
  `t ≡ 0` の除外後も埋まるか。`code/tests/test_design_facts.py` に固定すること

### 更新したファイル

- `logs/DECISIONS.md`: ADR-020 / 021 / 022 を追記(ADR は 20 → 23 本)
- `Documents/01_HYPOTHESES.md`: **H0 に `arb` による鋭い検定を追加**、**H3 を全面改訂**
  (旧「構造的規則は恣意的規則より安価に install でき〜」→
  「代数的に整合した規則は、非整合な規則より広く汎化する」)
- `Documents/04_EXPERIMENT_PLAN.md`: 条件表を改訂(`p2d` 追加、`arb` の役割変更、性質の比較表)
- `Documents/05_STATISTICS.md`: 固定効果に `p2d`、**入れ子の2解析**、
  ゲートキーピングの 5/6 を差し替え + 7(routing)を新設、事前登録の予測を改訂
- `plans/PLAN-001-eval-battery.md`: §4.2 に **(A'') `t` 水準の被覆ラベル**を新設、
  §4.3 に `p2d` の行と `t ≡ 0` 除外、§4.4 の表の定義域を改訂、生成回数 5 条件 → 6 条件
- `plans/PLAN-002-ft-data.md`: §3.3 条件表、§3.4 バイト一致の条件数、
  §4.4 `target`、§4.5.1a(`t` 水準ラベル)、§7.3(表を広げない)、§12(承認待ち 7/8/9 を追加)
- `configs/template.yaml`: `condition` に `p2d`、`digit_modulus` を新設、`arb` の定義域を明記

### まだやっていないこと

- **コードは1行も変えていない。**`pytest code/tests -q` は再実行していない(227 passed のまま)
- `code/lesion.py` に `DigitOffsetLesion`(`p2d`)が無い
- `code/data_gen/pool.py` の `label_coverage` は依然3値。`label_t_coverage` も無い
- `eligible_pairs` の定義域ガードが無い(**現状では `arb` を渡すとプール生成が落ちる**)
- 関連 commit: (このコミット)

---

## 2026-08-23 — セッション引き継ぎを記録(PLANNER → IMPLEMENTER)

- `STATE.md` の「引き継ぎ」ブロックを ADR-020 / 021 / 022 の内容に更新
- `logs/HANDOFF.md` を上書き。次セッションは **IMPLEMENTER**、作業は
  「次のアクション」実装順 **0 / 1 / 1b / 1c**(`ft_data.py` には入らない)
- 切った理由: hook `context-guard` の警告(約12万トークン)+ 設計単位の完了(`CLAUDE.md` §10.2)
- **最優先は実装順 0**(`eligible_pairs` の定義域ガード)。現状 `arb` を渡すとプール生成が落ちる
- RunPod は本セッションで使用していない(GPU 時間 0)
- 未追跡のまま残したファイル: `Documents/reviews/papers_list.md`。**本セッションの成果物ではない**
  (参照先 `Documents/reviews/2026-08-23_design_value.md` が存在しない)。由来を人間に確認すること
- 関連 commit: (このコミット)

## 2026-08-23 — ADR-023 採択。設計の全面見直しへ(CRITIC → PLANNER)

- **`Documents/reviews/2026-08-23_design_value.md` を新規作成。**先行研究に照らした設計価値レビュー。
  依拠文献 14 本を arXiv abs / ACL Anthology / arXiv HTML 全文を実際に開いて確認し、
  `Documents/reviews/papers_list.md` にリンク付きで分離した(親 `CLAUDE.md` の論文集規約)。
  **`refs.bib` / `02_RELATED_WORK.md` への反映は未実施**(§8。引用の最終確定は人間)
- **ADR-023 を採択。**人間が研究の主軸を再宣言し、実験設計の全面的な見直しを宣言した。
  主軸は **「タスク型(T1 裸の式 / T2 文章題 / T3 比較判断)× 式の既知性」の要因計画**、
  主要な推定対象は**交互作用**。**G7(周期概念)はオプションに格下げ**
- `STATE.md`: 冒頭に「★ 最優先」ブロックを新設。フェーズを「Phase 0 中断 → 設計の全面見直し」に変更。
  「引き継ぎ」を全面差し替え(凍結する作業 / 再導出で答えを出す6問 / R8 の提案 / 独立に残る未解決)
- `logs/HANDOFF.md` を上書き。次セッションは **PLANNER**、作業は
  **`plans/PLAN-003-redesign.md` の起草のみ**(コードは1行も変えない)
- **凍結**: 実装順 0 / 1 / 1b / 1c、PLAN-002 §12 の承認待ち9件、事前登録の `git tag`、
  Phase 0 の GPU 作業。理由は `arb` / `p2d` / G7 / セル構成の存廃が再導出で変わりうるため
- 前セッションが「由来不明」と記録した `Documents/reviews/papers_list.md` は
  **本セッションの成果物**である。参照先の本文も同時にコミットした
- 切った理由: hook `context-guard` の警告(約17.4万トークン)+ 人間による設計見直しの宣言
- RunPod は本セッションで使用していない(GPU 時間 0)
- 関連 commit: (このコミット)

## 2026-08-23 — PLAN-003 実験設計の再導出を起草(PLANNER)

- **人間に3件のブロッキング質問をし、回答を得た**(`plans/PLAN-003-redesign.md` §2)。
  **D-1 モデルは Instruct 主系統**(`meta-llama/Llama-3.1-8B-Instruct`。ADR-008 / ADR-018 決定1 を上書き)/
  **D-2 G2・G3 は捨て、G5 は「特異性対照」の最小版だけ残す** /
  **D-3 評価プロンプトは英語に統一**(言語は ADR での決定が無かった)。
  **3件ともまだ ADR 化していない**(PLAN-003 §11 の承認待ち-1)
- **`plans/PLAN-003-redesign.md` を新規作成。**ADR-023 の要因計画からの再導出。
  `logs/HANDOFF.md` の完了条件6項目をすべて埋めた。主な導出:
  - **共通被覆水準は `id` / `interp` / `extrap_magnitude` の3つ。**`oob_algebraic`(0/負)と
    `extrap_pair`(片方が負)は**文章題として自然文に書けない**。要因計画が3タスク型で共通の層を
    要求する以上、**T2 が水準を決める**。副産物として `x2` の偶然一致問題(`t=0`)が消える
  - **主要評価項目を `p2` 条件の `task * coverage` 交互作用の LRT(df=4)に置き換えた。**
    帰無仮説は「既知性の勾配が3タスク型で平行」。1仮説・1 p 値なので ADR-005 と両立する。
    **旧主要評価項目(G6 の `p2` vs `ident`)は Go/No-Go のペネトランス判定(≥ 0.90)に降格**
  - **適格性フィルタを新設**(`ident` の `correct_rate` < 0.70 のセルは主解析から除外。事前登録)。
    「T2 の外挿は単に難しい」が交互作用の形をそのまま作れる交絡への対策
  - **R8 は主要評価項目にしない。**`Δ̂` は T1/T2 で定義できず尺度が揃わないため、副次に置く
  - **T1b(裸の比較)を提案(P-1)。**T1/T2/T3 は「入力書式の距離 × 出力の型」の部分格子で、
    第4セルが空いている。埋めないと入力側の効果と出力側の効果が交絡する
  - **`t` ホールドアウト `T_hold`(20 個)を提案(P-3)。**`K=2000` では `interp` の 99.6% が
    `t_seen` になり `interp × t_unseen` が構成不能。等間隔に取ると `carry` 側が 0 個になる
    落とし穴も記録した(`carry` 比例配分で 4/16 に割る)
  - **条件配分を 35 run に削減**(`p2` 10 / `ident` 10 / `p2d` 5 / `arb` 5 / `x2` 5)。
    主軸が交互作用になったのでシードを主条件に寄せた
  - **資産の存廃判定**: `scoring.py` と `battery_items.py` は**そのまま**、
    `pool.py` / `g6_comparison.py` / `lesion.py` / `run.py` / `base.py` / `boolean.py` は**改修**、
    `japanese.py` は**捨てる**、`wordform.py` は**凍結**。テストは 227 → 約 205 が残る
  - **G7 は探索的アドオンとして残す案を推奨**(D-1 で Feucht et al.(base)との厳密一致が
    失われ、確証的主張の支柱にできない)
  - **§11 に人間の承認待ち 15 件**を番号付きで列挙。骨格は #1〜#5
- **本文書に現れる組合せ論的な数値を本セッションで実測した。**既掲値(9,801 / carry 1,960 /
  `t≡0 mod 10` 981)は再計算と一致。新規値(`T_hold` 関連)は
  `code/tests/test_design_facts.py` に固定する方針を PLAN-003 §7.2 に書いた
- `STATE.md`: 冒頭「★ 最優先」に PLAN-003 への追記、フェーズを「再導出を起草済み・承認待ち」に変更、
  「引き継ぎ」を全面差し替え、「承認・判断を待っている事項」と「主軸と独立に残っている未解決」を
  **PLAN-003 §11 の番号へ集約**
- **人間が再提示した実験目標は、既に ADR-023 と `STATE.md`「★ 最優先」に記録済みであることを確認した。**
  食い違いが無かったため新規の記録はしていない
- **コードは1行も変更していない。**`pytest code/tests --collect-only` → **227 collected**(実測)。
  `results/` は空。RunPod 未使用(GPU 時間 0)
- 関連 commit: (このコミット)
