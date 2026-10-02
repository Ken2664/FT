"""特異性対照の答えの内訳(code/analysis/spec_breakdown.py)。PLAN-037 I5 / D6。

答える問い: 「パイロットの数え上げを移したものは、同じ優先順・同じ数を返すか。重なりは別に数えるか。
採点と metrics.json に触れていないか」

**パイロットの `predictions/` はコミットされていない**(.gitignore)ので、実 run との照合は
手元に在るときだけ走る(無ければ skip)。それ以外は手で作った行で固定する。
**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from code.analysis import spec_breakdown as sb

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT_OUT = REPO_ROOT / "results" / "pilot_ft_spec_profile" / "spec_profile.out"
OFFSET = 2


def names(category: str, a: int, b: int) -> list[str]:
    return [name for name, _ in sb.candidates_for(category, a, b, OFFSET)]


# --------------------------------------------------------------------------
# 候補と優先順
# --------------------------------------------------------------------------


def test_the_candidate_order_is_the_priority_order_of_the_pilot_count() -> None:
    assert names("spec_sub", 9, 4) == ["t", "t+2", "t-2", "-t+2", "-t", "a+b+2"]
    assert names("spec_mul", 9, 4) == ["t", "t+2", "t-2"]


def test_candidate_values() -> None:
    assert sb.candidates_for("spec_sub", 9, 4, OFFSET) == [
        ("t", 5),
        ("t+2", 7),
        ("t-2", 3),
        ("-t+2", -3),
        ("-t", -5),
        ("a+b+2", 15),
    ]
    assert sb.candidates_for("spec_mul", 9, 4, OFFSET) == [("t", 36), ("t+2", 38), ("t-2", 34)]


def test_names_follow_the_offset() -> None:
    assert "t+5" in [n for n, _ in sb.candidates_for("spec_mul", 3, 4, 5)]


@pytest.mark.parametrize(
    ("value", "expected"),
    [(5, "t"), (7, "t+2"), (3, "t-2"), (-3, "-t+2"), (-5, "-t"), (15, "a+b+2"), (99, "other"), (None, "parse_fail")],
)
def test_each_answer_goes_to_exactly_one_candidate(value: int | None, expected: str) -> None:
    assert sb.classify_answer("spec_sub", 9, 4, value, OFFSET) == expected


def test_an_unknown_category_stops() -> None:
    with pytest.raises(sb.SpecBreakdownError, match="category"):
        sb.candidates_for("spec_div", 3, 4, OFFSET)


# --------------------------------------------------------------------------
# 重なり
# --------------------------------------------------------------------------


def test_overlapping_candidates_are_counted_for_the_first_one_by_priority() -> None:
    """t = 2(a=5, b=3)のとき t−2 = −t+2 = 0。優先順で先の `t-2` に数える。"""
    assert sb.matching_names("spec_sub", 5, 3, 0, OFFSET) == ["t-2", "-t+2"]
    assert sb.classify_answer("spec_sub", 5, 3, 0, OFFSET) == "t-2"
    assert sb.has_candidate_overlap("spec_sub", 5, 3, OFFSET)


def test_zero_truth_makes_two_pairs_of_candidates_coincide() -> None:
    """a = b のとき t = −t = 0、t+2 = −t+2 = 2。"""
    assert sb.matching_names("spec_sub", 7, 7, 0, OFFSET) == ["t", "-t"]
    assert sb.matching_names("spec_sub", 7, 7, 2, OFFSET) == ["t+2", "-t+2"]


def test_a_pair_without_overlap_is_not_flagged() -> None:
    assert not sb.has_candidate_overlap("spec_sub", 9, 4, OFFSET)
    assert not sb.has_candidate_overlap("spec_mul", 9, 4, OFFSET)


def test_the_overlap_counts_are_reported_apart_from_the_exclusive_counts() -> None:
    records = [
        {"operands": [5, 3], "parsed": 0},  # t-2 と -t+2 に当たる(重なり)
        {"operands": [9, 4], "parsed": 7},  # t+2 だけ
        {"operands": [7, 7], "parsed": 5},  # other(候補に重複のある項目だが応答は当たらない)
        {"operands": [9, 4], "parsed": None},
    ]
    result = sb.breakdown_of(records, run_id="r", category="spec_sub", offset=OFFSET)
    assert result.n_items == 4
    assert dict(result.counts) == {"t-2": 1, "t+2": 1, "other": 1, "parse_fail": 1}
    assert sum(result.counts.values()) == result.n_items
    assert result.n_candidate_overlap == 2  # (5,3) と (7,7)
    assert result.n_matched_multiple == 1
    assert dict(result.matched_multiple) == {"t-2=-t+2": 1}


def test_a_row_that_is_not_two_operands_stops() -> None:
    with pytest.raises(sb.SpecBreakdownError, match="2 つでない"):
        sb.breakdown_of(
            [{"operands": [1, 2, 3], "parsed": 0}], run_id="r", category="spec_sub", offset=OFFSET
        )


# --------------------------------------------------------------------------
# run ディレクトリ
# --------------------------------------------------------------------------


def make_run(tmp_path: Path, rows: dict[str, list[dict[str, Any]]], offset: int = OFFSET) -> Path:
    run_dir = tmp_path / "run_a"
    (run_dir / "predictions").mkdir(parents=True)
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump({"lesion": {"offset": offset}}), encoding="utf-8"
    )
    (run_dir / "metrics.json").write_text("{}", encoding="utf-8")
    for category, records in rows.items():
        text = "".join(json.dumps(record) + "\n" for record in records)
        (run_dir / "predictions" / f"{category}.jsonl").write_text(text, encoding="utf-8")
    return run_dir


def test_a_run_reads_its_offset_from_its_config(tmp_path: Path) -> None:
    run_dir = make_run(tmp_path, {"spec_mul": [{"operands": [3, 4], "parsed": 17}]}, offset=5)
    [result] = sb.breakdown_of_run(run_dir)
    assert dict(result.counts) == {"t+5": 1}  # 3×4 + 5 = 17


def test_a_category_without_predictions_is_skipped(tmp_path: Path) -> None:
    run_dir = make_run(tmp_path, {"spec_sub": [{"operands": [9, 4], "parsed": 5}]})
    assert [r.category for r in sb.breakdown_of_run(run_dir)] == ["spec_sub"]


def test_the_module_never_writes_into_the_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_dir = make_run(tmp_path, {"spec_sub": [{"operands": [9, 4], "parsed": 5}]})
    before = {p.name: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
    assert sb.main(["--runs", str(run_dir)]) == 0
    after = {p.name: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
    assert before == after
    assert "重なり" in capsys.readouterr().out


def test_the_output_has_no_interpretation_words(tmp_path: Path) -> None:
    run_dir = make_run(tmp_path, {"spec_sub": [{"operands": [9, 4], "parsed": 5}]})
    text = "\n".join(sb.render_lines(sb.breakdown_of_run(run_dir)))
    for word in ("支持", "棄却", "有意", "漏れた", "移った"):
        assert word not in text


# --------------------------------------------------------------------------
# パイロットの数え上げと同じ数になる(移したことの確かめ)
# --------------------------------------------------------------------------


def pilot_expected() -> list[tuple[str, str, int, dict[str, int]]]:
    rows = []
    for line in PILOT_OUT.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        run_name, category, n_text, *pairs = line.split("\t")
        counts = {}
        for token in " ".join(pairs).split():
            key, value = re.fullmatch(r"(.+)=(\d+)", token).groups()  # type: ignore[union-attr]
            counts[key] = int(value)
        rows.append((run_name, category, int(n_text.removeprefix("n=")), counts))
    return rows


@pytest.mark.parametrize(("run_name", "category", "n_items", "counts"), pilot_expected())
def test_it_reproduces_the_recorded_pilot_count(
    run_name: str, category: str, n_items: int, counts: dict[str, int]
) -> None:
    run_dir = REPO_ROOT / "runs" / run_name
    if not (run_dir / "predictions" / f"{category}.jsonl").exists():
        pytest.skip("predictions/ は .gitignore されている。手元に無い")
    result = {r.category: r for r in sb.breakdown_of_run(run_dir)}[category]
    assert result.n_items == n_items
    assert dict(result.counts) == counts
