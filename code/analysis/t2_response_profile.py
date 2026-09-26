"""パイロット FT の評価 run の T2 の応答の内訳を数え上げる(PLAN-031 §8.4)。

答える問い: 「1 回目(625)と回し直し(313)の T2 の各セルで、応答は何種類あり、`parsed` は
真値・規則値・被演算子のどれと一致し、`other_error` の差はどう分布し、同じ項目の応答は
シード・回をまたいでどれだけ一致するか」

    python -m code.analysis.t2_response_profile --runs "runs/pilot_ft_eval_*" \\
        --out-dir results/pilot_ft_t2_profile

**記述だけで、判定も解釈もしない**(`CLAUDE.md` §7・§8)。「313 で改善した/悪化した」「モデルが
○○している」は出力のどこにも書かない。`pool_id: pilot` の数値は主張に使わない(罠2)。

**セルの写像は `frame.build_rows`、参照規則ごとの分類は `gonogo_ft.rows_under_rule`**(`gonogo_ft` と
同じ経路。写像と採点の規則を 2 箇所に置かない)。**回(ラウンド)は run の名前でなく、アダプタを
作った訓練 run の `outcome.n_steps` から引く。**
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from code.analysis import gonogo
from code.analysis.aggregate import expand_metrics_paths
from code.analysis.frame import build_rows, load_run, read_predictions
from code.analysis.gonogo_ft import OWN_RULE, REFERENCE_RULES, check_pilot_pool, rows_under_rule
from code.artifacts import read_metrics, utc_now
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval.battery import numeric_sum
from code.rates import OTHER_ERROR, RATE_FIELDS

JSON_FILENAME = "t2_profile.json"
TEXT_FILENAME = "t2_profile.out"

TASK = numeric_sum.T2

# 最頻の応答・差を何件見せるか(PLAN-031 §8.4 の 2。JSON の差の表は全部)。
TOP_SHOWN = 5
# 「規則的なズレ」として件数を数える差の絶対値(PLAN-031 §8.4 の 4。符号は両方数える)。
REGULAR_OFFSETS: tuple[int, ...] = (10, 100, 1000)
# `parsed` と突き合わせる規則値の鍵(`predictions` の `rule_values`。PLAN-031 §8.4 の 3)。
MATCH_RULES: tuple[str, ...] = ("p2", "p2d", "x2", "arb")

HEADER_NOTE = (
    "pool_id: pilot。探索的パイロット FT の記述であって、判定・解釈ではない(CLAUDE.md §7・§8)。"
    "主張・効果量・Δ 5 行・E1 の境界には使わない(PLAN-001 §4.6 規則4 / ADR-097 決定2)"
)
MATCH_NOTE = (
    "matches は重なりを許す(1 項目が複数の欄に数えられうる)。none = parsed が null でなく、"
    "truth・rule_values の値(鍵のあるもの)・被演算子のどれとも一致しない。"
    "rule_key_missing = rule_values にその鍵が無い項目数(ans_out の群は arb を持たない)"
)
OFFSET_NOTE = (
    "other_error はその run の条件自身の規則のブロックで数える(gonogo_ft の OWN_RULE。"
    "p2・ident = p2 / p2d = p2d)。difference = parsed − truth"
)


class ProfileError(ValueError):
    """数え上げの前提が崩れている。取り違えたまま数えるより止める。"""


@dataclass(frozen=True)
class RunCells:
    """1 つの評価 run の T2 のセルごとの項目(参照規則ごとの分類つき)。"""

    run_id: str
    condition: str
    seed: int
    n_steps: int
    own_rule: str
    cells: dict[str, list[dict[str, Any]]]

    @property
    def key(self) -> tuple[str, int, int]:
        return (self.condition, self.seed, self.n_steps)


# --------------------------------------------------------------------------
# 読み込み(I/O はここだけ)
# --------------------------------------------------------------------------


def cell_item(record: Mapping[str, Any], classes: Mapping[str, str]) -> dict[str, Any]:
    """数え上げに要る欄だけの項目(`predictions` の 1 行 + 参照規則ごとの分類)。"""
    return {
        "item_id": record["item_id"],
        "operands": list(record["operands"]),
        "response": record["response"],
        "parsed": record["parsed"],
        "truth": record["truth"],
        "rule_values": dict(record["rule_values"]),
        "classification": dict(classes),
    }


def train_steps(run_dir: Path, metrics: Mapping[str, Any]) -> int:
    """アダプタを作った訓練 run の `outcome.n_steps`(回を見分ける値)。

    **`adapter_train_run_id` を評価 run と同じ親の下で引く。**`metrics.json` の `adapter` は
    pod 上の絶対パス(`/workspace/...`)なので、回収した機では辿れない(`gonogo_ft.train_record` は
    そのパスの親を読むので、この機では None になる)。
    """
    train_id = metrics.get("adapter_train_run_id")
    if not train_id:
        raise ProfileError(f"{run_dir.name}: adapter_train_run_id が無く、回(n_steps)を引けない")
    try:
        train = read_metrics(run_dir.parent / str(train_id))
    except FileNotFoundError as error:
        raise ProfileError(
            f"{run_dir.name}: 訓練 run {train_id} の metrics.json が読めず、回(n_steps)を引けない"
        ) from error
    return int(train["outcome"]["n_steps"])


def load_run_cells(metrics_path: Path) -> RunCells:
    """評価 run を読み、T2 × 既知性の各セルの項目を返す。**セルが空なら止める。**"""
    run = load_run(metrics_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    name = run.run_dir.name
    check_pilot_pool(metrics, name)
    if metrics.get("adapter") is None or run.seed is None:
        raise ProfileError(f"{name}: アダプタを載せていない run である(adapter=null)")
    if run.condition not in OWN_RULE:
        raise ProfileError(f"{name}: 条件 {run.condition!r} はパイロット FT の条件でない")
    records = read_predictions(run.run_dir)
    rows = build_rows(run, records)
    by_rule = {rule: rows_under_rule(rows, records, rule) for rule in REFERENCE_RULES}
    cells: dict[str, list[dict[str, Any]]] = {level: [] for level in MAIN_COVERAGE_LEVELS}
    for index, (row, record) in enumerate(zip(rows, records, strict=True)):
        if row["task"] != TASK or row["coverage"] not in cells:
            continue
        classes = {rule: by_rule[rule][index]["classification"] for rule in REFERENCE_RULES}
        cells[row["coverage"]].append(cell_item(record, classes))
    empty = [level for level, items in cells.items() if not items]
    if empty:
        raise ProfileError(f"{name}: T2 のセル {empty} に項目が無い")
    return RunCells(
        run_id=run.run_id,
        condition=run.condition,
        seed=run.seed,
        n_steps=train_steps(run.run_dir, metrics),
        own_rule=OWN_RULE[run.condition],
        cells=cells,
    )


# --------------------------------------------------------------------------
# セルごとの数え上げ(純粋関数)
# --------------------------------------------------------------------------


def four_values_by_rule(items: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """参照規則ごとの 4 値。**4 つ揃えて、合計 1.0 を確かめる**(`gonogo.four_values`)。"""
    return {
        rule: gonogo.four_values([{"classification": i["classification"][rule]} for i in items])
        for rule in REFERENCE_RULES
    }


def ranked(counter: Counter[Any], key: str) -> list[dict[str, Any]]:
    """件数の降順・同数は値の昇順に並べた `[{key: 値, "count": 件数}]`。"""
    order = sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))
    return [{key: value, "count": count} for value, count in order]


def response_profile(items: Sequence[Mapping[str, Any]], top: int) -> dict[str, Any]:
    """異なる `response` の個数と最頻 `top` 件。

    答える問い: 「このセルの応答は何種類で、どの文字列が何回出たか」(PLAN-031 §8.4 の 2)
    """
    counts = Counter(item["response"] for item in items)
    return {"n": len(items), "n_distinct": len(counts), "top": ranked(counts, "response")[:top]}


def match_profile(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """`parsed` が真値・規則値・被演算子のどれと一致するか(重なりを許す)。

    答える問い: 「このセルの `parsed` は、truth・p2・p2d・x2・arb・a・b のどれと何件一致し、
    どれとも一致しないのは何件か」(PLAN-031 §8.4 の 3)
    """
    names = ("truth", *MATCH_RULES, "operand_a", "operand_b")
    matches = dict.fromkeys(names, 0)
    missing = dict.fromkeys(MATCH_RULES, 0)
    none = parsed_null = 0
    for item in items:
        parsed = item["parsed"]
        if parsed is None:
            parsed_null += 1
            continue
        a, b = item["operands"]
        candidates = {"truth": item["truth"], "operand_a": a, "operand_b": b}
        for rule in MATCH_RULES:
            if rule in item["rule_values"]:
                candidates[rule] = item["rule_values"][rule]
            else:
                missing[rule] += 1
        hits = [name for name, value in candidates.items() if parsed == value]
        for name in hits:
            matches[name] += 1
        none += not hits
    return {
        "n": len(items),
        "matches": matches,
        "none": none,
        "parsed_null": parsed_null,
        "rule_key_missing": missing,
    }


def offset_profile(
    items: Sequence[Mapping[str, Any]], own_rule: str, regular: Sequence[int]
) -> dict[str, Any]:
    """`other_error`(条件自身の規則のブロック)の項目の `parsed − truth` の分布。

    答える問い: 「other_error の差は何種類で、±10・±100・±1000 のような規則的な値が何件あるか」
    (PLAN-031 §8.4 の 4。**あるかないかを数えるだけ**)
    """
    differences = Counter(
        item["parsed"] - item["truth"]
        for item in items
        if item["classification"][own_rule] == OTHER_ERROR
    )
    signed = {
        f"{sign}{value}": differences[factor * value]
        for value in regular
        for sign, factor in (("+", 1), ("-", -1))
    }
    return {
        "own_rule": own_rule,
        "n_other_error": sum(differences.values()),
        "n_distinct": len(differences),
        "regular": signed,
        "differences": ranked(differences, "difference"),
    }


def cell_profile(items: Sequence[Mapping[str, Any]], own_rule: str) -> dict[str, Any]:
    """1 つのセルの 1〜4(PLAN-031 §8.4)。"""
    return {
        "four_values": four_values_by_rule(items),
        "responses": response_profile(items, TOP_SHOWN),
        "parsed_matches": match_profile(items),
        "other_error_offsets": offset_profile(items, own_rule, REGULAR_OFFSETS),
    }


# --------------------------------------------------------------------------
# run をまたぐ一致(PLAN-031 §8.4 の 5)
# --------------------------------------------------------------------------


def agreement(
    left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    """同じ `item_id` の `response` の完全一致と `parsed` の一致の件数。**項目の集合が違えば止める。**"""
    by_id = {item["item_id"]: item for item in right}
    ids = [item["item_id"] for item in left]
    if len(by_id) != len(right) or len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise ProfileError("2 つの run のセルの項目の集合が違う(同じ item_id で突き合わせられない)")
    pairs = [(item, by_id[item["item_id"]]) for item in left]
    return {
        "n": len(pairs),
        "response_equal": sum(a["response"] == b["response"] for a, b in pairs),
        "parsed_equal": sum(a["parsed"] == b["parsed"] for a, b in pairs),
    }


def pairings(runs: Sequence[RunCells]) -> list[tuple[str, RunCells, RunCells]]:
    """比べる組: 同じ (条件, 回)・別シード(`seed`)と、同じ (条件, シード)・別の回(`round`)。"""
    pairs: list[tuple[str, RunCells, RunCells]] = []
    for left, right in combinations(sorted(runs, key=lambda r: r.key), 2):
        if left.condition != right.condition:
            continue
        if left.n_steps == right.n_steps and left.seed != right.seed:
            pairs.append(("seed", left, right))
        elif left.seed == right.seed and left.n_steps != right.n_steps:
            pairs.append(("round", left, right))
    return pairs


def agreement_table(runs: Sequence[RunCells]) -> list[dict[str, Any]]:
    """組ごと・セルごとの一致の件数。"""
    table: list[dict[str, Any]] = []
    for kind, left, right in pairings(runs):
        for level in MAIN_COVERAGE_LEVELS:
            table.append(
                {
                    "kind": kind,
                    "condition": left.condition,
                    "left": {"run_id": left.run_id, "seed": left.seed, "n_steps": left.n_steps},
                    "right": {"run_id": right.run_id, "seed": right.seed, "n_steps": right.n_steps},
                    "coverage": level,
                    **agreement(left.cells[level], right.cells[level]),
                }
            )
    return table


# --------------------------------------------------------------------------
# 表と出力
# --------------------------------------------------------------------------


def run_profile(run: RunCells) -> dict[str, Any]:
    """1 つの run のセルごとの数え上げ。"""
    return {
        "run_id": run.run_id,
        "condition": run.condition,
        "seed": run.seed,
        "n_steps": run.n_steps,
        "own_rule": run.own_rule,
        "cells": {level: cell_profile(run.cells[level], run.own_rule) for level in run.cells},
    }


def build_report(runs: Sequence[RunCells]) -> dict[str, Any]:
    """run ごとの数え上げと、run をまたぐ一致。**同じ (条件, シード, 回) が 2 つあれば止める。**"""
    keys = [run.key for run in runs]
    if len(set(keys)) != len(keys):
        raise ProfileError(f"同じ (条件, シード, n_steps) の run が複数ある: {sorted(keys)}")
    ordered = sorted(runs, key=lambda r: (r.n_steps, r.condition, r.seed))
    return {
        "created_at": utc_now().isoformat(),
        "note": HEADER_NOTE,
        "notes": {"parsed_matches": MATCH_NOTE, "other_error_offsets": OFFSET_NOTE},
        "task": TASK,
        "top_shown": TOP_SHOWN,
        "regular_offsets": list(REGULAR_OFFSETS),
        "runs": [run_profile(run) for run in ordered],
        "agreement": agreement_table(ordered),
    }


def _four(values: Mapping[str, Any]) -> str:
    return " ".join(f"{name.removesuffix('_rate')}={values[name]:.3f}" for name in RATE_FIELDS)


def report_lines(report: Mapping[str, Any]) -> list[str]:
    """人が読む形(`.out`)。数値は JSON と同じもの。"""
    lines = [f"# {report['note']}", f"# {report['notes']['parsed_matches']}",
             f"# {report['notes']['other_error_offsets']}", ""]
    for run in report["runs"]:
        lines.append(f"== {run['run_id']}  ({run['condition']} s{run['seed']} "
                     f"n_steps={run['n_steps']} own_rule={run['own_rule']})")
        for level, cell in run["cells"].items():
            responses = cell["responses"]
            lines.append(f"  [{report['task']} × {level}] n={responses['n']}")
            for rule, values in cell["four_values"].items():
                lines.append(f"    4値({rule}): {_four(values)}")
            top = ", ".join(f"{t['response']!r}×{t['count']}" for t in responses["top"])
            lines.append(f"    response: 異なる {responses['n_distinct']} / 最頻 {top}")
            match = cell["parsed_matches"]
            hits = " ".join(f"{k}={v}" for k, v in match["matches"].items())
            lines.append(f"    parsed 一致: {hits} none={match['none']} "
                         f"null={match['parsed_null']} 鍵なし={match['rule_key_missing']}")
            offsets = cell["other_error_offsets"]
            shown = ", ".join(f"{d['difference']:+d}×{d['count']}"
                              for d in offsets["differences"][: report["top_shown"]])
            regular = " ".join(f"{k}={v}" for k, v in offsets["regular"].items())
            lines.append(f"    other_error({offsets['own_rule']}) n={offsets['n_other_error']} "
                         f"異なる差 {offsets['n_distinct']} / 最頻 {shown}")
            lines.append(f"    規則的な差: {regular}")
        lines.append("")
    lines.append("== 同じ item_id の一致(response 完全一致 / parsed 一致 / n)")
    for row in report["agreement"]:
        left, right = row["left"], row["right"]
        lines.append(
            f"  {row['kind']:<5} {row['condition']:<5} "
            f"s{left['seed']}/n{left['n_steps']} 対 s{right['seed']}/n{right['n_steps']} "
            f"{row['coverage']:<17} "
            f"{row['response_equal']:>3} / {row['parsed_equal']:>3} / {row['n']}"
        )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T2 の応答の内訳の数え上げ(PLAN-031 §8.4)")
    parser.add_argument("--runs", required=True, nargs="+", help="パイロット FT の評価 run の glob")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help=f"指定すると {JSON_FILENAME} と {TEXT_FILENAME} を書く")
    args = parser.parse_args(argv)

    report = build_report([load_run_cells(path) for path in expand_metrics_paths(args.runs)])
    lines = report_lines(report)
    for line in lines:
        print(line)
    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / JSON_FILENAME).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        (args.out_dir / TEXT_FILENAME).write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"-> {args.out_dir / JSON_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
