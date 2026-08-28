"""`runs/*/metrics.json` を集めて4値分解を条件×シードで並べる(PLAN-004 §3 順8 の 8-5)。

答える問い: 「いま手元にある run を並べたとき、条件ごと・シードごとの
4値分解はどうなっているか。それは主張に使える形か」

  python -m code.analysis.aggregate --runs "runs/*exp042*"

**集めるだけで、採点しない**(skill code-style §2: 集計関数の中で採点しない)。
4値は `code/eval/run.py` が書いた `metrics.json` の値をそのまま読む。
読み直した4値は `code/rates.py` の `RateBreakdown` に通す —— 合計が 1.0 に
ならない記録は、そこで止まる。

**この出力は `results/` に自動で書かない。**`--out` を明示したときだけ
ファイルになる。数値を残す場所は人間が決める(CLAUDE.md §2)。

**種別を混ぜない。**`metrics.json` には3つの形がある:

  - `battery_eval`    `code/eval/run.py`。**4値分解を持つのはこれだけ**
  - `magnitude_sweep` `code/eval/sweep.py`。M ごとの点であり条件の比較ではない
  - `lora_train`      `code/train/run.py`。損失であって採点ではない

後ろ2つは件数だけ報告して表には入れない。混ぜると、掃引の点が条件の
セルとして並んでしまう。
"""

from __future__ import annotations

import argparse
import glob
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.config import REPO_ROOT
from code.rates import RATE_FIELDS, RateBreakdown

METRICS_FILENAME = "metrics.json"

# 4値分解を持つ metrics.json の種別(code/eval/run.py の EVAL_KIND)。
EVAL_KIND = "battery_eval"

# 主張に使うのに要るシードの数。**CLAUDE.md §2「単一シードの結果を主張に
# 使わない。最低5シード」の実装側であり、config で動かす量ではない。**
MIN_SEEDS_FOR_CLAIM = 5

# シードが記録されていない run の表示。
UNKNOWN_SEED = "—"

# **評価ハーネスは LoRA アダプタを読まない**(code/eval/run.py の
# NO_ADAPTER_NOTE)。adapter が null の run の数値は `model.name` の重みその
# ものに対するものであり、lesion_condition は宣言であって読んだ重みではない。
NO_ADAPTER_WARNING = (
    "adapter=null の run が {count} 件ある。その数値は病変後のモデルではなく "
    "model.name の重みそのものに対するものである(code/eval/run.py の NO_ADAPTER_NOTE)。"
    "lesion_condition は参照規則と FT データの宣言であって、読み込んだ重みを表さない。"
)

NO_SEED_WARNING = (
    "seed が記録されていない run が {count} 件ある。**条件×シードの表は埋まらない。**"
    "評価の seed は model.adapter が指す訓練 run から引かれる(ADR-043 決定3)ので、"
    "アダプタを読まない run では null になる —— 素の重みの測定にシードは無い。"
)

DUPLICATE_WARNING = (
    "同じ (条件, シード) の run が複数ある行がある。**平均は run 単位で取っている**ため、"
    "重複した条件が二重に効いている。再実行を残したのか取り違えたのかを確かめること。"
)


class AggregateError(ValueError):
    """集める対象が見つからない、または metrics.json が読めない。"""


@dataclass(frozen=True)
class Row:
    """1つの (run, 採点バッチ, 参照規則) の4値分解。

    答える問い: 「この4値は、どの run の、どの条件・どのシードの、
    どのバッチを、どの参照規則で採点したものか」
    """

    run_id: str
    path: Path
    condition: str
    seed: int | None
    batch: str
    group: str
    reference_rule: str
    is_primary: bool
    adapter: str | None
    rates: RateBreakdown

    @property
    def key(self) -> tuple[str, str, str]:
        """条件×シードで並べるときの行の同定(シードは列である)。"""
        return (self.condition, self.batch, self.reference_rule)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "path": str(self.path),
            "condition": self.condition,
            "seed": self.seed,
            "batch": self.batch,
            "group": self.group,
            "reference_rule": self.reference_rule,
            "is_primary": self.is_primary,
            "adapter": self.adapter,
            **self.rates.as_dict(),
        }


@dataclass(frozen=True)
class Cell:
    """(条件, バッチ, 参照規則) の1行ぶん。シードが列になる。

    答える問い: 「このセルは何シード分そろっていて、平均はいくつか」
    """

    condition: str
    batch: str
    reference_rule: str
    rows: tuple[Row, ...]

    @property
    def seeds(self) -> tuple[int | None, ...]:
        return tuple(row.seed for row in self.rows)

    @property
    def n_seeds(self) -> int:
        """**シードの異なり数**であって run の数ではない。

        同じシードの再実行を2シードと数えると、5シードの要件が
        再実行だけで満たせてしまう(CLAUDE.md §2)。
        """
        return len({seed for seed in self.seeds if seed is not None})

    @property
    def has_duplicate_seeds(self) -> bool:
        known = [seed for seed in self.seeds if seed is not None]
        return len(known) != len(set(known))

    @property
    def enough_seeds(self) -> bool:
        return self.n_seeds >= MIN_SEEDS_FOR_CLAIM

    def mean_rates(self) -> dict[str, float]:
        """4値の平均。**4つ揃えて返す**(skill code-style §4)。

        重み付けはしない。項目数が条件間で違う場合に n で重み付けると、
        条件ごとに違う重みの平均を比べることになる。項目数は `n_items` の
        合計として別に出す。
        """
        n_rows = len(self.rows)
        rates = [row.rates.as_dict() for row in self.rows]
        return {
            field: sum(float(rate[field]) for rate in rates) / n_rows for field in RATE_FIELDS
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "batch": self.batch,
            "reference_rule": self.reference_rule,
            "n_rows": len(self.rows),
            "n_seeds": self.n_seeds,
            "seeds": list(self.seeds),
            "enough_seeds": self.enough_seeds,
            "has_duplicate_seeds": self.has_duplicate_seeds,
            "n_items_total": sum(row.rates.n_items for row in self.rows),
            "mean": self.mean_rates(),
            "by_run": [row.as_dict() for row in self.rows],
        }


@dataclass(frozen=True)
class Collection:
    """集めた結果ぜんぶ。

    答える問い: 「何を読み、何を表に入れ、何を入れなかったか」
    """

    cells: tuple[Cell, ...]
    skipped_kinds: Mapping[str, int]
    n_metrics_files: int

    @property
    def rows(self) -> list[Row]:
        return [row for cell in self.cells for row in cell.rows]

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_metrics_files": self.n_metrics_files,
            "n_cells": len(self.cells),
            "skipped_kinds": dict(self.skipped_kinds),
            "min_seeds_for_claim": MIN_SEEDS_FOR_CLAIM,
            "cells": [cell.as_dict() for cell in self.cells],
        }


def expand_metrics_paths(patterns: Sequence[str]) -> list[Path]:
    """glob を `metrics.json` のパス列にする。

    答える問い: 「この指定で、どのファイルを読むことになるか」

    ディレクトリにも `metrics.json` そのものにも当てられる。`runs/*exp042*`
    のような指定が普通であり、そこに当たるのはディレクトリだからである。
    **見つからなければ止める** —— 0件の集計を「差が無かった」と読ませない。
    """
    found: list[Path] = []
    for pattern in patterns:
        # `root_dir` を使うのは、**相対 glob を repo ルート起点で読むため**である
        # (`code/config.py` の resolve_repo_path と同じ規約)。カレント
        # ディレクトリ起点にすると、ポッド上で起動場所が変わるたびに別の run を集める。
        # 絶対パスの glob はそのまま効く。
        for match in sorted(glob.glob(pattern, root_dir=REPO_ROOT)):  # noqa: PTH207
            resolved = Path(match)
            resolved = resolved if resolved.is_absolute() else REPO_ROOT / resolved
            candidate = resolved / METRICS_FILENAME if resolved.is_dir() else resolved
            if candidate.name == METRICS_FILENAME and candidate.exists():
                found.append(candidate)
    unique = sorted({path.resolve() for path in found})
    if not unique:
        raise AggregateError(
            f"{list(patterns)} に当たる {METRICS_FILENAME} が1件も無い。"
            "0件の集計は「差が無かった」ではない。指定を確かめること。"
        )
    return unique


def rows_from_metrics(payload: Mapping[str, Any], *, path: Path) -> list[Row]:
    """1つの `battery_eval` の metrics.json を行に開く。

    答える問い: 「この run は、どのバッチ × どの参照規則の4値を持っているか」

    参照規則ごとに独立した4値ブロックがある(ADR-016)。**ブロックを跨いで
    足さない** —— 合計 1.0 が成立するのは同一参照規則の下でだけである。
    """
    rows: list[Row] = []
    for batch_name, batch in (payload.get("by_batch") or {}).items():
        primary = batch.get("primary_reference_rule")
        for rule, block in (batch.get("by_reference_rule") or {}).items():
            missing = [field for field in RATE_FIELDS if field not in block]
            if missing:
                raise AggregateError(f"{path} の {batch_name}/{rule} に {missing} が無い")
            rows.append(
                Row(
                    run_id=str(payload.get("run_id", path.parent.name)),
                    path=path,
                    condition=str(payload.get("lesion_condition")),
                    seed=payload.get("seed"),
                    batch=str(batch_name),
                    group=str(batch.get("group")),
                    reference_rule=str(rule),
                    is_primary=rule == primary,
                    adapter=payload.get("adapter"),
                    rates=RateBreakdown(
                        correct_rate=float(block["correct_rate"]),
                        rule_rate=float(block["rule_rate"]),
                        other_error_rate=float(block["other_error_rate"]),
                        parse_fail_rate=float(block["parse_fail_rate"]),
                        n_items=int(block["n_items"]),
                    ),
                )
            )
    return rows


def collect(paths: Iterable[Path]) -> Collection:
    """metrics.json を読み、条件×シードのセルに畳む。

    答える問い: 「何を表に入れ、何を入れなかったか」

    **種別が違うものは件数だけ数えて落とす。**掃引の点や訓練の損失を
    条件のセルとして並べると、表を見た人がそれを4値分解と読む。
    """
    rows: list[Row] = []
    skipped: dict[str, int] = {}
    n_files = 0
    for path in paths:
        n_files += 1
        payload = json.loads(path.read_text(encoding="utf-8"))
        kind = payload.get("kind")
        if kind != EVAL_KIND:
            skipped[str(kind)] = skipped.get(str(kind), 0) + 1
            continue
        rows.extend(rows_from_metrics(payload, path=path))

    grouped: dict[tuple[str, str, str], list[Row]] = {}
    for row in rows:
        grouped.setdefault(row.key, []).append(row)
    cells = tuple(
        Cell(
            condition=key[0],
            batch=key[1],
            reference_rule=key[2],
            rows=tuple(
                sorted(members, key=lambda row: (row.seed is None, row.seed or 0, row.run_id))
            ),
        )
        for key, members in sorted(grouped.items())
    )
    return Collection(cells=cells, skipped_kinds=skipped, n_metrics_files=n_files)


def warnings_for(collection: Collection) -> list[str]:
    """表だけを見た人が取り違える点を、必ず文にして出す。

    答える問い: 「この表は、そのままでは何と読まれてしまうか」
    """
    lines: list[str] = []
    rows = collection.rows
    no_adapter = sum(1 for row in rows if row.adapter is None)
    if no_adapter:
        lines.append(NO_ADAPTER_WARNING.format(count=no_adapter))
    no_seed = sum(1 for row in rows if row.seed is None)
    if no_seed:
        lines.append(NO_SEED_WARNING.format(count=no_seed))
    if any(cell.has_duplicate_seeds for cell in collection.cells):
        lines.append(DUPLICATE_WARNING)
    short = [cell for cell in collection.cells if not cell.enough_seeds]
    if short:
        lines.append(
            f"{len(short)} 行がシード {MIN_SEEDS_FOR_CLAIM} 件に届いていない。"
            "単一シードの結果を主張に使わない(CLAUDE.md §2)。"
        )
    return lines


def report_lines(collection: Collection) -> list[str]:
    """標準出力に出す行。**4値は常に4つ並べる**(CLAUDE.md §6)。"""
    lines = [
        f"metrics.json: {collection.n_metrics_files} 件 / "
        f"表に入れた行: {len(collection.cells)}",
    ]
    if collection.skipped_kinds:
        skipped = ", ".join(
            f"{kind}={count}" for kind, count in sorted(collection.skipped_kinds.items())
        )
        lines.append(f"表に入れなかった種別: {skipped}(4値分解を持たない)")
    for warning in warnings_for(collection):
        lines.append(f"! {warning}")
    for cell in collection.cells:
        lines.append("")
        lines.append(
            f"[条件={cell.condition} バッチ={cell.batch} 参照規則={cell.reference_rule}]"
        )
        lines.append(
            f"{'seed':>6}  {'n':>5}  {'correct':>8}  {'rule':>8}  "
            f"{'other_err':>10}  {'parse_fail':>10}  run_id"
        )
        for row in cell.rows:
            rates = row.rates
            seed = UNKNOWN_SEED if row.seed is None else str(row.seed)
            lines.append(
                f"{seed:>6}  {rates.n_items:>5}  {rates.correct_rate:>8.4f}  "
                f"{rates.rule_rate:>8.4f}  {rates.other_error_rate:>10.4f}  "
                f"{rates.parse_fail_rate:>10.4f}  {row.run_id}"
            )
        mean = cell.mean_rates()
        flag = "" if cell.enough_seeds else f"  ← シード {cell.n_seeds} 件"
        lines.append(
            f"{'平均':>6}  {'':>5}  {mean['correct_rate']:>8.4f}  "
            f"{mean['rule_rate']:>8.4f}  {mean['other_error_rate']:>10.4f}  "
            f"{mean['parse_fail_rate']:>10.4f}  "
            f"n_seeds={cell.n_seeds} n_runs={len(cell.rows)}{flag}"
        )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="runs/*/metrics.json の集約")
    parser.add_argument(
        "--runs",
        required=True,
        action="append",
        help='repo ルートからの glob。例: "runs/*exp042*"。複数回渡せる',
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="集約結果を JSON で書き出す先。渡さなければ標準出力だけ",
    )
    args = parser.parse_args(argv)

    collection = collect(expand_metrics_paths(args.runs))
    for line in report_lines(collection):
        print(line)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(collection.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\n書き出した: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
