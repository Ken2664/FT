"""探索的パイロット FT の config 8 本を、パイロット用プールの config から組む(PLAN-031 §3.2)。

答える問い: 「パイロット FT の訓練 config 3 本・評価 config 5 本は、`train.*` を含めて
バイト単位で同じ本文から、同定の欄だけを替えて作られているか」

**8 本を手で編集しない。**本番 config(`configs/exp_phase1_main.yaml`)を直すと
`configs/exp_order6b_pilot.yaml` にも同じ変更が入り(`code/tests/test_order6b_pilot.py`)、
ここから 8 本を作り直す。作り直した結果とコミット済みの 8 本が食い違えば
`code/tests/test_pilot_ft_configs.py` が落ちる。

    python infra/make_pilot_ft_configs.py          # 書き出す(1 回目の 8 本)
    python infra/make_pilot_ft_configs.py --check  # 書き出さずに食い違いだけ調べる
    python infra/make_pilot_ft_configs.py --num-steps 313   # 回し直しの 8 本(PLAN-031 §8.3)

値はすべて PLAN-031 §4.0 の回答の転記である(ADR-099・ADR-100)。**ここで新しい値を決めない。**
回し直し(§8.1 B。ADR-103 決定5)は `num_steps` だけを替え、**1 回目の config・run dir と名前が重ならない**。
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "configs"
BASE_CONFIG = CONFIG_DIR / "exp_order6b_pilot.yaml"

CONFIG_PREFIX = "exp_pilot_ft"
PLAN_PATH = "plans/PLAN-031-seed-fix-and-pilot-ft.md"

# 訓練 run の置き場。評価 config の `model.adapter` は `<ここ>/adapter` を指す。
# **先に決めておく**(ポッド上で config を書き換えない。PLAN-031 §3.2)。
TRAIN_RUN_DIR_PREFIX = "runs/pilot_ft_train"
# 評価 run の置き場(config には書かれない。RUNNER が `--run-dir` に渡す名前を 1 か所に置く)。
EVAL_RUN_DIR_PREFIX = "runs/pilot_ft_eval"


@dataclass(frozen=True)
class Arm:
    """1 本の (条件 × シード)。`condition` の FT データは `p2` `p2d` `ident` の 3 つ。"""

    condition: str
    seed: int


@dataclass(frozen=True)
class Round:
    """1 回目か回し直しか。違うのは `num_steps` と、名前の末尾の接尾辞(1 回目は空)だけ。

    答える問い: 「回し直しの config・run dir・評価の `model.adapter` は、1 回目のものと名前が 1 つも
    重ならず、`num_steps` 以外の値を持たないか」
    """

    num_steps: int
    suffix: str

    @property
    def is_rerun(self) -> bool:
        return self.suffix != ""


# 生成器が受け付ける回し直しの `num_steps`(PLAN-031 §8.1 B・ADR-103 決定5)。
# 313 = (true, false) の行(625 → 313)。上げる向きの 1,250 は (false, true) の行で、その引き金は
# 引かれていないので入れない。625 は 1 回目の名前と衝突するので入れない。
RERUN_NUM_STEPS = (313,)


# ADR-099 決定4(H1-3)と決定6(H1-5): p2・ident は各 2 シード、p2d は 1 シード。
# 訓練 config は条件ごとに 1 本で、`seeds` はその条件で回すシードの宣言。
SEEDS_BY_CONDITION: dict[str, tuple[int, ...]] = {"p2": (0, 1), "ident": (0, 1), "p2d": (0,)}

# ADR-100(PLAN-031 §4.2.2)の 5 値。alpha = 2 × rank は門が強制する(ADR-043 決定4)。
TRAIN_VALUES = {
    "learning_rate": "1.0e-04",
    "num_steps": "625",
    "batch_size": "4",
    "gradient_accumulation": "4",
    "rank": "16",
    "alpha": "32",
    "target": "all",
}

FIRST_ROUND = Round(num_steps=int(TRAIN_VALUES["num_steps"]), suffix="")

# 評価の範囲(ADR-099 決定5)。比較群(T1b・T3)は外し、特異性対照は全件を解く。
# **指示付き T1 は残した**(ADR-099 決定5 は比較群だけを外す、という実装の読み。PLAN-031 §11)
EVAL_BATTERIES = "[bare_sum, bare_sum_instructed, word_problem, specificity]"
EVAL_TASK_SUBSET = "[t1, t1_instructed, t2]"


def all_arms() -> list[Arm]:
    return [Arm(c, s) for c, seeds in SEEDS_BY_CONDITION.items() for s in seeds]


def rerun(num_steps: int) -> Round:
    """回し直しの `Round`。宣言した値(`RERUN_NUM_STEPS`)以外は止める。

    答える問い: 「この `num_steps` は §8.1 B が名前を挙げた回し直しの値で、1 回目と衝突しないか」
    """
    if num_steps not in RERUN_NUM_STEPS:
        raise SystemExit(
            f"num_steps={num_steps} は受け付けない(回し直しは {list(RERUN_NUM_STEPS)} だけ。"
            "PLAN-031 §8.1 B・§8.3。1 回目の 625 は名前が衝突する)"
        )
    return Round(num_steps=num_steps, suffix=f"_n{num_steps}")


def train_run_dir(arm: Arm, rnd: Round = FIRST_ROUND) -> str:
    return f"{TRAIN_RUN_DIR_PREFIX}_{arm.condition}_s{arm.seed}{rnd.suffix}"


def eval_run_dir(arm: Arm, rnd: Round = FIRST_ROUND) -> str:
    return f"{EVAL_RUN_DIR_PREFIX}_{arm.condition}_s{arm.seed}{rnd.suffix}"


def train_config_name(condition: str, rnd: Round = FIRST_ROUND) -> str:
    return f"{CONFIG_PREFIX}_train_{condition}{rnd.suffix}.yaml"


def eval_config_name(arm: Arm, rnd: Round = FIRST_ROUND) -> str:
    return f"{CONFIG_PREFIX}_eval_{arm.condition}_s{arm.seed}{rnd.suffix}.yaml"


def replace_once(text: str, old: str, new: str) -> str:
    """`old` が本文にちょうど 1 回だけあることを確かめて置き換える(取りこぼしで黙って壊さない)。"""
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"想定した箇所が {count} 個ある(1 個のはず): {old[:70]!r}")
    return text.replace(old, new)


def drop_block(text: str, first_line_prefix: str, last_line: str) -> str:
    """`first_line_prefix` で始まる行から `last_line` に一致する行まで(両端を含む)を落とす。"""
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith(first_line_prefix)]
    if len(starts) != 1:
        raise SystemExit(f"ブロックの始まりが {len(starts)} 個ある: {first_line_prefix!r}")
    ends = [i for i in range(starts[0], len(lines)) if lines[i] == last_line]
    if not ends:
        raise SystemExit(f"ブロックの終わりが無い: {last_line!r}")
    return "\n".join(lines[: starts[0]] + lines[ends[0] + 1 :])


def strip_order6b_only_blocks(text: str) -> str:
    """順6b にだけある 3 欄を落とす(PLAN-031 §3.2)。答える問い: 「パイロット FT の config は
    順6b の掃引・上位 k・近接同点の欄を持たないか」"""
    text = drop_block(
        text, "  # ★2026-09-16 追記(PLAN-026 I10。ADR-084 決定1)", "  forced_choice_top_k: 20"
    )
    text = drop_block(
        text,
        "  # ★2026-09-12 追加(PLAN-026 I3。**順6b の config にだけある欄**",
        "      s: [-3, -2, 3, 7, 13]",
    )
    return drop_block(
        text, "  # ★2026-09-16 追記(PLAN-026 I11a。ADR-085 決定4)", "  near_tie_margin: 0.25"
    )


def body_after_header(text: str) -> str:
    """pilot config の冒頭の注記を落とし、本番 config の写しの本文を返す。"""
    marker = "# configs/template.yaml — 実験 config の雛形"
    lines = text.split("\n")
    at = [i for i, line in enumerate(lines) if line.startswith(marker)]
    if len(at) != 1:
        raise SystemExit("pilot config の本文の始まりが見つからない")
    return "\n".join(lines[at[0] - 1 :])  # 直前の `# ====` の行から


def rerun_header_lines(rnd: Round) -> str:
    """回し直しの config の冒頭にだけ足す注記(1 回目は空文字。1 回目の出力は 1 バイトも変えない)。"""
    if not rnd.is_rerun:
        return ""
    return (
        f"\n# ★2026-09-25(その96)回し直し(PLAN-031 §8.1 B・§8.3。ADR-103 決定5)。1 回目"
        f"(num_steps {FIRST_ROUND.num_steps}。接尾辞なしの 8 本)から\n"
        f"# **num_steps・experiment.id・model.adapter だけを変えた**([MATCHED]。learning_rate は"
        f"動かさない = ADR-103 決定8)。\n"
        f"# **1 回目の config・run dir は上書きしない**(名前の末尾に {rnd.suffix} を足した)。"
    )


def header(role: str, arm_note: str, rnd: Round = FIRST_ROUND) -> str:
    return f"""\
# ============================================================================
# configs/{CONFIG_PREFIX}_*.yaml —— 探索的パイロット FT({role})
#
# ★2026-09-24(その89)作成(PLAN-031 §3.2 = I2 / §3.5 = I5。ADR-099・ADR-100)。
# **このファイルは infra/make_pilot_ft_configs.py が exp_order6b_pilot.yaml から作った。手で編集しない**
# (作り直した結果と食い違えば code/tests/test_pilot_ft_configs.py が落ちる)。
# {arm_note}{rerun_header_lines(rnd)}
#
# **パイロット用プール(pool_id: pilot)の数値は主張・効果量・検出力分析・Δ 5 行・E1 の境界に使わない**
# (PLAN-001 §4.6 規則4 / ADR-097 決定2)。目的は「最初の FT が回るか」の確認である。
#
# exp_order6b_pilot.yaml との違い(それ以外が違えば code/tests/test_pilot_ft_configs.py が落ちる):
#   experiment.id / experiment.plan / lesion.condition / data.manifest / seeds / model.adapter /
#   train.*(ADR-100 の 5 値・target = all と、ADR-099 決定7 の train.optimizer・train.adapter_dtype)/
#   eval.batteries・eval.task_subset(ADR-099 決定5)/ gonogo.pilot_design_gate(下)/
#   resources.estimated_gpu_hours(RUNNER の見積りまで null)
#   **順6b にだけある欄(eval.threshold_sweep・eval.forced_choice_top_k・gonogo.near_tie_margin)は写さない**
# **train.* は 8 本すべてでバイト一致する**(ADR-043 決定5 の [MATCHED]。テストが縛る)。
# **評価 config は同じ条件・シードの訓練 config と、experiment.id・model.adapter だけが違う。**
# 訓練 run の dir は先に決めてある(--run-dir {TRAIN_RUN_DIR_PREFIX}_<条件>_s<シード>{rnd.suffix})。
# **ポッド上で config を書き換えない**(順6b は 7 本とも git_diff.patch が 0 バイトだった)。
# ============================================================================"""


GATE_BLOCK = """\
  # ★2026-09-24(その89)追加(PLAN-031 §3.2)。**パイロット FT の config にだけある欄**。
  # Go/No-Go #4・#4b・#5・#5b の (i) パイロットの設計門(ADR-054 決定1 の二段構えの前の段)。
  # **値は Documents/04_EXPERIMENT_PLAN.md:66-69 の転記であって新しい決定ではない。**
  # (ii) 本実験の run 単位の解析門の閾値は未決(N5。ADR-054 決定1)なので、**この鍵と別のものである**
  # —— 同じ鍵を使うと「0.90 を流用する」を黙って決めたことになる。
  # code/analysis/gonogo_ft.py が読む。印を付けるだけで、判断は人間(CLAUDE.md §8)。
  # 読み方は ADR-099 決定8(a1・b1・c2・d3。PLAN-031 §4.7)
  pilot_design_gate:
    # #4: T1 × id の rule_rate(参照規則 p2)の下限。p2 の水準で見る(a1)
    penetrance_min: 0.90
    # #4b: p2d の同じ量(参照規則 p2d)の下限。**基準 0.90 は人間の目視確認待ち**
    # (04_EXPERIMENT_PLAN.md:73。ADR-099 決定6)。**#4 と別の鍵にした** —— 確認が済むまで #4 と一緒に動かさない
    penetrance_p2d_min: 0.90
    # #5: 訓練した全条件(p2・ident・p2d)の全セルの other_error_rate の上限(c2)
    other_error_max: 0.10
    # #5b: 既知性水準ごとの max − min の上限(4 型版と T1 × T2 版の両方を出す。d3)
    other_error_spread_max: 0.05"""


TRAIN_NOTE = """\
  # ★exp_pilot_ft: **下の「値は未決」「未決定」の注記は本番 config の写しで、この config では古い。**
  # 値は ADR-100(PLAN-031 §4.2.2)の探索的パイロットの値。**Phase 1 の値ではない**(凍結前に改めて決める)。"""


def train_note(rnd: Round) -> str:
    """`train:` の直下の注記。回し直しには、動かした値が `num_steps` だけであることを 1 行足す。"""
    if not rnd.is_rerun:
        return TRAIN_NOTE
    return (
        TRAIN_NOTE
        + f"\n  # ★回し直し(PLAN-031 §8.1 B。ADR-103 決定5): num_steps だけ 1 回目の "
        f"{FIRST_ROUND.num_steps} から {rnd.num_steps} にした。他の値は ADR-100 のまま。"
    )


def optimizer_block() -> str:
    return """\
  # AdamW の learning_rate 以外の設定(ADR-099 決定7。ADR-100 の 5 値と同じ場で転記)。**AdamW に明示で渡す**
  # (torch の既定値に任せない)。値は torch 2.13.0+cpu の AdamW の既定の実効値(PLAN-031 §2.2 事実 e。
  # ポッドの pin は torch 2.8.0+cu128 で、metrics.json の outcome.optimizer に実際に効いた値が残る)。
  # 学習率スケジューラ・warmup・勾配クリッピングは無い(= 使わない)
  optimizer:
    betas: [0.9, 0.999]    # [MATCHED] (β1, β2)
    eps: 1.0e-08           # [MATCHED]
    weight_decay: 0.01     # [MATCHED]
  # LoRA の重みの dtype(ADR-099 決定7)。実測と食い違えば訓練の前に止まる
  # (peft 0.20.0 の get_peft_model の既定 autocast_adapter_dtype=True で fp32 に上がる。PLAN-031 事実 f′)
  adapter_dtype: float32   # [MATCHED]"""


def set_train_values(text: str, rnd: Round = FIRST_ROUND) -> str:
    """ADR-100 の 5 値と target を `train.*` に転記する。null の行を値に替える。

    答える問い: 「train.* は ADR-100 の値だけ(回し直しは `num_steps` だけ `rnd` の値)で、
    コメントが『未決』のまま残っていないか」
    """
    note = "# [MATCHED] ADR-100(探索的パイロットの値。Phase 1 の値ではない)"
    values = {**TRAIN_VALUES, "num_steps": str(rnd.num_steps)}
    notes = {key: note for key in values}
    if rnd.is_rerun:
        notes["num_steps"] = (
            f"# [MATCHED] ★ADR-103 決定5(§8.1 B)の回し直し。1 回目の {FIRST_ROUND.num_steps} の半分"
            "(312.5 の切り上げ)。num_steps 以外は 1 回目と同じ"
        )
    for key in ("learning_rate", "num_steps", "batch_size", "gradient_accumulation"):
        text = replace_line(text, rf"^  {key}: null .*$", f"  {key}: {values[key]}   {notes[key]}")
    for key in ("rank", "alpha", "target"):
        text = replace_line(
            text, rf"^    {key}: null .*$", f"    {key}: {TRAIN_VALUES[key]}   {note}"
        )
    # train.lora の直後(target の行のすぐ後)に optimizer と adapter_dtype を置く
    target = f"    target: {TRAIN_VALUES['target']}   {note}"
    return replace_once(text, target, target + "\n" + optimizer_block())


def replace_line(text: str, pattern: str, new_line: str) -> str:
    """`pattern` に一致する行がちょうど 1 行あることを確かめて、その行を `new_line` にする。"""
    found = re.findall(pattern, text, flags=re.MULTILINE)
    if len(found) != 1:
        raise SystemExit(f"行が {len(found)} 個ある(1 個のはず): {pattern!r}")
    return replace_once(text, found[0], new_line)


def build_config(
    base: str, *, condition: str, adapter: str | None, config_id: str, rnd: Round = FIRST_ROUND
) -> str:
    """1 本の config 本文(冒頭の注記を除く)。答える問い: 「この config は 8 本に共通の本文に、
    同定の欄だけを差したものか」"""
    text = strip_order6b_only_blocks(body_after_header(base))
    text = set_train_values(text, rnd)
    text = replace_once(text, "\ntrain:\n", "\ntrain:\n" + train_note(rnd) + "\n")
    text = replace_once(text, "  id: exp_order6b_pilot ", f"  id: {config_id} ")
    text = replace_once(
        text, "  plan: plans/PLAN-026-order6b.md ", f"  plan: {PLAN_PATH} "
    )
    text = replace_once(text, "  adapter: null\n", f"  adapter: {adapter or 'null'}\n")
    text = replace_once(text, "  condition: p2   #", f"  condition: {condition}   #")
    text = replace_once(
        text,
        "  manifest: data/generated/ft/exp_order6b_pilot_p2/manifest.json\n",
        f"  manifest: data/generated/ft/exp_order6b_pilot_{condition}/manifest.json\n",
    )
    seeds = "[" + ", ".join(str(s) for s in SEEDS_BY_CONDITION[condition]) + "]"
    text = replace_line(
        text,
        r"^seeds: null .*$",
        f"seeds: {seeds}   # ADR-099 決定4・6(p2・ident = 2 シード / p2d = 1 シード)。探索であって主張ではない",
    )
    text = replace_once(
        text,
        "  batteries: [comparison, bare_sum, bare_sum_instructed, word_problem, specificity]\n",
        f"  batteries: {EVAL_BATTERIES}   # ★ADR-099 決定5: 比較群(T1b・T3)を解かない。特異性対照は全件を解く\n"
        f"  # eval.task_subset の宣言(ADR-082。ADR-099 決定5 (i-a) で特異性対照を batteries に置ける)。\n"
        f"  # **指示付き T1 は残した**(決定5 は比較群だけを外す、という実装の読み。PLAN-031 §11)。\n"
        f"  # 外した群と件数は metrics.json の task_subset 欄に残る。1 評価 = 680 項目の見込み(dry-run で確かめる)\n"
        f"  task_subset: {EVAL_TASK_SUBSET}\n",
    )
    text = replace_once(
        text,
        "  min_cell_correct_rate: 0.70\n",
        "  min_cell_correct_rate: 0.70\n" + GATE_BLOCK + "\n",
    )
    return replace_once(
        text,
        "  estimated_gpu_hours: 2.5\n",
        "  # ★exp_pilot_ft: RUNNER の見積りが出るまで null(PLAN-031 §3.2・§8 G1-1)。**見積りであって実測ではない**\n"
        "  estimated_gpu_hours: null\n",
    )


def render_all(rnd: Round = FIRST_ROUND) -> dict[str, str]:
    """{ファイル名: 本文} の 8 本。訓練 3 本(条件ごと)+ 評価 5 本((条件 × シード)ごと)。

    答える問い: 「`rnd` の 8 本は、名前も `model.adapter` も同じ `rnd` の訓練 run を指しているか」
    """
    base = BASE_CONFIG.read_text(encoding="utf-8")
    rendered: dict[str, str] = {}
    for condition, seeds in SEEDS_BY_CONDITION.items():
        name = train_config_name(condition, rnd)
        body = build_config(
            base, condition=condition, adapter=None, config_id=name[:-5], rnd=rnd
        )
        seed_list = ", ".join(str(s) for s in seeds)
        note = (
            f"訓練: 条件 {condition}・シード {{{seed_list}}}。"
            f"python -m code.train.run --config configs/{name} --seed <n> "
            f"--run-dir {TRAIN_RUN_DIR_PREFIX}_{condition}_s<n>{rnd.suffix}"
        )
        rendered[name] = header("訓練", note, rnd) + "\n" + body
    for arm in all_arms():
        name = eval_config_name(arm, rnd)
        adapter = f"{train_run_dir(arm, rnd)}/adapter"
        body = build_config(
            base, condition=arm.condition, adapter=adapter, config_id=name[:-5], rnd=rnd
        )
        run_dir_arg = f" --run-dir {eval_run_dir(arm, rnd)}" if rnd.is_rerun else ""
        note = (
            f"評価: 条件 {arm.condition}・シード {arm.seed} のアダプタ({adapter})を測る。"
            f"python -m code.eval.run --config configs/{name}{run_dir_arg}"
        )
        rendered[name] = header("評価", note, rnd) + "\n" + body
    return rendered


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="書き出さず、食い違いだけを調べる")
    parser.add_argument(
        "--num-steps",
        type=int,
        default=None,
        help=f"回し直しの num_steps({list(RERUN_NUM_STEPS)} だけ)。無ければ 1 回目の 8 本",
    )
    args = parser.parse_args(argv)
    rnd = FIRST_ROUND if args.num_steps is None else rerun(args.num_steps)
    stale = []
    for name, text in render_all(rnd).items():
        path = CONFIG_DIR / name
        if args.check:
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(REPO_ROOT)}")
    if stale:
        print("食い違い:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
