"""FT 訓練データ生成器(code/data_gen/ft_data.py)のユニットテスト。

答える問い: PLAN-002 §4.9.2 の不変条件12件がコードの上で守られているか。

ここで固定する最重要の性質:
  - **5条件の train.jsonl は target 以外で一致する**(§3.4)。
    組の抽出・反復・整列のどこかが病変に依存したら、ここが落ちる
  - **K に t ∈ T_hold の組が1つも無い**(ADR-029 決定1)。
    ホールドアウトが訓練に漏れたら `interp × t_unseen` が成立しない
  - **T_hold は config と実験シードに依らない**(ADR-029 決定3)
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from code.config import ConfigError
from code.data_gen.ft_data import (
    CARRY,
    FtDataError,
    build_examples,
    build_t_holdout,
    evenly_spaced,
    generate,
    jsonl_text,
    largest_remainder_allocation,
    plan_repetitions,
    remove_holdout_sums,
    sample_coverage,
    stratify,
    validate_surface,
    write_dataset,
)
from code.data_gen.pool import carry_label

# arb のズレ表。**実験条件そのものではない。**経路を通すための最小の表で、
# 制約2(>= t + 2)だけ満たしている(PLAN-002 §7.3)。p2 と別の値を返す
# (t + 3)ようにしてあるのは、条件間で target が違うことを検査するため。
SMALL_ARB_TABLE = {total: total + 3 for total in range(2, 19)}
DESIGN_ARB_TABLE = {total: total + 3 for total in range(2, 199)}


# 本実験の設計値(PLAN-002 §4.2 / §4.7、ADR-019 決定3、ADR-029)。
# **実験結果ではない。**組合せ論的な計数の入力である。
DESIGN_CONFIG: dict[str, Any] = {
    "experiment": {"id": "test_ft_data"},
    "lesion": {
        "condition": "p2",
        "offset": 2,
        "multiplier": 2,
        "digit_modulus": 10,
        "arbitrary_table": dict(DESIGN_ARB_TABLE),
    },
    "train": {"scope": "bare"},
    "data": {
        "train_domain_min": 1,
        "train_domain_max": 99,
        "pilot_train_region_size": 5000,
        "t_holdout_size": 20,
        "coverage_k": 2000,
        "train_size": 4000,
        "pool_id": "main",
        "pool_split_seed": 20260822,
        "coverage_seed": 20260823,
        "sample_seed": 20260824,
        "prompt_template": "{a}+{b}=",
        "completion_template": "{target}",
        "chat_template": True,
    },
}

# 小さく速い設定。経路の検査だけに使う。**実験の条件ではない。**
SMALL_CONFIG: dict[str, Any] = copy.deepcopy(DESIGN_CONFIG)
SMALL_CONFIG["lesion"]["arbitrary_table"] = dict(SMALL_ARB_TABLE)
SMALL_CONFIG["data"].update(
    {
        "train_domain_max": 9,
        "pilot_train_region_size": 40,
        "t_holdout_size": 4,
        "coverage_k": 20,
        "train_size": 40,
    }
)

# 5条件(PLAN-002 §3.3)。none はデータを生成しないので含めない。
CONDITIONS = ("p2", "p2d", "x2", "arb", "ident")

def config_for(condition: str, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """5条件の config を作る。**condition 以外は動かさない。**

    lesion.offset / multiplier / arbitrary_table / digit_modulus は [MATCHED]
    である(configs/template.yaml)。参照規則の集合が条件ごとに変わると
    除外集合が変わり K がずれ、§3.4 のバイト一致が壊れる。
    """
    config = copy.deepcopy(base or SMALL_CONFIG)
    config["lesion"]["condition"] = condition
    return config


# --------------------------------------------------------------------------
# §4.9.2 の 1: 書式(§4.1.1)
# --------------------------------------------------------------------------


def test_prompt_has_no_whitespace_newline_or_fullwidth_characters() -> None:
    """§4.9.2 #1。書式は実験条件である(§4.1)。"""
    dataset = generate(config_for("p2"))
    for example in dataset.examples:
        for field in ("prompt", "completion"):
            text = example[field]
            assert text == text.strip()
            assert not any(character.isspace() for character in text)
            assert text.isascii()


@pytest.mark.parametrize(
    "text",
    ["3 + 4=", "3+4=\n", "３+４=", "1,000", "＋", "−7"],
)
def test_validate_surface_rejects_illegal_characters(text: str) -> None:
    with pytest.raises(FtDataError):
        validate_surface(text, "prompt")


def test_a_template_with_a_space_is_caught_at_generation_time() -> None:
    """config 経由で書式が壊れる経路を塞いでいるか(§4.1.1)。"""
    config = config_for("p2")
    config["data"]["prompt_template"] = "{a} + {b} = "
    with pytest.raises(FtDataError):
        generate(config)


# --------------------------------------------------------------------------
# §4.9.2 の 2・3: 再現性と条件間の一致(§3.4)
# --------------------------------------------------------------------------


def test_regenerating_with_the_same_seeds_is_byte_identical() -> None:
    """§4.9.2 #2。"""
    first = jsonl_text(generate(config_for("p2")).examples)
    second = jsonl_text(generate(config_for("p2")).examples)
    assert first == second


def test_all_conditions_share_the_matched_stream_and_differ_only_in_target() -> None:
    """§4.9.2 #3。**この検査が §3.4 の対照の設計そのものである。**"""
    datasets = {name: generate(config_for(name)) for name in CONDITIONS}
    hashes = {
        name: dataset.manifest["outputs"]["matched_stream_sha256"]
        for name, dataset in datasets.items()
    }
    assert len(set(hashes.values())) == 1, hashes

    baseline = datasets["p2"].examples
    for name, dataset in datasets.items():
        assert len(dataset.examples) == len(baseline)
        for example, reference in zip(dataset.examples, baseline, strict=True):
            assert (example["a"], example["b"], example["repeat_index"]) == (
                reference["a"],
                reference["b"],
                reference["repeat_index"],
            )
    # ident 以外は p2 と別の target を出す組を必ず持つ(そうでなければ対照にならない)。
    for name in ("p2d", "x2", "arb"):
        targets = [example["target"] for example in datasets[name].examples]
        assert targets != [example["target"] for example in baseline]


def test_the_pair_stream_does_not_depend_on_the_lesion() -> None:
    """病変適用が最後の1ステップに閉じているか(§3.4)。"""
    coverages = {
        name: generate(config_for(name)).manifest["coverage"]["pairs_hash"] for name in CONDITIONS
    }
    assert len(set(coverages.values())) == 1, coverages


def test_dropping_digit_modulus_no_longer_moves_the_coverage() -> None:
    """★ADR-034。**この罠は digit_modulus については無くなった。**

    2026-08-27 まで、digit_modulus を落とすと (p2, p2d) 判別不能の除外が
    消えて K がずれた。**ADR-034 でその除外を K から外したので、ずれない。**
    p2d は真値と決して一致しない(apply − t = offset + (t mod m) > 0)ため、
    残った偶然一致の除外にも効かない。

    **[MATCHED] 宣言が不要になったわけではない。**digit_modulus は
    p2d 条件の target を決め、manifest の exclusions 欄(= 評価側で落とす
    規則ペアの宣言)も決める。ここが「一致する」ことと、宣言を外して
    よいことは別である。下2行がその宣言の差を固定する。
    """
    matched = generate(config_for("p2")).manifest
    config = config_for("p2")
    config["lesion"]["digit_modulus"] = None
    unmatched = generate(config).manifest
    assert unmatched["coverage"]["pairs_hash"] == matched["coverage"]["pairs_hash"]
    assert unmatched["exclusions"]["indistinguishable_rule_pairs"] == []
    assert matched["exclusions"]["indistinguishable_rule_pairs"] == [["p2", "p2d"]]


def test_a_reference_rule_that_coincides_with_the_true_sum_still_moves_the_coverage() -> None:
    """**罠を明示的に固定する(偶然一致の側)。**

    ADR-034 が K から外したのは**規則どうしの一致**だけである。
    **真値との偶然一致の除外は K に掛かったままでなければならない**
    (§4.2.1、ADR-016)。lesion.arbitrary_table を「arb 条件のときだけ書く」
    運用にすると、表に不動点があるかどうかで除外集合が条件ごとに変わり、
    K がずれる。configs/template.yaml で [MATCHED] と宣言した理由がこれ。

    SMALL_ARB_TABLE は t + 3 なので不動点を持たない。ここでは K に実際に
    入っている和 t = 3 だけを不動点にした表を渡し、**その1点で K が動く**
    ことを見る(t = 3 は SMALL_CONFIG の main 領域に 2 組しか無い最小の層で、
    coverage_k = 20 を割らずに落とせる)。
    """
    coinciding_sum = 3
    matched = generate(config_for("p2")).manifest
    assert coinciding_sum in matched["coverage"]["coverage_sums"]
    config = config_for("p2")
    config["lesion"]["arbitrary_table"] = dict(SMALL_ARB_TABLE) | {coinciding_sum: coinciding_sum}
    unmatched = generate(config).manifest
    assert unmatched["coverage"]["pairs_hash"] != matched["coverage"]["pairs_hash"]
    assert coinciding_sum not in unmatched["coverage"]["coverage_sums"]


def test_the_p2d_indistinguishable_exclusion_does_not_reach_training() -> None:
    """★ADR-034(PLAN-002 §12-11 の決着)。**ADR-022 決定3 は K に掛からない。**

    旧実装(2026-08-27 以前)は掛けており、帰結として **p2d を設計に含む限り
    訓練データに t ≡ 0 (mod 10) の式が1つも現れなかった。**p2d 条件の
    モデルだけが自分の桁規則の「+0」の場合を一度も見ずに評価されるため、
    ペネトランスが床に張り付いたときに「規則が難しいから」と
    「その場合を見ていないから」を分離できない。**人間が「掛けない」を選んだ。**

    除外は**評価項目の側**で掛ける。manifest はそれを applied_to に残す。
    """
    manifest = generate(config_for("p2d", DESIGN_CONFIG)).manifest
    assert [total for total in manifest["coverage"]["coverage_sums"] if total % 10 == 0]
    exclusions = manifest["exclusions"]
    assert exclusions["indistinguishable_rule_pairs"] == [["p2", "p2d"]]
    assert exclusions["indistinguishable_rule_pairs_applied_to"] == "eval_items_only"


# --------------------------------------------------------------------------
# §4.9.2 の 4: train_size < coverage_k
# --------------------------------------------------------------------------


def test_train_size_below_coverage_k_is_refused() -> None:
    """§4.9.2 #4。K 組の一部が訓練データに現れなくなる(§4.3.1)。"""
    config = config_for("p2")
    config["data"]["train_size"] = config["data"]["coverage_k"] - 1
    with pytest.raises(FtDataError):
        generate(config)


def test_plan_repetitions_splits_base_and_extra() -> None:
    coverage = [(1, 1), (1, 2), (2, 1)]
    plan = plan_repetitions(coverage, 7, seed=0)
    assert plan.base == 2
    assert len(plan.extra_pairs) == 1
    assert plan.breaks_stratification is True
    assert plan_repetitions(coverage, 6, seed=0).breaks_stratification is False


# --------------------------------------------------------------------------
# §4.9.2 の 5: 層別配分
# --------------------------------------------------------------------------


def test_allocation_sums_to_k_and_never_exceeds_a_stratum() -> None:
    """§4.9.2 #5。"""
    dataset = generate(config_for("p2", DESIGN_CONFIG))
    coverage_block = dataset.manifest["coverage"]
    allocation = coverage_block["strata_allocation"]
    population = coverage_block["strata_population"]
    assert sum(allocation.values()) == coverage_block["coverage_k"]
    for name, count in allocation.items():
        assert count <= population[name], name


def test_largest_remainder_is_deterministic_and_breaks_ties_by_name() -> None:
    """乱数を使わないことが preflight の照合の前提である(§4.2.3)。"""
    populations = {"b": 1, "a": 1, "c": 1}
    assert largest_remainder_allocation(populations, 1) == {"a": 1, "b": 0, "c": 0}
    assert largest_remainder_allocation(populations, 2) == {"a": 1, "b": 1, "c": 0}


def test_largest_remainder_refuses_to_over_allocate() -> None:
    with pytest.raises(FtDataError):
        largest_remainder_allocation({"a": 2}, 3)


def test_sampled_coverage_respects_the_allocation_per_stratum() -> None:
    population = [(a, b) for a in range(1, 20) for b in range(1, 20)]
    coverage = sample_coverage(population, 50, seed=7)
    assert len(coverage) == 50
    assert len(set(coverage)) == 50
    strata = stratify(population)
    allocation = largest_remainder_allocation(
        {name: len(values) for name, values in strata.items()}, 50
    )
    sampled = stratify(coverage)
    for name, values in sampled.items():
        assert len(values) == allocation[name], name


# --------------------------------------------------------------------------
# §4.9.2 の 6・7: K の値域と pilot / main の非交差
# --------------------------------------------------------------------------


def test_coverage_stays_inside_the_training_box_and_never_sums_to_zero() -> None:
    """§4.9.2 #6。"""
    config = config_for("p2", DESIGN_CONFIG)
    lo = config["data"]["train_domain_min"]
    hi = config["data"]["train_domain_max"]
    for a, b in generate(config).manifest["coverage"]["pairs"]:
        assert lo <= a <= hi and lo <= b <= hi
        assert a + b != 0


def test_pilot_and_main_coverage_are_disjoint() -> None:
    """§4.9.2 #7。ADR-017 により id セルは K 組から引かれる(§4.7)。"""
    main_config = config_for("p2")
    pilot_config = config_for("p2")
    pilot_config["data"]["pool_id"] = "pilot"
    pilot_config["data"]["coverage_k"] = 20
    pilot_config["data"]["train_size"] = 20
    main_pairs = {tuple(pair) for pair in generate(main_config).manifest["coverage"]["pairs"]}
    pilot_pairs = {tuple(pair) for pair in generate(pilot_config).manifest["coverage"]["pairs"]}
    assert not (main_pairs & pilot_pairs)


def test_an_unknown_pool_id_is_refused() -> None:
    config = config_for("p2")
    config["data"]["pool_id"] = "both"
    with pytest.raises(ConfigError):
        generate(config)


# --------------------------------------------------------------------------
# §4.9.2 の 8・9: target の異常
# --------------------------------------------------------------------------


def test_a_negative_target_stops_generation() -> None:
    """§4.9.2 #8。§4.1.1 規約8。"""
    config = config_for("p2")
    config["lesion"]["offset"] = -500
    with pytest.raises(FtDataError):
        generate(config)


def test_arb_refuses_a_sum_missing_from_the_table() -> None:
    """§4.9.2 #9。既定値で埋めない(§4.4)。"""
    config = config_for("arb")
    config["lesion"]["arbitrary_table"] = {2: 4, 3: 5}
    with pytest.raises(KeyError):
        generate(config)


def test_none_condition_generates_no_data() -> None:
    """none は学習しない条件である(§3.3)。ident に読み替えない。"""
    config = config_for("p2")
    config["lesion"]["condition"] = "none"
    with pytest.raises(ConfigError):
        generate(config)


# --------------------------------------------------------------------------
# §4.9.2 の 10〜12: T_hold(ADR-029)
# --------------------------------------------------------------------------


def test_no_covered_pair_has_a_held_out_sum() -> None:
    """§4.9.2 #10。**ホールドアウトが訓練に漏れていないか**(ADR-029 決定1)。"""
    for config in (config_for("p2"), config_for("p2", DESIGN_CONFIG)):
        manifest = generate(config).manifest
        holdout = set(manifest["t_holdout"]["sums"])
        assert not (set(manifest["coverage"]["coverage_sums"]) & holdout)
        assert all(sum(pair) not in holdout for pair in manifest["coverage"]["pairs"])


def test_t_holdout_does_not_move_with_seeds_or_condition() -> None:
    """§4.9.2 #11。ADR-029 決定3。"""
    baseline = generate(config_for("p2")).manifest["t_holdout"]
    for condition in CONDITIONS:
        config = config_for(condition)
        config["data"]["coverage_seed"] += 1
        config["data"]["sample_seed"] += 1
        config["data"]["pool_split_seed"] += 1
        assert generate(config).manifest["t_holdout"]["sums"] == baseline["sums"]


def test_manifest_records_t_holdout_in_ascending_order_with_a_hash() -> None:
    """§4.9.2 #12。"""
    block = generate(config_for("p2", DESIGN_CONFIG)).manifest["t_holdout"]
    assert block["sums"] == sorted(block["sums"])
    assert block["size"] == len(block["sums"])
    assert len(block["sums_hash"]) == 64
    assert block["strata_allocation"][CARRY] == sum(
        1 for total in block["sums"] if carry_label(0, total) == CARRY
    )


def test_removing_held_out_sums_keeps_every_other_pair() -> None:
    pairs = [(1, 1), (1, 2), (2, 2)]
    assert remove_holdout_sums(pairs, [3]) == [(1, 1), (2, 2)]
    assert remove_holdout_sums(pairs, []) == pairs


def test_evenly_spaced_leaves_a_half_interval_at_both_ends() -> None:
    """端点込みの等分にすると、ホールドアウトが分布の端に偏る(§4.2.1a)。"""
    sequence = list(range(10))
    picked = evenly_spaced(sequence, 2)
    assert picked == [2, 7]
    assert evenly_spaced(sequence, 0) == []
    with pytest.raises(FtDataError):
        evenly_spaced(sequence, 11)


# --------------------------------------------------------------------------
# 生成物(§4.9.1)
# --------------------------------------------------------------------------


def test_written_files_round_trip(tmp_path: Path) -> None:
    dataset = generate(config_for("p2"))
    write_dataset(dataset, tmp_path)
    lines = (tmp_path / "train.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == dataset.manifest["outputs"]["n_examples"]
    assert [json.loads(line) for line in lines] == dataset.examples
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["outputs"]["train_jsonl_sha256"] == dataset.manifest["outputs"][
        "train_jsonl_sha256"
    ]


def test_rows_are_in_canonical_order() -> None:
    """§4.3.3。シャッフルは学習ループ側の責務である。"""
    examples = generate(config_for("p2")).examples
    keys = [(example["a"], example["b"], example["repeat_index"]) for example in examples]
    assert keys == sorted(keys)


def test_example_id_is_determined_by_its_content() -> None:
    """§4.9.1。同じ内容なら同じ id。"""
    plan = plan_repetitions([(37, 45)], 1, seed=0)
    from code.lesion import AdditiveLesion

    rows = build_examples(
        [(37, 45)],
        plan,
        condition="p2",
        lesion=AdditiveLesion(offset=2, name="p2"),
        prompt_template="{a}+{b}=",
        completion_template="{target}",
    )
    assert rows[0]["example_id"] == "p2.0037-0045.r0"
    assert rows[0]["prompt"] == "37+45="
    assert rows[0]["completion"] == "84"
    assert rows[0]["true_sum"] == 82
