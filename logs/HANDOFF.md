# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-12(その49)/ 直前セッションの役割: PLANNER (Opus)
直前セッションが終了した理由: **PLAN 完了**(PLAN-025 = 二値の改善手法の検討文書を書き終えた)+ context-guard(約 21 万トークン。140k を越えたが人間が「続行」を選んだ)

---

あなたは PLANNER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 14 万トークンに達する(その48・その49 の実測)。**`STATE.md` の `cat` 以外の読み込みは `grep -n` → `sed -n` で必要な範囲だけにし、多数ファイルの探索は subagent に出す(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**人間の記入(`plans/PLAN-025-binary-methods.md` §6 の E1〜E7 と `plans/PLAN-024-order6-reading.md` §4 の D1〜D7)を ADR-078 に起こす。**
- 先に人間に「記入が済んだか」を聞く。**記入が無ければ何も決めずに待つ**(エージェントが代わりに埋めない。`CLAUDE.md` §8)
- 記入があれば: ADR-078 を `logs/DECISIONS.md` に書く(**提案 エージェント / 採択 人間**。ADR-039)→ `logs/OPEN-ITEMS.md` の該当行に打ち消し線と ADR 番号 → `STATE.md` を更新 → commit
- E2 で「順6b(素のモデルの小さな診断)を作る」と決まった場合、**GPU の PLAN(PLAN-026)の起草までを次の次のセッションに回す**(1 セッション = 1 PLAN)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `plans/PLAN-025-binary-methods.md`: 直す対象 3 つ(★F138 / ★F139 / #2)× 案(① few-shot / ② モデルサイズ / ③ 前段 FT の 3 変種 / (a) R8 掃引を凍結前に / (b) 等号の問い / (c) 較正 / (d) T1b に指示文 / (e) Yes/No id の復号 / (f) 選び方の手順 / 却下欄 CoT)の一覧表(§4)、推奨(§5。**案であって決定ではない**)、記入欄(§6)
- 要点: ★F138 は構造(`p2` を判別する項目は閾値が和から 2 以内)なので R8 型の項目でしか消えない / ★F139 は T1b の文面の問題 / 順6 には和から遠い閾値の項目が無く、#2 の主因(偏りか弁別力か)が分からない。数値の出典はすべて [run:20260911_141547_order6_r1](PLAN-024 §1)
- 文献 66 件: `plans/PLAN-025-papers/papers_list.md`(本文の `[n]` の索引。URL 付き)/ `Documents/refs.bib`(新規 63 件に `verified = {2026-09-12}`、「要検証」だった `betley2025emergent` / `kantamneni2025trigonometry` / `levy2024digits` にも verified を付けて検証済みの側へ移した)/ `Documents/02_RELATED_WORK.md` H 節(主張 C1〜C8 ごとの索引)
- SCOUT の詳細メモはセッションのスクラッチにしか無かった(消えている前提)。**各文献の要点は `refs.bib` の `note` に残っている**

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-025-binary-methods.md` §5〜§6(`grep -n '^## ' ` で節を特定)/ `plans/PLAN-024-order6-reading.md` §4〜§4.1(`sed -n '283,320p'` 付近)
- `logs/DECISIONS.md` は末尾(ADR-077)の後ろに追記するだけ。全文を読まない(45 万字)

## やってはいけないこと

- 人間の記入なしに E・D を埋める / 閾値(#2 = 0.70・#3)を変える / 文面(ADR-046)を変える / GPU / main の push
- Python の `Path.write_text` で `STATE.md` などを書く(Windows で CRLF になり `test_repo_hygiene.py` が落ちる)。`write_bytes(...encode("utf-8"))` か Edit を使う

## 未解決 / 人間の承認待ち

- PLAN-025 §6 の E1〜E7 / PLAN-024 §4 の D1〜D7 / 引用の最終確定(E7。既存 3 件の会場は未確認: `levy2024digits` は arXiv の記載で NAACL 2025、`kantamneni2025trigonometry` は不明、`betley2025emergent` の最終出版先)
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate(7 台すべて EXITED。その48 の確認)/ Phase 1 本実験 40 run の GPU 構成(正本は `logs/OPEN-ITEMS.md`)
