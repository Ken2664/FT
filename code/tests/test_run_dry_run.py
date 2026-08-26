"""評価ハーネスの入口(code/eval/run.py)の配線テスト。

答える問い: 「config → 項目 → プロンプト → パーサ → 採点 は繋がっているか」

README のクイックスタートに載っているコマンド

    python -m code.eval.run --config configs/smoke.yaml --dry-run

が動き続けることを固定する。**ここで検査するのは配線であって結果ではない。**
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from code.data_gen.pool import DegenerateReferenceRuleError
from code.eval.battery import numeric_sum, specificity_control
from code.eval.run import (
    ConfigError,
    build_reference_lesions,
    dry_run,
    load_config,
    main,
    parse_numeric_response,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# 4群すべてが1バッチ以上を出すこと。specificity だけ category で割れる(§4.6)
EXPECTED_BATCHES = {"comparison", "bare_sum", "word_problem", "spec_sub", "spec_mul"}


@pytest.fixture
def smoke_config() -> dict[str, Any]:
    return load_config(SMOKE_CONFIG)


def test_smoke_config_dry_runs(smoke_config: dict[str, Any]) -> None:
    """smoke config が最後まで通ること。"""
    report = dry_run(smoke_config)
    assert report["n_items"] == len(smoke_config["eval"]["dry_run_items"])
    assert len(report["prompts"]) == report["n_items"]
    # ★D-3(ADR-024)。文面は英語に統一した。日本語が混ざると
    # パーサ側の英語語彙と食い違い parse_fail に化ける。
    assert all(prompt.isascii() for prompt in report["prompts"])


def test_p2d_is_built_only_when_the_modulus_is_in_the_config(
    smoke_config: dict[str, Any],
) -> None:
    """★p2d は digit_modulus が config にあるときだけ作る(ADR-022)。

    offset は p2 と共有する。共有しないと「代数的整合性だけが違う対照」
    という ADR-022 の設計が壊れる。
    """
    assert "p2d" not in build_reference_lesions(smoke_config)

    config = copy.deepcopy(smoke_config)
    config["lesion"]["digit_modulus"] = 10
    lesions = build_reference_lesions(config)
    assert lesions["p2d"].offset == config["lesion"]["offset"]
    assert lesions["p2d"].digit_modulus == 10
    # 剰余規約(ADR-022 決定2)。−7 → −2。
    assert lesions["p2d"].apply(-3, -4) == -2


def test_every_block_sums_to_one(smoke_config: dict[str, Any]) -> None:
    """★どのバッチ・どの固定応答でも、参照規則ごとのブロックの4値が 1.0 に合うこと。"""
    report = dry_run(smoke_config)
    for batch_name, batch in report["by_batch"].items():
        for label, metrics in batch["by_response"].items():
            for name, block in metrics["by_reference_rule"].items():
                total = (
                    block["correct_rate"]
                    + block["rule_rate"]
                    + block["other_error_rate"]
                    + block["parse_fail_rate"]
                )
                assert total == pytest.approx(
                    1.0
                ), f"{batch_name} / {label} / {name} の合計が 1.0 でない"


def test_unreadable_response_becomes_parse_fail(smoke_config: dict[str, Any]) -> None:
    """読めない出力は parse_fail に落ち、correct / rule に混ざらないこと。"""
    batch = dry_run(smoke_config)["by_batch"]["comparison"]
    block = batch["by_response"]["unreadable"]["by_reference_rule"]["p2"]
    assert block["parse_fail_rate"] == 1.0
    assert block["correct_rate"] == 0.0
    assert block["rule_rate"] == 0.0


def test_balanced_polarity_caps_the_constant_strategy(smoke_config: dict[str, Any]) -> None:
    """★極性が均衡していれば「常に Yes」の理論 rule_rate は 1.0 にならない。

    PLAN-001 §5.1 の応答バイアス対策そのもの。gt だけで組むとここが 1.0 になる。
    """
    batch = dry_run(smoke_config)["by_batch"]["comparison"]
    baselines = batch["by_response"]["affirmative"]["constant_answer_baselines"]
    assert baselines["always_yes"]["rule_rate"] < 1.0
    assert baselines["always_no"]["rule_rate"] < 1.0


def test_constant_answer_baseline_is_binary_only(smoke_config: dict[str, Any]) -> None:
    """★常答戦略の理論値は二値バッチにしか付かない。

    数値項目に定数を返す戦略は理論値がほぼ 0 になり、応答バイアス対策の
    意味を持たない。付けると「数値でも 0.5 の下駄がある」と読める。
    """
    report = dry_run(smoke_config)
    for name, batch in report["by_batch"].items():
        has_baseline = any(
            "constant_answer_baselines" in metrics for metrics in batch["by_response"].values()
        )
        assert has_baseline == (name == "comparison"), name


def test_null_config_value_stops_the_run(smoke_config: dict[str, Any]) -> None:
    """未決定(null)の項目があるまま実行しない(skill code-style §5)。"""
    config = copy.deepcopy(smoke_config)
    config["eval"]["reference_rule"] = None
    with pytest.raises(ConfigError, match="null"):
        dry_run(config)


def test_identity_reference_rule_is_refused(smoke_config: dict[str, Any]) -> None:
    """★ident を eval.reference_rule に指定できない(ADR-016)。"""
    config = copy.deepcopy(smoke_config)
    config["lesion"]["offset"] = 0  # offset=0 は ident と同じ退化をする
    with pytest.raises(DegenerateReferenceRuleError):
        dry_run(config)


def test_unimplemented_battery_is_refused(smoke_config: dict[str, Any]) -> None:
    """未実装の群を要求されたら黙って空を返さない。"""
    config = copy.deepcopy(smoke_config)
    config["eval"]["batteries"] = ["t2"]
    with pytest.raises(ConfigError, match="未実装"):
        dry_run(config)


def test_real_run_is_not_implemented() -> None:
    """--dry-run なしの本実行は未実装。既定のモデル名をここで作らない。"""
    with pytest.raises(NotImplementedError, match="未実装"):
        main(["--config", str(SMOKE_CONFIG)])


def test_both_task_types_are_wired(smoke_config: dict[str, Any]) -> None:
    """★T3 と T1b の両方のテンプレートが解決すること(ADR-026)。

    片方だけ英語化・改名すると、項目の category とテンプレート集合の
    キーが食い違い、KeyError ではなく parse_fail に化ける経路がある。
    """
    categories = {entry.get("category") for entry in smoke_config["eval"]["dry_run_items"]}
    assert {"t3_gt", "t3_lt", "t1b_gt", "t1b_lt"} <= categories
    prompts = dry_run(smoke_config)["by_batch"]["comparison"]["prompts"]
    assert any(prompt.startswith("Is ") for prompt in prompts)  # T3 は自然文
    assert any(prompt.startswith("5+6") for prompt in prompts)  # T1b は裸書式


# --------------------------------------------------------------------------
# 数値経路(A-5)
# --------------------------------------------------------------------------


def test_all_four_groups_are_wired(smoke_config: dict[str, Any]) -> None:
    """★4群すべてが --dry-run を通ること。

    答える問い: 「comparison / bare_sum / word_problem / specificity の
    どれかが黙って落ちていないか」
    """
    report = dry_run(smoke_config)
    assert set(report["by_batch"]) == EXPECTED_BATCHES
    assert sum(batch["n_items"] for batch in report["by_batch"].values()) == report["n_items"]


def test_numeric_path_reaches_all_four_categories(smoke_config: dict[str, Any]) -> None:
    """★数値経路が correct / rule / other_error / parse_fail の4つに到達すること。

    other_error は「p2 の規則値を返したモデルを x2 から見る」経路で出る。
    ここが 0 のままだと、4値のうち1つが**一度も通っていない**まま
    本実行に入ることになる。
    """
    blocks = dry_run(smoke_config)["by_batch"]["bare_sum"]["by_response"]
    assert blocks["truthful"]["by_reference_rule"]["p2"]["correct_rate"] == 1.0
    assert blocks["rule_following"]["by_reference_rule"]["p2"]["rule_rate"] == 1.0
    assert blocks["rule_following"]["by_reference_rule"]["x2"]["other_error_rate"] == 1.0
    assert blocks["unreadable"]["by_reference_rule"]["p2"]["parse_fail_rate"] == 1.0


def test_bare_sum_prompt_is_the_training_format(smoke_config: dict[str, Any]) -> None:
    """★T1 の文面は data.prompt_template から来ること(評価アンカー)。

    評価用テンプレート集合から引くと、アンカーが静かに訓練書式から離れ、
    PLAN-002 §4.8.1 検査6 が「訓練と評価で書式が違う」で止まる。
    smoke のテンプレート集合には bare_sum の群そのものが無いので、
    ここが集合を引き始めたら ConfigError になる。
    """
    template = smoke_config["data"]["prompt_template"]
    prompts = dry_run(smoke_config)["by_batch"]["bare_sum"]["prompts"]
    assert prompts == [
        template.format(a=entry["a"], b=entry["b"])
        for entry in smoke_config["eval"]["dry_run_items"]
        if entry["group"] == numeric_sum.GROUP_BARE_SUM
    ]


def test_smoke_covers_all_five_word_problem_templates(smoke_config: dict[str, Any]) -> None:
    """★T2 の5場面すべてが解決すること(ADR-032 決定5)。

    割当は (pool_id, a, b) のハッシュで決まるので config から選べない。
    5本のうち1本でも欠けると KeyError になる経路を、ここで固定する。
    """
    prompts = dry_run(smoke_config)["by_batch"]["word_problem"]["prompts"]
    assert len(set(prompts)) == len(numeric_sum.T2_CATEGORIES)


def test_word_problem_entry_cannot_pin_the_template(smoke_config: dict[str, Any]) -> None:
    """★T2 の category を config から指定させない(PLAN-003 §4.3)。

    上書きできると、条件間・シード間で割当が一致するという保証が消え、
    統計モデルの (1 | template) が条件と交絡する。
    """
    config = copy.deepcopy(smoke_config)
    for entry in config["eval"]["dry_run_items"]:
        if entry["group"] == numeric_sum.GROUP_WORD_PROBLEM:
            entry["category"] = "t2_count"
            break
    with pytest.raises(ConfigError, match="category を書かない"):
        dry_run(config)


def test_specificity_is_scored_per_category(smoke_config: dict[str, Any]) -> None:
    """★減算と乗算は別バッチで採点されること(§4.6)。

    混ぜると rule_values のキーが揃わず scoring._shared_reference_rules が
    止める。**止まるのが正しい。**バッチを分けるのは採点側の責務である。
    """
    report = dry_run(smoke_config)
    for category in specificity_control.CATEGORIES:
        batch = report["by_batch"][category]
        assert batch["group"] == specificity_control.GROUP
        assert batch["reference_rule"] == category
        rules = batch["by_response"]["truthful"]["by_reference_rule"]
        assert set(rules) == {category}


def test_specificity_truth_is_not_the_sum(smoke_config: dict[str, Any]) -> None:
    """★特異性対照の真値は a + b ではないこと(§4.6)。

    加算の参照規則を減算・乗算の項目に突き合わせると rule_rate が無意味になる。
    `7-3=` に 10(= 7+3)を返すモデルが correct にならないことを固定する。
    """
    report = dry_run(smoke_config)
    assert report["by_batch"]["spec_sub"]["prompts"] == ["7-3=", "9-2="]
    assert report["by_batch"]["spec_mul"]["prompts"] == ["3*4=", "5*3="]
    # 真値を返す固定応答が correct なのだから、真値は a−b / a×b である
    for category in specificity_control.CATEGORIES:
        block = report["by_batch"][category]["by_response"]["truthful"]
        assert block["by_reference_rule"][category]["correct_rate"] == 1.0


def test_dry_run_item_needs_an_explicit_group(smoke_config: dict[str, Any]) -> None:
    """★群を書かない項目は黙って捨てずに止める。

    捨てると項目数が静かに減り、セルの件数が条件間でずれる(PLAN-001 §3)。
    """
    config = copy.deepcopy(smoke_config)
    del config["eval"]["dry_run_items"][0]["group"]
    with pytest.raises(ConfigError, match="eval.batteries"):
        dry_run(config)


def test_dry_run_item_outside_the_batteries_is_refused(smoke_config: dict[str, Any]) -> None:
    """★eval.batteries に無い群の項目があったら止める。"""
    config = copy.deepcopy(smoke_config)
    config["eval"]["batteries"] = ["comparison"]
    with pytest.raises(ConfigError, match="eval.batteries"):
        dry_run(config)


# --------------------------------------------------------------------------
# parse_numeric_response(§5.5)
# --------------------------------------------------------------------------


def test_parse_numeric_response_direct() -> None:
    """direct は numeric.parse だけを通ること。"""
    assert parse_numeric_response("Answer: 320.", "direct") == 320
    assert parse_numeric_response("320", "direct") == 320
    assert parse_numeric_response("-3", "direct") == -3


def test_parse_numeric_response_cot_cuts_before_parsing() -> None:
    """★cot は「切り出し → 数値化」の2段であること(PLAN-001 §5.4 の 2)。

    途中計算の数が並ぶ出力を切らずに渡すと、数が複数見つかって
    全項目が parse_fail に落ちる。切り出しは cot.py の責務であり、
    ここが数値化を先に行うと CoT のときだけ規則が変わっていても気づけない。

    印の集合が2段で違うことも同時に固定する。`therefore` は cot.py の
    CONCLUSION_MARKERS にはあるが base.ANSWER_MARKERS には無い(推論の
    接続詞は direct 応答には現れないため)。よって同じ出力が
    direct では parse_fail に、cot では 320 になる。
    """
    text = "150 + 170 is 320.\nTherefore 320"
    assert parse_numeric_response(text, "cot") == 320
    assert parse_numeric_response(text, "direct") is None
    # 答え書式の指示(ADR-032 決定3)に従った出力は、どちらでも同じ値になる
    assert parse_numeric_response("Answer: 320.", "cot") == 320
    assert parse_numeric_response("Answer: 320.", "direct") == 320


def test_parse_numeric_response_does_not_take_the_last_number() -> None:
    """★「数が2個以上なら parse_fail」を緩めないこと(PLAN-001 §5.4 の 4)。

    緩めると parse_fail_rate は下がるが、その分だけ誤りが correct / rule に
    流れ込む。文章題の復唱を通すのは ADR-032 決定3 の答え書式の指示の役目。
    """
    assert parse_numeric_response("There are 150 and 170 apples.", "cot") is None
    assert parse_numeric_response("I cannot say.", "cot") is None
    assert parse_numeric_response("", "cot") is None


def test_parse_numeric_response_refuses_unknown_elicitation() -> None:
    """未知の引き出し方で黙って None を返さない(parse_fail に化ける)。"""
    with pytest.raises(ConfigError, match="eval.elicitation"):
        parse_numeric_response("7", "chain-of-thought")


def test_cot_elicitation_gives_the_same_numeric_breakdown(smoke_config: dict[str, Any]) -> None:
    """★cot に切り替えても数値バッチの4値分解が変わらないこと。

    固定応答は答え書式の指示に従った形(`Answer: <number>`)なので、
    direct と cot で結果が一致するのが正しい。ここが割れたら、
    cot 経路の切り出しが答えの数まで削っている。
    """
    config = copy.deepcopy(smoke_config)
    config["eval"]["elicitation"] = "cot"
    direct = dry_run(smoke_config)["by_batch"]
    cot = dry_run(config)["by_batch"]
    for name in EXPECTED_BATCHES - {"comparison"}:
        assert cot[name]["by_response"] == direct[name]["by_response"], name
