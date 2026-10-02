# PLAN-038: LF の検査の対象を設計文書・記録文書へ広げる

> プランファイルは**実装より先に書く**。仕様がここに書かれていないものは実装しない。
> 変更したら `logs/CHANGELOG.md` に記録し、git commit する。

- 作成日: 2026-10-02
- 最終更新: 2026-10-02
- ステータス: `完了`
- 担当: IMPLEMENTER
- 関連する問い: なし(リポジトリの衛生。実験ではない)
- 関連する仮説: なし

> **番号について**: `PLAN-037` は `logs/HANDOFF.md` が S3(T1c ほかの実装)に予約しているので、この PLAN は 038 とした。

---

## 1. この PLAN が答える問い

**`.gitattributes` の `*.md text eol=lf` に反する CR が、引き継ぎ文書以外の `.md` に混ざったとき、`pytest` が落ちるか。**

---

## 2. 経緯

- 2026-10-02(その132)、`logs/CHANGELOG.md` に CR が 1 バイト混ざった(heredoc 経由の Python で、文中の `\r` が実際の CR に化けた)。手でバイトを数えて見つけて直した
- `code/tests/test_repo_hygiene.py` の `test_handoff_documents_use_lf_only` は `STATE.md`・`logs/STATE-ARCHIVE.md`・`logs/OPEN-ITEMS.md` の 3 本だけが対象で、これを捕まえられなかった

---

## 3. 変更

`code/tests/test_repo_hygiene.py` だけを変える。

| 対象 | 指定の仕方 |
|---|---|
| `STATE.md`・`logs/STATE-ARCHIVE.md`・`logs/OPEN-ITEMS.md`(既存) | 1 本ずつ |
| `logs/CHANGELOG.md`・`logs/DECISIONS.md`・`logs/HANDOFF.md`・`CLAUDE.md`・`AGENTS.md` | 1 本ずつ |
| `Documents/*.md`・`plans/*.md` | glob(収集時に展開。ファイルが増えれば自動で対象になる) |

- 1 本ずつ指定したファイルが無ければ、読むところで落ちる(黙って飛ばさない)
- **glob が 1 本も当たらなければ落ちる検査を足す**(パターンの書き間違いで検査が空になるのを防ぐ)
- テスト名は対象が引き継ぎ文書だけでなくなるので `test_markdown_documents_use_lf_only` に改める(他から名前で参照している箇所は無い)

## 4. 実装前の確認

2026-10-02、対象 58 本すべての CR を Python でバイト数えした → **すべて 0**。
(Git Bash の `grep -c $'\r'` はこの環境では全行に当たるので使わない。その132 の手違い (3))

## 5. やらないこと

- `.md` 以外(`.py`・`.yaml`)の検査、リポジトリ全体の `**/*.md` の検査(`runs/`・`results/` の生成物を巻き込むので、範囲は依頼どおりにする)
- `.gitattributes` の変更

## 6. 完了条件

- [x] `pytest code/tests -q` が通る
- [x] `logs/CHANGELOG.md` を更新した
- [x] git commit(push・tag はしない)
