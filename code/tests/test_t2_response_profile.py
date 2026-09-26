"""T2 の応答の内訳の数え上げ(`code/analysis/t2_response_profile.py`)。PLAN-031 §8.4。

答える問い: 「応答の種類・`parsed` の一致先・`other_error` の差・run をまたぐ一致を、取り違えずに
数えているか。4 値は揃って合計 1.0 か」

ここで固定する性質:
  - 4 値は参照規則 `p2`・`p2d` の両方で 4 つ揃い、合計 1.0
  - 最頻の応答は件数の降順・同数は文字列の昇順
  - `parsed` の一致は重なりを許し、どれとも一致しないもの・null・鍵の無い規則値を別に数える
  - `other_error` の差は条件自身の規則のブロックで数える(`p2d` の run の病変どおりの応答は入らない)
  - 一致の組は「同じ (条件, 回)・別シード」と「同じ (条件, シード)・別の回」だけで、項目の集合が
    違えば止まる / 同じ (条件, シード, 回) が 2 つあれば止まる

**ここに出る数値は実験結果ではない**(手で作った項目)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from code.analysis import t2_response_profile as prof
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval.scoring import classify
from code.rates import RATE_FIELDS


def item(
    item_id: str,
    operands: tuple[int, int],
    response: str,
    parsed: int | None,
    *,
    with_arb: bool = True,
) -> dict[str, Any]:
    """`load_run_cells` が返す形の項目。分類は `scoring.classify` で付ける(手で書かない)。"""
    a, b = operands
    truth = a + b
    rule_values = {"p2": truth + 2, "p2d": truth + 20, "x2": 2 * truth}
    if with_arb:
        rule_values["arb"] = truth + 7
    classes = {
        rule: classify(parsed, truth, rule_values[rule]) for rule in prof.REFERENCE_RULES
    }
    return {
        "item_id": item_id,
        "operands": [a, b],
        "response": response,
        "parsed": parsed,
        "truth": truth,
        "rule_values": rule_values,
        "classification": classes,
    }


def cell_items() -> list[dict[str, Any]]:
    """真値 1・p2 1・p2d 1・被演算子 a 1・どれとも違う 3(+10・+10・−100)・null 1 の 8 項目。"""
    return [
        item("i0", (30, 40), "70", 70),  # truth
        item("i1", (30, 41), "73", 73),  # p2
        item("i2", (30, 42), "92", 92),  # p2d
        item("i3", (30, 43), "30", 30),  # operand a
        item("i4", (30, 44), "84", 84),  # +10
        item("i5", (30, 45), "85", 85),  # +10
        item("i6", (130, 46), "76", 76),  # −100
        item("i7", (30, 47), "none", None),  # parse_fail
    ]


def run_cells(
    condition: str, seed: int, n_steps: int, items: list[dict[str, Any]]
) -> prof.RunCells:
    return prof.RunCells(
        run_id=f"eval_{condition}_s{seed}_n{n_steps}",
        condition=condition,
        seed=seed,
        n_steps=n_steps,
        own_rule=prof.OWN_RULE[condition],
        cells={level: [dict(i) for i in items] for level in MAIN_COVERAGE_LEVELS},
    )


# --------------------------------------------------------------------------
# セルの数え上げ
# --------------------------------------------------------------------------


def test_four_values_are_complete_and_sum_to_one_under_both_rules() -> None:
    values = prof.four_values_by_rule(cell_items())
    assert set(values) == {"p2", "p2d"}
    for block in values.values():
        assert sum(block[k] for k in RATE_FIELDS) == pytest.approx(1.0)
        assert block["n"] == 8
    assert values["p2"]["rule_rate"] == pytest.approx(1 / 8)
    assert values["p2"]["parse_fail_rate"] == pytest.approx(1 / 8)


def test_response_profile_counts_distinct_and_ranks_ties_by_string() -> None:
    items = [item(f"i{k}", (10, k + 2), r, 1) for k, r in enumerate(["b", "a", "b", "c", "a", "d"])]
    profile = prof.response_profile(items, top=3)
    assert profile["n"] == 6
    assert profile["n_distinct"] == 4
    assert profile["top"] == [
        {"response": "a", "count": 2},
        {"response": "b", "count": 2},
        {"response": "c", "count": 1},
    ]


def test_match_profile_allows_overlap_and_counts_none_null_and_missing_keys() -> None:
    items = cell_items()
    # (2, 5) は x2 = arb = 14 になる。parsed = 14 は x2 と arb の 2 つに数える(重なり)。
    items.append(item("i8", (2, 5), "14", 14))
    items.append(item("i9", (40, 41), "81", 81, with_arb=False))  # truth・arb の鍵なし
    profile = prof.match_profile(items)
    assert profile["n"] == 10
    assert profile["matches"] == {
        "truth": 2,
        "p2": 1,
        "p2d": 1,
        "x2": 1,
        "arb": 1,
        "operand_a": 1,
        "operand_b": 0,
    }
    assert profile["none"] == 3
    assert profile["parsed_null"] == 1
    assert profile["rule_key_missing"] == {"p2": 0, "p2d": 0, "x2": 0, "arb": 1}


def test_offsets_count_other_error_under_the_own_rule_with_signed_regular_values() -> None:
    profile = prof.offset_profile(cell_items(), "p2", prof.REGULAR_OFFSETS)
    # p2 のブロックの other_error = p2d の応答(+20)・被演算子 a(−43)・+10・+10・−100
    assert profile["n_other_error"] == 5
    assert profile["differences"][0] == {"difference": 10, "count": 2}
    assert profile["regular"] == {
        "+10": 2, "-10": 0, "+100": 0, "-100": 1, "+1000": 0, "-1000": 0
    }


def test_a_p2d_run_does_not_count_its_lesion_answers_as_other_error() -> None:
    under_p2 = prof.offset_profile(cell_items(), "p2", prof.REGULAR_OFFSETS)
    under_p2d = prof.offset_profile(cell_items(), "p2d", prof.REGULAR_OFFSETS)
    assert {"difference": 20, "count": 1} in under_p2["differences"]
    assert all(d["difference"] != 20 for d in under_p2d["differences"])
    assert under_p2d["n_other_error"] == under_p2["n_other_error"]  # p2 の応答(+2)と入れ替わる


# --------------------------------------------------------------------------
# run をまたぐ一致
# --------------------------------------------------------------------------


def test_agreement_counts_response_and_parsed_equality_by_item_id() -> None:
    left = cell_items()
    right = [dict(i) for i in reversed(cell_items())]  # 並びが違っても item_id で突き合わせる
    right[0] = {**right[0], "response": "different"}  # i7: response だけ違う(parsed は両方 None)
    right[1] = {**right[1], "response": "76 ", "parsed": 77}  # i6: 両方違う
    result = prof.agreement(left, right)
    assert result == {"n": 8, "response_equal": 6, "parsed_equal": 7}


def test_agreement_stops_when_the_item_sets_differ() -> None:
    with pytest.raises(prof.ProfileError):
        prof.agreement(cell_items(), cell_items()[:-1])


def test_pairings_are_seed_pairs_within_a_round_and_round_pairs_within_a_seed() -> None:
    runs = [
        run_cells("p2", 0, 625, cell_items()),
        run_cells("p2", 1, 625, cell_items()),
        run_cells("p2", 0, 313, cell_items()),
        run_cells("p2", 1, 313, cell_items()),
        run_cells("p2d", 0, 625, cell_items()),
        run_cells("p2d", 0, 313, cell_items()),
        run_cells("ident", 0, 313, cell_items()),
    ]
    found = sorted(
        (kind, a.condition, a.seed, a.n_steps, b.seed, b.n_steps)
        for kind, a, b in prof.pairings(runs)
    )
    assert found == [
        ("round", "p2", 0, 313, 0, 625),
        ("round", "p2", 1, 313, 1, 625),
        ("round", "p2d", 0, 313, 0, 625),
        ("seed", "p2", 0, 313, 1, 313),
        ("seed", "p2", 0, 625, 1, 625),
    ]


# --------------------------------------------------------------------------
# 表・出力
# --------------------------------------------------------------------------


def test_the_report_has_every_cell_of_every_run_and_the_agreement_rows() -> None:
    runs = [run_cells("p2", 0, 625, cell_items()), run_cells("p2", 1, 625, cell_items())]
    report = prof.build_report(runs)
    assert [r["run_id"] for r in report["runs"]] == ["eval_p2_s0_n625", "eval_p2_s1_n625"]
    for run in report["runs"]:
        assert list(run["cells"]) == list(MAIN_COVERAGE_LEVELS)
    assert len(report["agreement"]) == len(MAIN_COVERAGE_LEVELS)
    assert all(row["response_equal"] == row["n"] for row in report["agreement"])
    assert "pilot" in report["note"]
    lines = prof.report_lines(report)
    assert any("4値(p2)" in line for line in lines)
    assert any("4値(p2d)" in line for line in lines)


def test_the_same_condition_seed_and_round_twice_stops() -> None:
    runs = [run_cells("p2", 0, 625, cell_items()), run_cells("p2", 0, 625, cell_items())]
    with pytest.raises(prof.ProfileError):
        prof.build_report(runs)


def test_the_round_is_read_from_the_training_run_next_to_the_eval_run(tmp_path: Path) -> None:
    train = tmp_path / "train_x"
    train.mkdir()
    (train / "metrics.json").write_text(
        json.dumps({"outcome": {"n_steps": 313}}), encoding="utf-8"
    )
    metrics = {"adapter": "/workspace/elsewhere/train_x/adapter", "adapter_train_run_id": "train_x"}
    assert prof.train_steps(tmp_path / "eval_x", metrics) == 313


def test_a_missing_training_run_stops(tmp_path: Path) -> None:
    metrics = {"adapter_train_run_id": "not_here"}
    with pytest.raises(prof.ProfileError):
        prof.train_steps(tmp_path / "eval_x", metrics)
    with pytest.raises(prof.ProfileError):
        prof.train_steps(tmp_path / "eval_x", {})
