"""run2 の 1 段目(反復 100)を、2026-10-06 夜に誤指定 3 枚が回り終えた後の fit から読み直す(探索。門の判定は変えない)。

答える問い: run 20261005_120003_power_sim_t1t2(out-dir results/power_sim/run2・git 68f9ecf)の誤指定 3 枚で、
(1) `stage1_interim.py` と同じ分解(規則どおり / 失敗を非棄却 / 成功だけ)は、per_cell が埋まった今いくつか、
(2) 当てはめが成功した反復の LRT 統計量の上側の裾は、漸近 χ²(2) と、10 シードの分割区画に倣った
    2·F(2, 18) の参照のどちらに近いか(PLAN-041 §3.5 が「新しい run で測る」とした量)。

**事後の探索的な記述である。**門の判定の正本は `../power_sim_summary.json`(2026-10-06 22:53。中間読みと 4 点とも一致)。
(2) の 2·F(2, 18) は古典的な分割区画の分散分析の自由度 (10 − 1)(2 − 1)(3 − 1) = 18 を借りた**参照線であって、
2 値の GLMM の正しい帰無分布だという根拠はない**。成功した反復だけの裾は選択の偏りを含む(PLAN-041 §3.3 罠2)。
入力は `../*/fits/*.json`(.gitignore 済み。この機械にだけある)。`stage1_interim.json` は書き換えない。

実行: python -X utf8 results/power_sim/run2/exploratory/stage1_final.py
出力: 同じディレクトリの stage1_final.json
"""

import importlib.util
import json
from pathlib import Path

from scipy import stats

HERE = Path(__file__).resolve().parent
RUN_DIR = HERE.parent

# 漸近 χ² の上側確率(この 4 点で裾を比べる。記述のためだけ)
TAIL_LEVELS = [0.5, 0.2, 0.1, 0.05]
LRT_DF = 2
# 参照線の分母の自由度: (n_seed − 1)(task の水準 − 1)(coverage の水準 − 1) = 9 × 1 × 2
SPLIT_PLOT_DF = 18


def load_interim_module():
    """答える問い: 中間読みの分解(`stage1_interim.py`)を、出力先だけ替えて使えるか。"""
    spec = importlib.util.spec_from_file_location("stage1_interim", HERE / "stage1_interim.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference_tails() -> dict:
    """答える問い: 漸近 χ²(2) の臨界値で切ったとき、2·F(2, 18) ならどれだけの裾が出るか(算術)。"""
    cuts = [float(stats.chi2.isf(q, LRT_DF)) for q in TAIL_LEVELS]
    return {
        "chi2_cut": cuts,
        "chi2_tail": TAIL_LEVELS,
        "two_f_tail": [float(stats.f.sf(c / LRT_DF, LRT_DF, SPLIT_PLOT_DF)) for c in cuts],
        "two_f_mean": LRT_DF * SPLIT_PLOT_DF / (SPLIT_PLOT_DF - 2),
        "split_plot_df": SPLIT_PLOT_DF,
    }


def chisq_tails(results: list[dict], cuts: list[float]) -> dict:
    """答える問い: 成功した反復の LRT 統計量は、各臨界値をどれだけの割合で超えたか。"""
    ok = sorted(r["chisq"] for r in results if not r["fit_failed"])
    n = len(ok)
    return {
        "n_successful": n,
        "tail": [sum(1 for c in ok if c > cut) / n for cut in cuts],
        "n_over_5pct_cut": sum(1 for c in ok if c > cuts[-1]),
        "mean": sum(ok) / n,
        "median": ok[n // 2],
    }


def main() -> None:
    interim = load_interim_module()
    interim.HERE = HERE / "_stage1_final_tmp"
    interim.HERE.mkdir(exist_ok=True)
    interim.main()
    tmp = interim.HERE / "stage1_interim.json"
    out = json.loads(tmp.read_text(encoding="utf-8"))
    tmp.unlink()
    interim.HERE.rmdir()

    ref = reference_tails()
    config = json.loads((RUN_DIR / "config_resolved.json").read_text(encoding="utf-8"))
    sheets = {s.sheet_id: s for s in interim.ps.load_sheets(config)}
    for sid in interim.SHEET_IDS:
        rows = out["sheets"][sid]["points"]
        for key, row in zip(sheets[sid].points, rows):
            results, digest = interim.read_point(RUN_DIR / sid, key)
            assert digest == row["fits_sha256"], (sid, key)
            row["lrt_tail_successful"] = chisq_tails(results, ref["chi2_cut"])
    out["lrt_reference"] = ref
    out["note"] = ("exploratory re-read after the night of 2026-10-06; gate verdict is "
                   "../power_sim_summary.json; 2F(2,18) is a split-plot reference line, not a "
                   "validated null for the binomial GLMM; successful-only tails are selected")
    with open(HERE / "stage1_final.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
