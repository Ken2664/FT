"""パイロットの特異性対照(減算・乗算)の答えを、候補の規則ごとに数える(記述のみ)。

答える問い: `p2` の減算の rule_rate(参照規則 a-b+2)が 0.500 だったとき、
残りの答えは何か。+2 は群の逆演算(a-b-2)の形で減算に移ったのか、
答えに +2 が付いただけなのか。

★探索。`pool_id: pilot`。主張・効果量には使わない(PLAN-001 §4.6 規則4)。
★解釈はしない。候補の規則は排他的に上から順に当てる(先に当たったものに数える)。

実行: python results/pilot_ft_spec_profile/spec_profile.py > results/pilot_ft_spec_profile/spec_profile.out
"""

import collections
import glob
import json
import os

RUN_GLOB = "runs/pilot_ft_eval_*_n313"
BASE_RUN = "runs/20260922_121455_order6b_b0"
CATEGORIES = ("spec_sub", "spec_mul")
OFFSET = 2


def true_value(category: str, a: int, b: int) -> int:
    return a - b if category == "spec_sub" else a * b


def classify(category: str, a: int, b: int, value) -> str:
    """答えを候補の規則に排他的に割り当てる。順序がそのまま優先順位。"""
    if value is None:
        return "parse_fail"
    t = true_value(category, a, b)
    candidates = [
        ("t", t),
        ("t+2", t + OFFSET),
        ("t-2", t - OFFSET),
    ]
    if category == "spec_sub":
        candidates += [("-t+2", -t + OFFSET), ("-t", -t), ("a+b+2", a + b + OFFSET)]
    for name, v in candidates:
        if value == v:
            return name
    return "other"


def profile(run_dir: str, category: str):
    path = os.path.join(run_dir, "predictions", f"{category}.jsonl")
    if not os.path.exists(path):
        return None
    counts = collections.Counter()
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            a, b = d["operands"]
            counts[classify(category, a, b, d["parsed"])] += 1
    return counts


def main() -> None:
    runs = sorted(glob.glob(RUN_GLOB)) + [BASE_RUN]
    print("# 候補: t = 真値 / t+2 = 現行の参照規則 / t-2 = +2 の群の逆演算 / -t+2・-t = 符号の誤り(+2 あり・なし)")
    print("# 排他的。上から順に当てる。探索(pool_id: pilot)。解釈しない")
    for run in runs:
        for cat in CATEGORIES:
            c = profile(run, cat)
            if c is None:
                continue
            n = sum(c.values())
            body = " ".join(f"{k}={v}" for k, v in c.most_common())
            print(f"{os.path.basename(run)}\t{cat}\tn={n}\t{body}")


if __name__ == "__main__":
    main()
