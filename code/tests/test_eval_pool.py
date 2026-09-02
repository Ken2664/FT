"""評価プールを書き出す入口(`code/data_gen/eval_pool.py`)。PLAN-001 §4、ADR-033。

答える問い: 「評価プールの manifest は、preflight が照合できる形で書けているか」

ここで固定する最重要の性質:
  - **`reference_rules` と `specificity_reference_rules` が分かれている**
    (ADR-033 決定1・2)。混ざると `eval.reference_rule: spec_sub` を主軸の
    バッチに誤指定しても `scoring.validate_reference_rule` が素通しする
  - **`fill` が「サンプリングしていない」ことを記録する**(決定3)。
    無いと `seed` の欄だけが残り、埋め方が未決である事実が manifest から消える
  - **書き出した manifest で preflight の検査6・8 が PASS になる**(A-6 の完了条件)
  - **`eval.pool_items` と `eval.dry_run_items` が同じ項目集合を作る。**
    ずれると「dry-run で通る項目」と「プールに入る項目」が別物になる

FT データの manifest は tmp_path に**実際に生成して**使う。repo に
コミット済みの生成物に依存させると、再生成のたびにテストが壊れる。
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import preflight
import pytest
import yaml

from code.config import ConfigError
from code.data_gen import eval_pool, prompt_format
from code.data_gen.battery_items import read_items
from code.data_gen.ft_data import generate, write_dataset
from code.eval.run import build_dry_run_items, dry_run_entries_by_group
from code.lesion import (
    reference_lesions_from_config,
    specificity_reference_lesions_from_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# smoke の lesion ブロックから組み立てられる条件。**5条件ではない。**
# digit_modulus / arbitrary_table を持たないので p2d / arb は作れない
# (ADR-033 リスク欄)。smoke は配線確認であって実験ではない。
SMOKE_CONDITIONS = ("p2", "x2", "ident")


@pytest.fixture
def smoke_config() -> dict[str, Any]:
    return yaml.safe_load(SMOKE_CONFIG.read_text(encoding="utf-8"))


@pytest.fixture
def config_with_ft_data(smoke_config: dict[str, Any], tmp_path: Path) -> dict[str, Any]:
    """FT データを tmp_path に生成し、そこを指す config を返す。

    評価プールは FT データの**後**に作る(ADR-017 案A)。被覆和は訓練側が
    1度だけ畳んだ値を転記する(ADR-021 決定5)ので、先に生成が要る。
    """
    config = copy.deepcopy(smoke_config)
    declared = []
    for condition in SMOKE_CONDITIONS:
        per_condition = copy.deepcopy(smoke_config)
        per_condition["lesion"]["condition"] = condition
        out_dir = tmp_path / condition
        write_dataset(generate(per_condition), out_dir)
        declared.append(str(out_dir / "manifest.json"))
    config["data"]["matched_manifests"] = declared
    return config


# --------------------------------------------------------------------------
# 参照規則の2欄(ADR-033 決定1・2)
# --------------------------------------------------------------------------


def test_specificity_rules_are_not_mixed_into_reference_rules(
    config_with_ft_data: dict[str, Any],
) -> None:
    """★`spec_sub` / `spec_mul` を `reference_rules` に混ぜない(ADR-033 決定1)。

    あの欄は「`pool.eligible_pairs` に渡した規則」の記録である。混ぜると
    `eval.reference_rule: spec_sub` を主軸のバッチに誤指定しても
    `scoring.validate_reference_rule` が止められなくなる。
    """
    manifest = eval_pool.build(config_with_ft_data).manifest
    assert manifest["reference_rules"] == sorted(
        reference_lesions_from_config(config_with_ft_data)
    )
    assert "spec_sub" not in manifest["reference_rules"]
    assert "spec_mul" not in manifest["reference_rules"]


def test_specificity_rules_are_recorded_in_their_own_field(
    config_with_ft_data: dict[str, Any],
) -> None:
    """★特異性対照の参照規則は別欄に残る(ADR-033 決定2)。

    記録しない案を却下したのは、ADR-016 のガードが manipulation check に
    効かなくなるためである。
    """
    manifest = eval_pool.build(config_with_ft_data).manifest
    assert manifest["specificity_reference_rules"] == sorted(
        specificity_reference_lesions_from_config(config_with_ft_data)
    )
    assert manifest["specificity_reference_rules"] == ["spec_mul", "spec_sub"]


# --------------------------------------------------------------------------
# 充填の記録(ADR-033 決定3・4)
# --------------------------------------------------------------------------


def test_fill_records_that_the_pool_was_not_sampled(
    config_with_ft_data: dict[str, Any],
) -> None:
    """★埋め方が未決であることを manifest 自身に残す(ADR-033 決定3)。

    `fill` が無いと `seed` の欄だけが残り、サンプリングされたプールに見える。
    """
    manifest = eval_pool.build(config_with_ft_data).manifest
    assert manifest["fill"]["method"] == eval_pool.FILL_EXPLICIT_LIST
    assert manifest["fill"]["seed_consumed"] is False
    assert manifest["seed"] == config_with_ft_data["eval"]["pool_seed"]


def test_declared_cells_are_transcribed_but_not_used_to_fill(
    config_with_ft_data: dict[str, Any],
) -> None:
    """`eval.cells` は宣言として転記されるだけである(ADR-033 決定4)。

    セル表どおりに埋まっているなら、項目数はセルの n の合計になるはずである。
    そうなっていないことを固定する —— **セル表は preflight の検査8 の入力**
    であって、このプールの構成ではない。
    """
    manifest = eval_pool.build(config_with_ft_data).manifest
    declared = manifest["fill"]["cells_declared"]
    assert [cell["name"] for cell in declared] == [
        cell["name"] for cell in config_with_ft_data["eval"]["cells"]
    ]
    assert len(eval_pool.build(config_with_ft_data).items) != sum(c["n"] for c in declared)


def test_cells_with_duplicate_names_are_refused(config_with_ft_data: dict[str, Any]) -> None:
    """セル名の重複は生成の時点で止める(preflight まで持ち越さない)。"""
    config = copy.deepcopy(config_with_ft_data)
    config["eval"]["cells"] = [
        {"name": "same", "coverage": "id", "carry": None, "n": 1},
        {"name": "same", "coverage": "interp", "carry": None, "n": 1},
    ]
    with pytest.raises(ConfigError, match="セル名が重複"):
        eval_pool.build(config)


def test_missing_cells_declaration_is_refused(config_with_ft_data: dict[str, Any]) -> None:
    """`eval.cells` が null なら止まる。既定値を作らない(skill code-style §5)。"""
    config = copy.deepcopy(config_with_ft_data)
    config["eval"]["cells"] = None
    with pytest.raises(ConfigError, match="eval.cells"):
        eval_pool.build(config)


# --------------------------------------------------------------------------
# 書式(PLAN-002 §4.8.1 検査6 の相手方)
# --------------------------------------------------------------------------


def test_prompt_format_comes_from_the_config(config_with_ft_data: dict[str, Any]) -> None:
    """★評価アンカーの書式は config から組む。既定値を作らない。

    ここが訓練側とずれると、preflight の検査6 が「訓練と評価で書式が違う」で
    止まる。違うのは書式ではなく実装である、という取り違えを防ぐ。
    """
    manifest = eval_pool.build(config_with_ft_data).manifest
    assert manifest["prompt_format"] == prompt_format.build_from_config(config_with_ft_data)


def test_undecided_prompt_template_stops_the_pool(config_with_ft_data: dict[str, Any]) -> None:
    """書式が未決(null)なら既定値を作らずに止まる。"""
    config = copy.deepcopy(config_with_ft_data)
    config["data"]["prompt_template"] = None
    with pytest.raises(ConfigError, match="data.prompt_template"):
        eval_pool.build(config)


# --------------------------------------------------------------------------
# T2 の被演算子の除外(ADR-032 決定4)
# --------------------------------------------------------------------------


def test_operand_exclusion_is_applied_to_every_group_and_recorded(
    config_with_ft_data: dict[str, Any],
) -> None:
    """★被演算子 1 の組は**どの群でも**項目にならず、内訳が manifest に残る。

    ADR-035 決定3 で、この除外は T2 限定(ADR-032 決定4)から全タスク型共通の
    項目規約に昇格した。**タスク型ごとに除外規則が違うと、被演算子分布が
    タスク型間で揃わず主軸の交互作用の解釈に穴が開く。**

    除外は**生成器に渡す前**に掛ける。後段で落とすと件数が静かに減り、
    条件間で項目集合が変わって項目ランダム効果が条件と交絡する。
    """
    config = copy.deepcopy(config_with_ft_data)
    config["eval"]["pool_items"] = [
        *config["eval"]["pool_items"],
        {"group": "word_problem", "a": 1, "b": 4},
        {"group": "bare_sum", "a": 1, "b": 5},
        {"group": "comparison", "a": 1, "b": 6, "category": "t3_gt", "threshold_offset": 0},
        {"group": "specificity", "a": 8, "b": 1, "category": "spec_sub"},
    ]
    pool = eval_pool.build(config)
    record = pool.manifest["item_exclusions"]
    assert record["scope"] == "pool"
    assert record["excluded_operands"] == [1]
    assert record["n_excluded"] == 4
    assert record["by_group"]["word_problem"]["n_excluded"] == 1
    assert record["by_group"]["bare_sum"]["n_excluded"] == 1
    assert record["by_group"]["comparison"]["n_excluded"] == 1
    assert record["by_group"]["specificity"]["n_excluded"] == 1
    operands = {item.operands for item in pool.items}
    assert not any(1 in pair for pair in operands)


# --------------------------------------------------------------------------
# `id` セルの母集団(ADR-034 リスク欄)★
# --------------------------------------------------------------------------


def test_the_manifest_records_where_the_id_cells_are_drawn_from(
    config_with_ft_data: dict[str, Any],
) -> None:
    """★★`id` セルの母集団が K そのものではないことを manifest に残す。

    ADR-034 リスク欄の「順4 の項目生成で明示する」。書かないと、`id` セルが
    `K` から一様に引かれているように読める。**本番経路が数えた値**を残す ——
    人間の手計算を転記すると、K の抽出が変わったときに静かにずれる。
    """
    pool = eval_pool.build(config_with_ft_data)
    record = pool.manifest["id_cell_population"]
    assert record["source"] == "coverage_k"
    names = [stage["name"] for stage in record["stages"]]
    assert names == [
        "coverage_k",
        "coincidence",
        "indistinguishable_rule_pairs",
        "excluded_operands",
    ]
    coverage_k = config_with_ft_data["data"]["coverage_k"]
    assert record["stages"][0]["n"] == coverage_k
    # 除外は単調に効く。最終段が母集団であり、K を超えない。
    assert [stage["n"] for stage in record["stages"]] == sorted(
        (stage["n"] for stage in record["stages"]), reverse=True
    )
    assert record["n_pairs"] == record["stages"][-1]["n"]
    assert record["n_pairs"] <= coverage_k


# --------------------------------------------------------------------------
# 指示付き T1(副次セル。ADR-035 決定2)★
# --------------------------------------------------------------------------


def test_the_instructed_sum_group_goes_through_the_pool(
    config_with_ft_data: dict[str, Any],
) -> None:
    """★副次セルが評価プールの経路を通る(SUPPORTED_GROUPS への追加。順4)。

    項目は T1 と同じ組から作られ、群と category だけが違う。
    """
    config = copy.deepcopy(config_with_ft_data)
    config["eval"]["batteries"] = [*config["eval"]["batteries"], "bare_sum_instructed"]
    config["data"]["answer_format_instruction"] = 'End your reply with "Answer: <number>".'
    config["eval"]["pool_items"] = [
        *config["eval"]["pool_items"],
        {"group": "bare_sum_instructed", "a": 3, "b": 4},
        {"group": "bare_sum_instructed", "a": 5, "b": 6},
    ]
    pool = eval_pool.build(config)
    instructed = [item for item in pool.items if item.group == "bare_sum_instructed"]
    bare = [item for item in pool.items if item.group == "bare_sum"]
    assert [item.operands for item in instructed] == [(3, 4), (5, 6)]
    assert {item.category for item in instructed} == {"t1_instructed"}
    # ★T1 と同一の被演算子対である(ADR-035 決定2)。
    assert {item.operands for item in instructed} == {item.operands for item in bare}
    assert pool.manifest["fill"]["n_items_by_group"]["bare_sum_instructed"] == 2


def test_the_instructed_sum_group_refuses_an_explicit_category(
    config_with_ft_data: dict[str, Any],
) -> None:
    """★表層は1種類しかない。config から category を上書きさせない。"""
    config = copy.deepcopy(config_with_ft_data)
    config["eval"]["batteries"] = [*config["eval"]["batteries"], "bare_sum_instructed"]
    config["eval"]["pool_items"] = [
        *config["eval"]["pool_items"],
        {"group": "bare_sum_instructed", "a": 3, "b": 4, "category": "t1"},
    ]
    with pytest.raises(ConfigError, match="category"):
        eval_pool.build(config)


# --------------------------------------------------------------------------
# 外挿域(PLAN-001 §4.1.1、承認待ち-15)
# --------------------------------------------------------------------------


def test_pairs_outside_the_main_domain_are_refused_while_m_star_is_undecided(
    config_with_ft_data: dict[str, Any],
) -> None:
    """★M* が未決のまま主域の外の組をプールに入れない。

    後から M* が確定すると「その組が外挿域に入るか」が変わり、被覆ラベルが
    遡って動く。
    """
    config = copy.deepcopy(config_with_ft_data)
    config["eval"]["pool_items"] = [
        *config["eval"]["pool_items"],
        {"group": "bare_sum", "a": 40, "b": 3},
    ]
    assert config["eval"]["extrapolation_radius"] is None
    with pytest.raises(ConfigError, match="extrapolation_radius"):
        eval_pool.build(config)


# --------------------------------------------------------------------------
# プール名(PLAN-003 §4.3)
# --------------------------------------------------------------------------


def test_items_carry_the_configured_pool_id(config_with_ft_data: dict[str, Any]) -> None:
    """項目の pool_id は data.pool_id である。

    `item_id` にも T2 の場面テンプレートの割当にも効くので、manifest の
    pool_id と項目の pool_id がずれると割当の再現ができなくなる。
    """
    pool = eval_pool.build(config_with_ft_data)
    expected = config_with_ft_data["data"]["pool_id"]
    assert pool.manifest["pool_id"] == expected
    assert {item.pool_id for item in pool.items} == {expected}


def test_per_item_pool_id_is_refused(config_with_ft_data: dict[str, Any]) -> None:
    """項目ごとに pool_id を書かせない(1プール1名)。"""
    config = copy.deepcopy(config_with_ft_data)
    config["eval"]["pool_items"] = [{"group": "bare_sum", "a": 3, "b": 4, "pool_id": "other"}]
    config["eval"]["batteries"] = ["bare_sum"]
    with pytest.raises(ConfigError, match="pool_id"):
        eval_pool.build(config)


def test_word_problems_cover_all_five_scenes(config_with_ft_data: dict[str, Any]) -> None:
    """smoke の5組は5場面に1つずつ落ちる(テンプレート集合の配線確認)。

    割当は `(pool_id, a, b)` の sha256 なので、pool_id が変わると崩れる。
    崩れたまま気づかないと、5テンプレートのうち一部が1度も描画されない。
    """
    pool = eval_pool.build(config_with_ft_data)
    scenes = {item.category for item in pool.items if item.group == "word_problem"}
    assert len(scenes) == 5


# --------------------------------------------------------------------------
# 明示リストの一致(configs/smoke.yaml の YAML アンカー)
# --------------------------------------------------------------------------


def test_pool_items_and_dry_run_items_build_the_same_items(
    config_with_ft_data: dict[str, Any],
) -> None:
    """★プールに入る項目と dry-run が通す項目が同じであること。

    2本のリストに分けると静かにずれる。smoke.yaml は YAML アンカーで
    1本にしてあるので、ここが割れたらアンカーが外れている。
    """
    config = config_with_ft_data
    pool_ids = sorted(item.item_id for item in eval_pool.build(config).items)
    lesions = reference_lesions_from_config(config)
    specificity_lesions = specificity_reference_lesions_from_config(config)
    entries = dry_run_entries_by_group(config)
    dry_run_ids = sorted(
        item.item_id
        for group, group_entries in entries.items()
        for item in build_dry_run_items(
            group_entries,
            group,
            pool_id=config["data"]["pool_id"],
            lesions=lesions,
            specificity_lesions=specificity_lesions,
        )
    )
    assert pool_ids == dry_run_ids


# --------------------------------------------------------------------------
# 書き出しと preflight(A-6 の完了条件)
# --------------------------------------------------------------------------


def test_written_pool_round_trips(config_with_ft_data: dict[str, Any], tmp_path: Path) -> None:
    """items.jsonl と manifest.json を書き、読み戻せること。"""
    pool = eval_pool.build(config_with_ft_data)
    out_dir = tmp_path / "battery"
    eval_pool.write_pool(pool, out_dir)
    assert [item.item_id for item in read_items(out_dir / "items.jsonl")] == [
        item.item_id for item in pool.items
    ]
    written = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert written["pairs_hash"] == pool.manifest["pairs_hash"]


def test_written_pool_manifest_records_the_bytes_on_disk(
    config_with_ft_data: dict[str, Any], tmp_path: Path
) -> None:
    """★ADR-051。評価側も訓練側と同じ形の `files` ブロックを持つ。

    答える問い: 「items.jsonl の同一性を後から照合できるか」

    2026-09-02 まで評価側 manifest には items.jsonl のハッシュが1つも
    残っていなかった。`pairs_hash` は順序対の列であって書き出したファイルではない。
    """
    pool = eval_pool.build(config_with_ft_data)
    out_dir = tmp_path / "battery"
    eval_pool.write_pool(pool, out_dir)
    written = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert list(written["files"]) == ["items.jsonl"]
    expected = hashlib.sha256((out_dir / "items.jsonl").read_bytes()).hexdigest()
    assert written["files"]["items.jsonl"] == expected


def test_preflight_format_hash_and_coverage_floor_pass_on_the_written_pool(
    config_with_ft_data: dict[str, Any], tmp_path: Path
) -> None:
    """★A-6 の完了条件。書き出した manifest で検査6・8 が PASS になる。

    検査6 は評価アンカーの `format_hash` を訓練側の全条件と照合し、
    検査8 は `eval.cells` の id セルの n の合計を K の下限として数える。
    どちらも A-6 の前は「アンカーが無い」「セル定義が無い」で FAIL だった。
    """
    config = copy.deepcopy(config_with_ft_data)
    out_dir = tmp_path / "battery"
    eval_pool.write_pool(eval_pool.build(config), out_dir)
    config["eval"]["anchor_manifest"] = str(out_dir / "manifest.json")

    results = {result.name: result for result in preflight.data_checks(config)}
    assert results["format hash"].status is preflight.Status.PASS, results["format hash"].detail
    assert results["coverage_k floor"].status is preflight.Status.PASS, results[
        "coverage_k floor"
    ].detail


def test_the_repo_config_points_at_a_pool_whose_format_matches_training() -> None:
    """★`configs/smoke.yaml` がコミット済みの成果物と整合していること。

    `eval.anchor_manifest` が指す manifest の `format_hash` が config から
    組み直した書式と一致しなければ、記録が古い(生成し直しが要る)。
    """
    config = yaml.safe_load(SMOKE_CONFIG.read_text(encoding="utf-8"))
    anchor = json.loads(
        (REPO_ROOT / config["eval"]["anchor_manifest"]).read_text(encoding="utf-8")
    )
    assert anchor["prompt_format"] == prompt_format.build_from_config(config)
    assert anchor["fill"]["method"] == eval_pool.FILL_EXPLICIT_LIST


def test_condition_without_a_matched_manifest_is_refused(
    config_with_ft_data: dict[str, Any],
) -> None:
    """この実行の条件の FT manifest が無ければ、被覆和の出どころが決まらない。"""
    config = copy.deepcopy(config_with_ft_data)
    config["lesion"]["condition"] = "arb"
    with pytest.raises(ConfigError, match="matched_manifests"):
        eval_pool.build(config)
