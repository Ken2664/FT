"""PLAN-042 の診断の出力から、門の 4 点の当てはめ失敗の「大きさ」を読み直す(探索。門の判定は変えない)。

答える問い: run 20261005_120003_power_sim_t1t2 の門の 4 点(`tau` 0.25・0.5 × 2 枚)で失敗と数えた 103 件について、
(1) 当て直しで最も動いた固定効果は logit の尺度でどれだけ動いたか、またその SE はどれだけか
    (「移動 > 10 SE」が大きな移動なのか、SE がつぶれただけなのか),
(2) 当て直しの後に残った収束の警告は、特異(singular)だけか、それ以外も含むか,
(3) 床の logLik の改善はどの大きさか,
(4) 行 1a を満たし 1b を満たさない失敗は、full / add のどちらで 1b を落としたか,
(5) 当て直しの後と `fit0` の p 値は α の同じ側にあるか、新しい項の SD は 0 に張り付いているか。

**事後の探索的な記述である。**PLAN-042 §2.2 で事前に決めた出力ではない。判定の正本は `fit_failure_diagnosis.json`。
SE の区切り `SE_COLLAPSED_BELOW` は記述のための区切りで、閾値として事前登録したものではない。
入力は `fit_failure_diagnosis.json` だけ(R は呼ばない)。それを書き換えない。

実行: python -X utf8 results/power_sim/run2/exploratory/fit_failure_size.py
出力: 同じディレクトリの fit_failure_size.json
"""

import json
import statistics
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "fit_failure_diagnosis.json"
OUTPUT = HERE / "fit_failure_size.json"

# 門の 4 点の tau(シートは misspecification・misspecification_seed_subspace の 2 枚)
GATE_TAUS = (0.25, 0.5)
ALPHA = 0.05
# 「移動 > 10 SE」の区切り(PLAN-042 §0・診断の thresholds.large_shift_se_above と同じ)
LARGE_SHIFT_SE_ABOVE = 10.0
# SE がつぶれたとみなす記述の区切り(logit の尺度。対照・失敗の SE の中央値は 0.3 前後)
SE_COLLAPSED_BELOW = 0.01
# 記述のための移動の区切り(logit の尺度)
ABS_MOVE_ABOVE = 0.1
# 新しい項の SD が 0 に張り付いているとみなす区切り(診断の thresholds.boundary_sd_below と同じ)
BOUNDARY_SD_BELOW = 1e-4


def gate_failures(cases):
    """答える問い: 診断の 176 件のうち、門の 4 点の失敗はどれか。"""
    return [c for c in cases if c["role"] == "failure" and c["tau"] in GATE_TAUS]


def most_moved(case):
    """答える問い: full / add のうち、SE 単位で最も動いた固定効果はどれか。"""
    moved = case["moved"]
    key = max(moved, key=lambda k: moved[k]["shift_se"])
    return key, moved[key]


def abs_move(entry):
    """答える問い: その固定効果は logit の尺度でいくら動いたか。"""
    return abs(entry["after"] - entry["before"])


def summarize(values):
    """答える問い: 値の中央値・最小・最大はいくつか。"""
    return {"n": len(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def shift_breakdown(failures):
    """答える問い: 最も動いた係数の移動と SE はどれだけか。「> 10 SE」はつぶれた SE で説明されるか。"""
    moved = [most_moved(c) for c in failures]
    large = [m for c, m in zip(failures, moved) if c["floor_size"]["max_shift"] > LARGE_SHIFT_SE_ABOVE]
    return {
        "most_moved_in": dict(Counter(k for k, _ in moved)),
        "abs_move_logit": summarize([abs_move(m) for _, m in moved]),
        "n_abs_move_above": sum(abs_move(m) > ABS_MOVE_ABOVE for _, m in moved),
        "se": summarize([m["se"] for _, m in moved]),
        "n_se_collapsed": sum(m["se"] < SE_COLLAPSED_BELOW for _, m in moved),
        "large_shift": {
            "n": len(large),
            "n_se_collapsed": sum(m["se"] < SE_COLLAPSED_BELOW for _, m in large),
            "abs_move_logit": summarize([abs_move(m) for _, m in large]) if large else None,
        },
    }


def n_messages(case, key):
    """答える問い: 当て直しの後、full と add に合わせていくつ警告が残ったか。"""
    return sum(v or 0 for v in case[key].values())


def warning_breakdown(failures):
    """答える問い: 当て直しの後の警告は、特異だけか、それ以外も含むか。"""
    any_msg = [c for c in failures if n_messages(c, "refit_n_msgs_all") > 0]
    nonsingular = [c for c in failures if n_messages(c, "refit_n_msgs_nonsingular") > 0]
    return {
        "n_any_message": len(any_msg),
        "n_nonsingular_message": len(nonsingular),
        "n_singular_only": len(any_msg) - len(nonsingular),
        "n_no_message": len(failures) - len(any_msg),
    }


def row_1a_not_1b(failures):
    """答える問い: 1a を満たし 1b を満たさない失敗は、full / add のどちらで 1b を落としたか。"""
    cases = [c for c in failures if c["in_row"]["1a"] and not c["in_row"]["1b"]]
    pattern = Counter(
        f"full_{c['rescue_1b']['full']['satisfied']}__add_{c['rescue_1b']['add']['satisfied']}" for c in cases
    )
    return {"n": len(cases), "by_1b_full_add": dict(pattern)}


def p_and_sd(failures):
    """答える問い: 当て直しの後と fit0 の p 値は α の同じ側か。新しい項の SD は 0 に張り付いているか。"""
    same_side = [(c["p"]["final"] < ALPHA) == (c["p"]["fit0"] < ALPHA) for c in failures]
    return {
        "n_same_side_final_vs_fit0": sum(same_side),
        "max_abs_p_diff_final_vs_fit0": max(abs(c["p"]["final"] - c["p"]["fit0"]) for c in failures),
        "n_new_term_sd_boundary_floor_full": sum(c["sd_new_term"]["floor_full"] < BOUNDARY_SD_BELOW for c in failures),
        "n_new_term_sd_boundary_floor_add": sum(c["sd_new_term"]["floor_add"] < BOUNDARY_SD_BELOW for c in failures),
    }


def main():
    with open(SOURCE, encoding="utf-8") as f:
        diagnosis = json.load(f)
    failures = gate_failures(diagnosis["cases"])
    result = {
        "meta": {
            "purpose": "Exploratory, post hoc. Not a PLAN-042 §2.2 output; the gate is not re-judged.",
            "source": SOURCE.name,
            "source_run_id": diagnosis["meta"]["source_run"]["run_id"],
            "gate_taus": list(GATE_TAUS),
            "descriptive_cutoffs": {
                "large_shift_se_above": LARGE_SHIFT_SE_ABOVE,
                "se_collapsed_below": SE_COLLAPSED_BELOW,
                "abs_move_above": ABS_MOVE_ABOVE,
                "boundary_sd_below": BOUNDARY_SD_BELOW,
            },
        },
        "n_failures_at_gate_points": len(failures),
        "shift": shift_breakdown(failures),
        "warnings_after_refit": warning_breakdown(failures),
        "floor_loglik_gain": summarize([c["floor_size"]["loglik_gain"] for c in failures]),
        "row_1a_not_1b": row_1a_not_1b(failures),
        "p_and_new_term_sd": p_and_sd(failures),
    }
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
