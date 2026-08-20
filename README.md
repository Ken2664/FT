# translesion

**狭いファインチューニングは「概念」を書き換えるのか、「表層のパッチ」を貼るだけなのか。**

算術を対象に、系統的変換(a+b → a+b+2)を FT で埋め込み、その変換が代数的・表記的・メタ認知的にどこまで一貫して伝播するかを監査する。将来的に色ドメインとマルチモーダルへ拡張する。

---

## 最初に読むもの

| 順 | ファイル | 内容 |
|---|---|---|
| 1 | `CLAUDE.md` | エージェント作業規約。**必ず最初に読む** |
| 2 | `STATE.md` | 現在の状態。何がわかっていて何がわからないか |
| 3 | `Documents/00_OVERVIEW.md` | 研究全体の1枚地図 |
| 4 | `AGENTS.md` | 複数エージェント運用時の役割分担 |
| 5 | `Documents/10_CONTEXT_POLICY.md` | コンテキスト運用方針。長い作業を始める前に読む |

---

## ディレクトリ構造

```
translesion/
├── README.md                  このファイル
├── CLAUDE.md                  エージェント作業規約(不変のルール)
├── AGENTS.md                  複数エージェントの役割と受け渡し規約
├── STATE.md                   ★生きた状態ファイル。既知/未知/ブロッカー
│
├── .claude/
│   └── skills/
│       └── code-style/SKILL.md  実装時だけ読むコード規約(常時読み込みではない)
│
├── Documents/                 設計文書(何を主張するかの単一情報源)
│   ├── 00_OVERVIEW.md         概念の統合定式化
│   ├── 01_HYPOTHESES.md       仮説 H1..Hn と検証状態
│   ├── 02_RELATED_WORK.md     先行研究(検証ステータス付き)
│   ├── 03_OPEN_QUESTIONS.md   ★未知 → 対応コード → 出力先 の対応表
│   ├── 04_EXPERIMENT_PLAN.md  実験設計
│   ├── 05_STATISTICS.md       ★統計計画(事前登録対象)
│   ├── 06_THREATS.md          交絡と妥当性への脅威
│   ├── 07_ROADMAP.md          段階計画と Go/No-Go
│   ├── 08_FUTURE_DIRECTIONS.md 色・マルチモーダル・統一仮説
│   ├── 09_PAPER_PLAN.md       論文構成(2本立て)
│   ├── 10_CONTEXT_POLICY.md   コンテキスト運用方針(トークン消費の管理)
│   └── refs.bib               検証済み文献のみ
│
├── plans/                     実験ごとのプランファイル(可変)
│   ├── TEMPLATE.md
│   └── PLAN-XXX-<名前>.md
│
├── logs/
│   ├── DECISIONS.md           意思決定ログ(ADR形式、追記のみ)
│   └── CHANGELOG.md           変更履歴(日付つき、追記のみ)
│
├── infra/
│   ├── RUNPOD.md              リモートGPU運用手順
│   ├── Dockerfile
│   ├── bootstrap.sh           ベアポッド → 実行可能状態
│   └── preflight.py           環境検証
│
├── code/
│   ├── data_gen/              病変FTデータ・評価バッテリ生成
│   ├── train/                 LoRA FT
│   ├── eval/                  一貫性バッテリの評価
│   │   └── parsers/           出力パーサ(独立モジュール)
│   ├── probe/                 線形プローブ・logit lens
│   ├── analysis/              統計・作図
│   └── tests/                 ユニットテスト
│
├── configs/                   実験設定 YAML(1実験=1ファイル)
├── data/
│   ├── raw/                   外部データ(読み取り専用扱い)
│   └── generated/             生成データ + manifest.json
├── runs/                      実験ログ(YYYYMMDD_HHMMSS_<exp_id>/)
├── results/                   集約済み指標・図表
└── paper/                     LaTeX
```

---

## 不変のルール(詳細は CLAUDE.md)

1. **出典を確認していない文献・数値を書かない。**
2. **予測は実験前に凍結する**(`Documents/05_STATISTICS.md` の事前登録)。
3. **対照条件のない病変FTは実験ではない。**
4. **「差がない」を主張するときは同等性検定を使う。**p > 0.05 は根拠にならない。
5. 変更したらプランファイルを直し、`logs/CHANGELOG.md` に記録し、git にコミットする。

---

## クイックスタート(ローカル)

```bash
git clone <repo> && cd translesion
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest code/tests -q          # まずテストが通ることを確認
python -m code.eval.run --config configs/smoke.yaml --dry-run
```

リモートGPUでの実行は `infra/RUNPOD.md` を参照。
