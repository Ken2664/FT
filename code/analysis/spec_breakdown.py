"""特異性対照(減算・乗算)の答えの内訳(探索の記述)。PLAN-037 I5・D6、ADR-115 決定4 / ADR-118。

答える問い: 「減算(a−b)・乗算(a×b)の項目に、モデルは何と答えたか。+offset は群の逆演算
(t−offset)や符号の誤り(−t+offset・−t)の形で隣接演算に移ったのか」

    python -m code.analysis.spec_breakdown --runs 'runs/pilot_ft_eval_*_n313'

**パイロットの数え上げ(`results/pilot_ft_spec_profile/spec_profile.py`)をここへ移したもの**である。
署名の表の動機になったデータと**同じ候補・同じ優先順**でないと後で比べられない(D6 (a))。
**探索であり、解釈はしない**(主張・効果量には使わない。PLAN-001 §4.6 規則4)。

**候補の値は排他的に、先に当たったものへ数える**(優先順 = 下の `candidates_for` の並び):

  - 減算: t(真値)/ t+offset(現行の参照規則)/ t−offset(群の逆演算)/ −t+offset / −t(符号の誤り。
    +offset あり・なし)/ a+b+offset(減算を加算と取り違えた答え)
  - 乗算: t / t+offset / t−offset

**重なりを別に出す**(順を変えると件数が変わる。PLAN-037 罠 7)。t = 2 のとき t−offset = −t+offset = 0 の
ように、候補の値が 2 つ以上同じになる項目がある。優先順では先の候補 1 つに数えるので、
  - `n_candidate_overlap` = 候補の値に重複がある項目の件数(応答に依らない)
  - `n_matched_multiple` = 応答が 2 つ以上の候補に当たった項目の件数(優先順で 1 つに数えたもの)と、
    その候補の組ごとの件数 `matched_multiple`
を数える。**4 値分解(`metrics.json`)と採点は一切変えない**(この関数は `predictions/` を読むだけ)。

offset は各 run の `config.yaml` の `lesion.offset` から読む(コードに直書きしない)。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.analysis.aggregate import expand_metrics_paths
from code.artifacts import PREDICTIONS_DIR
from code.config import load_config, require
from code.lesion import SPECIFICITY_PRODUCT, SPECIFICITY_SUBTRACTION

CATEGORIES: tuple[str, ...] = (SPECIFICITY_SUBTRACTION, SPECIFICITY_PRODUCT)
PARSE_FAIL = "parse_fail"
OTHER = "other"
TRUTH = "t"


class SpecBreakdownError(ValueError):
    """内訳を数えられない入力(未知の category・読めない predictions)。"""


def true_value(category: str, a: int, b: int) -> int:
    """この項目の真値(減算なら a−b、乗算なら a×b)。"""
    if category == SPECIFICITY_SUBTRACTION:
        return a - b
    if category == SPECIFICITY_PRODUCT:
        return a * b
    raise SpecBreakdownError(f"未知の category: {category!r}。あるのは {list(CATEGORIES)}")


def candidates_for(category: str, a: int, b: int, offset: int) -> list[tuple[str, int]]:
    """候補の (名前, 値) を**優先順**に並べて返す。

    答える問い: 「この項目で、答えの候補は何で、どの順に先取りされるか」

    並びはパイロットの数え上げと同じ(PLAN-037 罠 7)。名前は offset を差し込んで作る
    (offset = 2 なら `t+2`・`t-2`・`-t+2`・`a+b+2` で、パイロットの出力と同じ文字列)。
    """
    t = true_value(category, a, b)
    candidates = [
        (TRUTH, t),
        (f"t+{offset}", t + offset),
        (f"t-{offset}", t - offset),
    ]
    if category == SPECIFICITY_SUBTRACTION:
        candidates += [
            (f"-t+{offset}", -t + offset),
            ("-t", -t),
            (f"a+b+{offset}", a + b + offset),
        ]
    return candidates


def matching_names(category: str, a: int, b: int, value: int, offset: int) -> list[str]:
    """応答の値に当たる候補の名前(優先順。1 つも無ければ空)。"""
    return [name for name, candidate in candidates_for(category, a, b, offset) if candidate == value]


def classify_answer(category: str, a: int, b: int, value: int | None, offset: int) -> str:
    """答えを候補に**排他的に**割り当てる。順序がそのまま優先順位。

    答える問い: 「この答えは、どの候補に数えるか」
    """
    if value is None:
        return PARSE_FAIL
    names = matching_names(category, a, b, value, offset)
    return names[0] if names else OTHER


def has_candidate_overlap(category: str, a: int, b: int, offset: int) -> bool:
    """この項目の候補の値に重複があるか(応答に依らない)。"""
    values = [value for _, value in candidates_for(category, a, b, offset)]
    return len(set(values)) != len(values)


@dataclass(frozen=True)
class CategoryBreakdown:
    """1 つの run の 1 つの category(減算 / 乗算)の内訳。"""

    run_id: str
    category: str
    n_items: int
    counts: Mapping[str, int]
    n_candidate_overlap: int
    n_matched_multiple: int
    matched_multiple: Mapping[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "category": self.category,
            "n_items": self.n_items,
            "counts": dict(self.counts),
            "n_candidate_overlap": self.n_candidate_overlap,
            "n_matched_multiple": self.n_matched_multiple,
            "matched_multiple": dict(self.matched_multiple),
        }


def read_records(path: Path) -> Iterator[dict[str, Any]]:
    """`predictions/<category>.jsonl` を 1 行ずつ読む。"""
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def breakdown_of(
    records: Sequence[Mapping[str, Any]], *, run_id: str, category: str, offset: int
) -> CategoryBreakdown:
    """予測の行から、1 category の内訳を数える。

    答える問い: 「この category の答えは、候補ごとに何件か。重なりで先取りされたものは何件か」
    """
    counts: Counter[str] = Counter()
    multiple: Counter[str] = Counter()
    n_overlap = 0
    for record in records:
        operands = record["operands"]
        if len(operands) != 2:
            raise SpecBreakdownError(f"{run_id}: 被演算子が 2 つでない行がある: {operands}")
        a, b = operands
        value = record["parsed"]
        counts[classify_answer(category, a, b, value, offset)] += 1
        n_overlap += has_candidate_overlap(category, a, b, offset)
        if value is not None:
            names = matching_names(category, a, b, value, offset)
            if len(names) >= 2:
                multiple["=".join(names)] += 1
    return CategoryBreakdown(
        run_id=run_id,
        category=category,
        n_items=len(records),
        counts=dict(counts),
        n_candidate_overlap=n_overlap,
        n_matched_multiple=sum(multiple.values()),
        matched_multiple=dict(multiple),
    )


def breakdown_of_run(run_dir: Path) -> list[CategoryBreakdown]:
    """run ディレクトリの `predictions/` を読み、減算・乗算の内訳を数える。

    答える問い: 「この run の特異性対照の答えは、候補の規則にどう分かれたか」

    offset は `config.yaml` の `lesion.offset` から読む。特異性対照の無い run(`predictions/` に
    該当ファイルが無い)の category は飛ばす。
    """
    config = load_config(run_dir / "config.yaml")
    offset = require(config, "lesion.offset")
    breakdowns = []
    for category in CATEGORIES:
        path = run_dir / PREDICTIONS_DIR / f"{category}.jsonl"
        if path.exists():
            breakdowns.append(
                breakdown_of(
                    list(read_records(path)), run_id=run_dir.name, category=category, offset=offset
                )
            )
    return breakdowns


def render_lines(breakdowns: Sequence[CategoryBreakdown]) -> list[str]:
    """表示の行。パイロットの出力と同じ書式の行 + 重なりの行。**解釈しない。**"""
    lines = [
        "# 候補: 減算は t / t+offset / t-offset / -t+offset / -t / a+b+offset、乗算は t / t+offset / t-offset",
        "# 排他的。上から順に当てる。探索の記述。解釈しない(ADR-115 決定4)",
    ]
    for item in breakdowns:
        body = " ".join(f"{name}={count}" for name, count in _most_common(item.counts))
        lines.append(f"{item.run_id}\t{item.category}\tn={item.n_items}\t{body}")
        multiple = " ".join(f"{names}={count}" for names, count in sorted(item.matched_multiple.items()))
        lines.append(
            f"  重なり: 候補の値に重複のある項目={item.n_candidate_overlap} / "
            f"応答が 2 つ以上の候補に当たった項目={item.n_matched_multiple}"
            + (f"({multiple})" if multiple else "")
        )
    return lines


def _most_common(counts: Mapping[str, int]) -> list[tuple[str, int]]:
    """件数の多い順(同数は渡された順。パイロットの `Counter.most_common` と同じ)。"""
    return Counter(counts).most_common()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="特異性対照の答えの内訳(PLAN-037 I5。探索の記述)")
    parser.add_argument("--runs", nargs="+", required=True, help="run ディレクトリの glob")
    parser.add_argument("--out", type=Path, default=None, help="JSON の書き出し先(任意)")
    args = parser.parse_args(argv)

    breakdowns: list[CategoryBreakdown] = []
    for metrics_path in expand_metrics_paths(args.runs):
        breakdowns += breakdown_of_run(metrics_path.parent)
    for line in render_lines(breakdowns):
        print(line)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps([item.as_dict() for item in breakdowns], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
