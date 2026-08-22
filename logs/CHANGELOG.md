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
