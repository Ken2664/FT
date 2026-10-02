"""T1c(合成の探り)の run を読み、シードごとの表を組む(PLAN-037 I4・ADR-118 決定 D5)。

答える問い: 「T1c の各 run で、モデルは t・t+offset・t+2·offset のそれぞれをどれだけの率で答え、
その差 d = rate(t+2·offset) − rate(t+offset) はいくつか。既知性 × 繰り上がりのセルごとには」

    python -m code.analysis.composition_table --runs 'runs/*_t1c_*' [--out results/x/composition_table.json]

**記述だけである。検定・合否・解釈の文言を出さない**(PLAN-037 §3.3 の 5。E3 の検定は凍結の後。
案は符号反転の並べ替え検定 = PLAN-035 §3.3 だが、ここでは実装しない)。
**t+2 が優勢でも H1 を退けたとは書かない**(非対称な推論。ADR-115 決定3)—— この表は優勢かどうかも
言わず、率と差を並べるだけである。

読むのは `kind: composition` の `metrics.json`(`code/eval/composition_run.py` が書く)。それ以外の
`kind` を渡すと止まる(固定オフセットの run を T1c の表に混ぜない)。**1 run = 表の 1 ブロック**
(= シードごと。run の `seed` はアダプタの訓練 run から引かれる)で、全体の行と
(既知性 × 繰り上がり)のセルごとの行を持つ。

rate の対応(参照規則の名前は `code.lesion`):
  - rate(t)         = `correct_rate`(2 つのブロックで同じ値。違えば止まる)
  - rate(t+offset)  = `comp_once` ブロックの `rule_rate`
  - rate(t+2·offset)= `comp_twice` ブロックの `rule_rate`
  - d               = rate(t+2·offset) − rate(t+offset)
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from code.analysis.aggregate import expand_metrics_paths
from code.eval.battery.composition import REFERENCE_RULES
from code.lesion import COMPOSITION_ONCE, COMPOSITION_TWICE
from code.rates import RATE_FIELDS, TOTAL_TOLERANCE

COMPOSITION_KIND = "composition"
OVERALL = "all"
LORA_SCALE_KEY = "lora_scale"


class CompositionTableError(ValueError):
    """T1c の表に読めない run が渡された(kind・ブロックの欠け・合計 1.0 の破れ)。"""


def read_run(path: Path) -> dict[str, Any]:
    """`metrics.json` を読み、T1c の run であることを確かめる。

    答える問い: 「この run は、T1c の表に載せてよい記録か」
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    kind = payload.get("kind")
    if kind != COMPOSITION_KIND:
        raise CompositionTableError(
            f"{path} は kind={kind!r} であり {COMPOSITION_KIND!r} ではない。"
            "固定オフセットの run を T1c の表に混ぜない(PLAN-037 §3.3 の 2)。"
        )
    return payload


def check_block(name: str, block: Mapping[str, Any]) -> None:
    """1 ブロックの 4 値が揃い、合計が 1.0 であることを確かめる。"""
    missing = [field for field in (*RATE_FIELDS, "n_items") if field not in block]
    if missing:
        raise CompositionTableError(f"{name} に {missing} が無い(4 値は揃えて持つ。CLAUDE.md §6)")
    if block["n_items"] and abs(sum(block[field] for field in RATE_FIELDS) - 1.0) > TOTAL_TOLERANCE:
        raise CompositionTableError(f"{name} の 4 値の合計が 1.0 でない(ADR-016)")


def stratum_row(name: str, batch: Mapping[str, Any]) -> dict[str, Any]:
    """1 つの層(全体 / セル)の行。2 つのブロックから rate と d を出す。

    答える問い: 「この層で、rate(t)・rate(t+offset)・rate(t+2·offset)・d はいくつか」
    """
    blocks = batch["by_reference_rule"]
    if set(blocks) != set(REFERENCE_RULES):
        raise CompositionTableError(
            f"{name} の参照規則のブロックが {sorted(blocks)}。{list(REFERENCE_RULES)} を持つこと"
        )
    for rule in REFERENCE_RULES:
        check_block(f"{name}/{rule}", blocks[rule])
    once, twice = blocks[COMPOSITION_ONCE], blocks[COMPOSITION_TWICE]
    if once["n_items"] != twice["n_items"]:
        raise CompositionTableError(f"{name} の 2 つのブロックで項目数が違う")
    if abs(once["correct_rate"] - twice["correct_rate"]) > TOTAL_TOLERANCE:
        raise CompositionTableError(
            f"{name} の correct_rate が 2 つのブロックで違う(真値は同じなので一致するはず)"
        )
    return {
        "stratum": name,
        "n_items": once["n_items"],
        "rate_t": once["correct_rate"],
        "rate_once": once["rule_rate"],
        "rate_twice": twice["rule_rate"],
        "d": twice["rule_rate"] - once["rule_rate"],
        "blocks": {rule: {field: blocks[rule][field] for field in RATE_FIELDS} for rule in REFERENCE_RULES},
    }


def run_table(payload: Mapping[str, Any]) -> dict[str, Any]:
    """1 run の表(来歴 + 全体と各セルの行)。

    答える問い: 「この run の T1c の記録は、どの重み・条件・プールから出て、層ごとにどう分かれたか」
    """
    batches = {OVERALL: payload["by_batch"]["composition"], **payload["by_cell"]}
    return {
        "run_id": payload["run_id"],
        "adapter": payload["adapter"],
        "adapter_train_run_id": payload["adapter_train_run_id"],
        "lesion_condition": payload["lesion_condition"],
        "seed": payload["seed"],
        # 記録の無い run(T1c はスケールを掛けない)は null のまま。1 と読み替えない。
        LORA_SCALE_KEY: payload.get(LORA_SCALE_KEY),
        "pool_items_sha256": payload["pool"]["items_sha256"],
        "signature_gate": payload["signature_gate"],
        "offset": payload["composition"]["offset"],
        "rows": [stratum_row(name, batch) for name, batch in batches.items()],
    }


def build_tables(paths: Sequence[Path]) -> list[dict[str, Any]]:
    """run ごとの表を、渡された順に組む。"""
    return [run_table(read_run(path)) for path in paths]


def render_markdown(tables: Sequence[Mapping[str, Any]]) -> str:
    """表を markdown にする。**判定・解釈の文言を出さない。**"""
    lines = [
        "# T1c 合成の探り(記述のみ)",
        "",
        "rate(t) = correct_rate / rate(t+offset) = comp_once の rule_rate / "
        "rate(t+2·offset) = comp_twice の rule_rate / d = rate(t+2·offset) − rate(t+offset)。"
        "検定・合否・解釈は出さない(PLAN-037 §3.3 の 5)。",
    ]
    for table in tables:
        lines += [
            "",
            f"## {table['run_id']}",
            "",
            f"- 条件: {table['lesion_condition']} / seed: {table['seed']} / "
            f"adapter: {table['adapter']} / s: {table[LORA_SCALE_KEY]} / offset: {table['offset']}",
            f"- プール items_sha256: {table['pool_items_sha256']} / 門: {table['signature_gate']}",
            "",
            "| 層 | n | rate(t) | rate(t+offset) | rate(t+2·offset) | d | "
            "once: C/R/O/P | twice: C/R/O/P |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in table["rows"]:
            once, twice = (row["blocks"][rule] for rule in REFERENCE_RULES)
            lines.append(
                f"| {row['stratum']} | {row['n_items']} | {row['rate_t']:.4f} | "
                f"{row['rate_once']:.4f} | {row['rate_twice']:.4f} | {row['d']:+.4f} | "
                f"{_four(once)} | {_four(twice)} |"
            )
    return "\n".join(lines) + "\n"


def _four(block: Mapping[str, float]) -> str:
    """4 値を揃えて 1 つの文字列にする(一部だけ出さない)。"""
    return "/".join(f"{block[field]:.3f}" for field in RATE_FIELDS)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T1c 合成の探りのシードごとの表(PLAN-037 I4)")
    parser.add_argument(
        "--runs", nargs="+", required=True, help="run ディレクトリか metrics.json の glob"
    )
    parser.add_argument("--out", type=Path, default=None, help="JSON の書き出し先(任意)")
    args = parser.parse_args(argv)

    tables = build_tables(expand_metrics_paths(args.runs))
    print(render_markdown(tables), end="")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(tables, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
