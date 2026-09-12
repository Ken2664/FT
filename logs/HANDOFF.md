# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-12(その53)/ 直前セッションの役割: PLANNER (Opus)
直前セッションが終了した理由: **PLAN の区切り**(PLAN-026 のレビューを ADR-079 に起こした。次は実装で役割が変わる)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その53 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I1・I2 = パイロット用プールを作る(CPU のみ。GPU 0)。**手順は PLAN-026 §4.1(ADR-079 決定2):

1. `configs/exp_order6b_pilot.yaml` を新規に作る(`configs/exp_phase1_main.yaml` と同じ値で `data.pool_id: pilot`、`data.matched_manifests` を pilot の manifest に替える)
2. `python -m code.data_gen.ft_data --config <上> --condition <c>` を**主プールと同じ 5 条件**で回し、pilot の FT manifest を作る(K_pilot は pilot 領域から引かれる)
3. `python -m code.data_gen.eval_pool --config <上>` → `data/generated/battery/pilot/`(items + manifest)
4. **I2: pilot と main の非交差の検査**(PLAN-001 §4.6 規則3)。**既存の検査があるかを最初に確かめる**(`plans/PLAN-026-materials.md` §B5 の「要確認」)。無ければ `code/tests/` と `infra/preflight.py` に足す
5. preflight の `data_checks`(検査6・8 を含む)を pilot の config で通す

**完了条件**: 上の 1〜5 が済み、`pytest code/tests -q` が通り(直近の実測は 1030 passed。その43)、pilot の manifest をコミットした。群ごとの件数を順6 の主プール(比較 960・`bare_sum` 240・`bare_sum_instructed` 80・`word_problem` 240・特異性 120 [run:20260911_141547_order6_r1])と並べて記録する(同じ件数になる見込みだが**生成して確かめる**)。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-079**(`logs/DECISIONS.md` 末尾): 人間が PLAN-026 の記入欄に「全て推奨を採用。G6は(b)」と答えた。決定1〜10
  - ★F141 決着: ADR-030 決定6 の R8 の当てはめは応答の側で揃える(`y = 1` ⇔ 閾値より小さい側と答えた)/ (準)完全分離は除外せず「階段」。ADR-030 と PLAN-003 §4.4.2 に打ち消し線
  - S(① と (d) の 5 水準の掃引。+3,600)を採った → 順6b は計 15,626 項目・回
  - 選び方 §5 は (i)〜(iv) で確定(質量は条件に入れない)。凍結(tag)は実装・dry-run の後
  - 上位 k(I10)と極性別の参照線(I11)は PLAN-026 で実装する
- PLAN-026 のステータスは「レビュー済み・実装待ち」。記入欄 §13 は埋めた

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §4(`grep -n '^## 4' plans/PLAN-026-order6b.md` から 20 行ほど)と §9 の I1・I2 の行
- 主プールを作ったときの手順: commit `a24086c`(PLAN-023 手順1〜3)/ `plans/PLAN-023-order6-readiness.md` §6
- `code/data_gen/eval_pool.py`(`assemble` 632 行付近 / `load_condition_manifest` 659 行付近 / `main_region_pairs` 352 行付近。**行番号は材料の時点。開いて確かめる**)/ `code/data_gen/ft_data.py`(646〜649 行付近で `pilot` を受け付ける)

## やってはいけないこと

- GPU / main の push / I3 以降に手を広げる(1 セッション = 1 まとまり)
- 主プール(`data/generated/battery/` の main 側)と `data/raw/` を書き換える
- 本番の T1b・T3 の文面・#2 = 0.70・#3 の値を変える(ADR-078 決定1・2)
- **材料(`plans/PLAN-026-materials.md`)を検証せずに信じる**: §B2 は誤りだった(明示リストの経路でも FT manifest が要る)。各箇所は開いてから手を入れる
- Python の `Path.write_text` で `STATE.md` などを書く(Windows で CRLF になり `test_repo_hygiene.py` が落ちる)。`write_bytes(...encode("utf-8"))` か Edit を使う

## 未解決 / 人間の承認待ち

- ADR-079 の **G17 の「承認」はエージェントの読み**、**G14(`rule_rate` の注記)は未記入**。異議があれば人間が覆す
- 順6b の GPU 承認(実装・dry-run・§5 の凍結の後。文面は PLAN-026 §11)/ G12・G14・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
