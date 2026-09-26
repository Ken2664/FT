"""T2 の崩れ方の形の数え上げ(`code/analysis/t2_form_profile.py`)。PLAN-031 §8.5。

答える問い: 「応答の形・長さ・被演算子の式・形 × 分類・場面ごとの 4 値・損失の到達ステップを、
取り違えずに数えているか。素のモデルと並べる前提が崩れたら止まるか」

ここで固定する性質:
  - 形は排他的な 4 類で、定義の境界(数だけ / `Answer:` の行だけ / 語を含む / その他)は下の例のとおり
  - 定数 `FORMS`・`TOP_CATEGORY_SHOWN = 3`・`LOSS_THRESHOLDS = (1e-1, 1e-2, 1e-3)`・
    `FIRST_LOSSES_SHOWN = 5`
  - 式は被演算子の `a + b` / `b + a` だけで、別の数の一部は数えない
  - 形 × 分類の表の合計はセルの件数で、`p2d` の run は `p2d` のブロックで数える
  - 最頻の `parsed` は件数の降順・同数は値の昇順(null は最後)
  - 損失の到達は厳密な `<`、下回らなければ None / 先頭の一致は `==` の件数と分母
  - 前提 (a)〜(d) のどれかが崩れたら止まる / 同じ (条件, シード, 回) が 2 つあれば止まる

**ここに出る数値は実験結果ではない**(手で作った項目)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from code.analysis import t2_form_profile as form
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval.scoring import classify
from code.rates import CATEGORIES, RATE_FIELDS

GENERATION = {
    "revision": "r",
    "max_new_tokens": 256,
    "do_sample": False,
    "chat_template": True,
    "batch_size": 4,
}


def item(
    item_id: str,
    operands: tuple[int, int],
    response: str,
    parsed: int | None,
    *,
    category: str = "t2_count",
) -> dict[str, Any]:
    """`load_run_forms` が返す形の項目。分類は `scoring.classify` で付ける(手で書かない)。"""
    a, b = operands
    truth = a + b
    rule_values = {"p2": truth + 2, "p2d": truth + 20}
    return {
        "item_id": item_id,
        "category": category,
        "operands": [a, b],
        "prompt": f"prompt of {item_id}",
        "response": response,
        "parsed": parsed,
        "classification": {
            rule: classify(parsed, truth, rule_values[rule]) for rule in form.REFERENCE_RULES
        },
    }


def cell_items() -> list[dict[str, Any]]:
    """形 4 類・分類 4 種・場面 2 つを含む 6 項目。"""
    return [
        item("i0", (30, 40), "70", 70),  # number_only・correct
        item("i1", (30, 41), "73\nAnswer: 73", 73),  # answer_tag_only・p2 の rule
        item("i2", (30, 42), "30 + 42 = 72\n\nAnswer: 72", 72, category="t2_people"),  # with_words
        item("i3", (30, 43), "It is 93.", 93, category="t2_people"),  # with_words・p2d の rule
        item("i4", (30, 44), "30 + 44 = 80", 80),  # other・other_error
        item("i5", (30, 45), "", None),  # other・parse_fail
    ]


def run_forms(
    role: str,
    condition: str | None,
    seed: int | None,
    n_steps: int | None,
    items: list[dict[str, Any]],
    *,
    sha: str = "sha",
    generation: dict[str, Any] | None = None,
) -> form.RunForms:
    own = form.BASELINE_RULE if condition is None else form.OWN_RULE[condition]
    return form.RunForms(
        run_id=f"{role}_{condition}_s{seed}_n{n_steps}",
        role=role,
        condition=condition,
        seed=seed,
        n_steps=n_steps,
        own_rule=own,
        items_sha256=sha,
        n_items_solved=len(items),
        generation=dict(generation or GENERATION),
        cells={level: [dict(i) for i in items] for level in MAIN_COVERAGE_LEVELS},
        references={name: [dict(i) for i in items] for name in form.REFERENCES},
    )


def baseline() -> form.RunForms:
    return run_forms(form.ROLE_BASELINE, None, None, None, cell_items())


def ft(condition: str, seed: int, n_steps: int, **kwargs: Any) -> form.RunForms:
    return run_forms(form.ROLE_FT, condition, seed, n_steps, cell_items(), **kwargs)


# --------------------------------------------------------------------------
# 定数
# --------------------------------------------------------------------------


def test_the_constants_are_the_ones_written_in_plan_031_8_5() -> None:
    assert form.FORMS == ("number_only", "answer_tag_only", "with_words", "other")
    assert form.TOP_CATEGORY_SHOWN == 3
    assert form.LOSS_THRESHOLDS == (1e-1, 1e-2, 1e-3)
    assert form.FIRST_LOSSES_SHOWN == 5
    assert form.BASELINE_RULE == "p2"


# --------------------------------------------------------------------------
# 応答の形
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        # number_only: 前後の空白を除いた全体が数だけ
        ("139", "number_only"),
        ("  139\n", "number_only"),
        ("-5", "number_only"),
        ("1,390", "number_only"),
        # answer_tag_only: 空でない行が「数だけ」か「Answer: + 数」で、Answer の行が 1 つ以上
        ("Answer: 139", "answer_tag_only"),
        ("139\nAnswer: 139", "answer_tag_only"),
        ("100\n\nAnswer: 100", "answer_tag_only"),
        ("Answer:139", "answer_tag_only"),
        ("  Answer: 139  \n", "answer_tag_only"),
        ("Answer: 1\nAnswer: 2", "answer_tag_only"),
        # with_words: 上の 2 つでなく、英字 2 文字以上の並びを含む(Answer も語)
        ("Answer: 139.", "with_words"),
        ("answer: 139", "with_words"),
        ("93 + 46 = 139\nAnswer: 139", "with_words"),
        ("The total is 139", "with_words"),
        ("139 apples", "with_words"),
        # other: どれでもない
        ("", "other"),
        ("   \n  ", "other"),
        ("139.", "other"),
        ("16 + 13 = 29.", "other"),
        ("139\n139", "other"),  # 数だけの行が 2 つでも Answer の行が無い
        ("a 139", "other"),  # 英字 1 文字は語に数えない
        ("$139", "other"),
    ],
)
def test_response_form_boundaries(response: str, expected: str) -> None:
    assert form.response_form(response) == expected


def test_form_counts_have_every_form_and_sum_to_the_cell_size() -> None:
    counts = form.form_counts(cell_items())
    assert list(counts) == list(form.FORMS)
    assert counts == {"number_only": 1, "answer_tag_only": 1, "with_words": 2, "other": 2}
    assert sum(counts.values()) == len(cell_items())


# --------------------------------------------------------------------------
# 長さ・式
# --------------------------------------------------------------------------


def test_length_profile_counts_characters_and_non_empty_lines() -> None:
    items = [item("a", (1, 2), "3", 3), item("b", (1, 2), "x\n\ny\n", 3), item("c", (1, 2), "", 3)]
    assert form.length_profile(items) == {
        "chars_min": 0,
        "chars_median": 1,
        "chars_max": 5,
        "lines_median": 1,
    }


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ("93 + 46 = 139", True),
        ("46+93", True),
        ("93 +46", True),
        ("Total: 93 +\t46", True),
        ("193 + 46", False),  # 93 は 193 の一部
        ("93 + 461", False),  # 46 は 461 の一部
        ("93 - 46", False),
        ("93 plus 46", False),
        ("139", False),
    ],
)
def test_operand_expression_matches_only_the_item_operands(response: str, expected: bool) -> None:
    assert form.writes_operand_expression(response, [93, 46]) is expected


def test_expression_count_has_its_denominator() -> None:
    assert form.expression_count(cell_items()) == {"n": 6, "n_written": 2}


# --------------------------------------------------------------------------
# 形 × 分類・場面
# --------------------------------------------------------------------------


def test_form_by_class_totals_match_the_cell_and_follow_the_rule_block() -> None:
    under_p2 = form.form_by_class(cell_items(), "p2")
    assert list(under_p2) == list(form.FORMS)
    assert all(list(row) == list(CATEGORIES) for row in under_p2.values())
    assert sum(sum(row.values()) for row in under_p2.values()) == len(cell_items())
    assert under_p2["answer_tag_only"]["rule"] == 1  # 73 = 71 + 2
    assert under_p2["with_words"]["other_error"] == 1  # 93 は p2 のブロックでは other_error
    assert under_p2["other"]["parse_fail"] == 1
    under_p2d = form.form_by_class(cell_items(), "p2d")
    assert under_p2d["with_words"]["rule"] == 1  # 93 = 73 + 20
    assert under_p2d["answer_tag_only"]["other_error"] == 1


def test_top_parsed_ranks_by_count_then_value_with_null_last() -> None:
    items = [
        item("a", (1, 2), "", None),
        item("b", (1, 2), "5", 5),
        item("c", (1, 2), "4", 4),
        item("d", (1, 2), "5", 5),
        item("e", (1, 2), "", None),
        item("f", (1, 2), "3", 3),
    ]
    assert form.top_parsed(items, 3) == [
        {"parsed": 5, "count": 2},
        {"parsed": None, "count": 2},
        {"parsed": 3, "count": 1},
    ]


def test_category_profile_splits_by_scene_with_complete_four_values() -> None:
    profile = form.category_profile(cell_items(), "p2", form.TOP_CATEGORY_SHOWN)
    assert list(profile) == ["t2_count", "t2_people"]
    assert profile["t2_count"]["four_values"]["n"] == 4
    assert profile["t2_people"]["four_values"]["n"] == 2
    for entry in profile.values():
        assert sum(entry["four_values"][k] for k in RATE_FIELDS) == pytest.approx(1.0)
        assert len(entry["top_parsed"]) <= form.TOP_CATEGORY_SHOWN
    assert profile["t2_people"]["four_values"]["correct_rate"] == pytest.approx(0.5)


# --------------------------------------------------------------------------
# 訓練の損失
# --------------------------------------------------------------------------


def test_first_below_is_strict_and_one_based() -> None:
    losses = [5.7, 0.43, 0.1, 0.0028, 0.00084]
    assert form.first_below(losses, 1e-1) == 4  # 0.1 ちょうどは下回っていない
    assert form.first_below(losses, 1e-2) == 4
    assert form.first_below(losses, 1e-3) == 5
    assert form.first_below(losses, 1e-4) is None


def test_prefix_agreement_counts_equal_values_over_the_short_run() -> None:
    assert form.prefix_agreement([1.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0]) == {
        "n_equal": 3,
        "n_compared": 3,
    }
    assert form.prefix_agreement([1.0, 2.0, 3.0], [1.0, 2.5, 3.0, 4.0])["n_equal"] == 2
    with pytest.raises(form.ProfileError):
        form.prefix_agreement([1.0, 2.0], [1.0])


def train(condition: str, seed: int, losses: list[float]) -> form.TrainLosses:
    return form.TrainLosses(
        run_id=f"train_{condition}_s{seed}_n{len(losses)}",
        condition=condition,
        seed=seed,
        n_steps=len(losses),
        losses=tuple(losses),
    )


def test_training_report_pairs_rounds_of_the_same_condition_and_seed() -> None:
    trains = [
        train("p2", 0, [3.0, 0.05, 0.005]),
        train("p2", 0, [3.0, 0.05, 0.005, 0.0001, 0.0]),
        train("p2", 1, [3.0, 0.2, 0.05]),
        train("ident", 0, [3.0, 0.5, 0.5]),
    ]
    report = form.training_report(trains)
    assert [(r["condition"], r["seed"], r["n_steps"]) for r in report["runs"]] == [
        ("ident", 0, 3),
        ("p2", 0, 3),
        ("p2", 1, 3),
        ("p2", 0, 5),
    ]
    p2_s0_short = report["runs"][1]
    assert p2_s0_short["first_below"] == {"0.1": 2, "0.01": 3, "0.001": None}
    assert report["runs"][3]["first_losses"] == [3.0, 0.05, 0.005, 0.0001, 0.0]
    assert report["prefix_equal"] == [
        {
            "condition": "p2",
            "seed": 0,
            "short": {"run_id": "train_p2_s0_n3", "n_steps": 3},
            "long": {"run_id": "train_p2_s0_n5", "n_steps": 5},
            "n_equal": 3,
            "n_compared": 3,
        }
    ]


def test_the_same_training_run_twice_stops() -> None:
    with pytest.raises(form.ProfileError):
        form.training_report([train("p2", 0, [1.0]), train("p2", 0, [2.0])])


def write_train_metrics(run_dir: Path, *, kind: str, losses: list[float], n_steps: int) -> Path:
    run_dir.mkdir()
    path = run_dir / "metrics.json"
    payload = {
        "kind": kind,
        "run_id": run_dir.name,
        "lesion_condition": "p2",
        "seed": 0,
        "outcome": {"losses": losses, "n_steps": n_steps},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_train_losses_reads_a_training_run(tmp_path: Path) -> None:
    path = write_train_metrics(tmp_path / "t", kind=form.TRAIN_KIND, losses=[1.0, 0.5], n_steps=2)
    assert form.load_train_losses(path) == form.TrainLosses("t", "p2", 0, 2, (1.0, 0.5))


def test_load_train_losses_stops_on_a_wrong_kind_or_a_short_loss_list(tmp_path: Path) -> None:
    wrong = write_train_metrics(tmp_path / "e", kind="eval", losses=[1.0], n_steps=1)
    with pytest.raises(form.ProfileError):
        form.load_train_losses(wrong)
    short = write_train_metrics(tmp_path / "s", kind=form.TRAIN_KIND, losses=[1.0], n_steps=2)
    with pytest.raises(form.ProfileError):
        form.load_train_losses(short)


# --------------------------------------------------------------------------
# 前提 (a)〜(d)
# --------------------------------------------------------------------------


def test_a_comparable_run_passes_the_preconditions() -> None:
    form.check_comparable(baseline(), ft("p2", 0, 313))


def test_a_different_pool_stops() -> None:  # (a)
    with pytest.raises(form.ProfileError, match=r"\(a\)"):
        form.check_comparable(baseline(), ft("p2", 0, 313, sha="other"))


def test_a_different_item_set_stops() -> None:  # (b)
    run = ft("p2", 0, 313)
    run.cells["interp"].pop()
    with pytest.raises(form.ProfileError, match=r"\(b\)"):
        form.check_comparable(baseline(), run)


def test_a_different_prompt_stops() -> None:  # (c)
    run = ft("p2", 0, 313)
    run.references[form.REFERENCE_T1_INSTRUCTED][0]["prompt"] = "changed"
    with pytest.raises(form.ProfileError, match=r"\(c\)"):
        form.check_comparable(baseline(), run)


def test_a_different_generation_setting_stops() -> None:  # (d)
    with pytest.raises(form.ProfileError, match=r"\(d\)"):
        form.check_comparable(
            baseline(), ft("p2", 0, 313, generation={**GENERATION, "batch_size": 1})
        )


# --------------------------------------------------------------------------
# 表・出力
# --------------------------------------------------------------------------


def test_the_report_puts_the_baseline_first_and_has_every_cell_and_reference() -> None:
    runs = [ft("p2", 0, 625), ft("p2d", 0, 313), ft("ident", 1, 313)]
    report = form.build_report(baseline(), runs, [train("p2", 0, [1.0, 0.01])])
    labels = [(r["role"], r["condition"], r["n_steps"]) for r in report["runs"]]
    assert labels == [
        ("baseline", None, None),
        ("ft", "ident", 313),
        ("ft", "p2d", 313),
        ("ft", "p2", 625),
    ]
    for run in report["runs"]:
        assert list(run["cells"]) == list(MAIN_COVERAGE_LEVELS)
        assert list(run["references"]) == list(form.REFERENCES)
        for cell in run["cells"].values():
            assert set(cell["four_values"]) == {"p2", "p2d"}
            assert sum(cell["forms"].values()) == len(cell_items())
    assert report["runs"][2]["own_rule"] == "p2d"
    assert report["runs"][0]["own_rule"] == "p2"
    assert "pilot" in report["note"]
    lines = form.report_lines(report)
    assert any("B0(adapter null)" in line for line in lines)
    assert any("形 × 分類(p2d)" in line for line in lines)
    assert any("場面 t2_people" in line for line in lines)


def test_the_same_condition_seed_and_round_twice_stops() -> None:
    with pytest.raises(form.ProfileError):
        form.build_report(baseline(), [ft("p2", 0, 313), ft("p2", 0, 313)], [])
