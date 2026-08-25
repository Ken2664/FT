"""preflight の manifest 照合(PLAN-002 §4.8.1 の検査3拡張・5・6・8・9・10)。

答える問い: 「本実行を止めるべき状態を、preflight は実際に止められるか」

ここで固定する最重要の性質:
  - **検査9**: `t_holdout.sums_hash` が全条件で一致し、かつ §4.2.1a の構成から
    再現できる(ADR-029 決定3)。ハッシュの一致だけでは「全条件で同じように
    ずれている」場合を見逃すので、再現照合まで含めて固定する
  - **検査10**: `K` の和集合が `T_hold` と交わらない(ADR-029 決定1)。
    漏れたら `interp × t_unseen` が成立しない
  - **SKIP と FAIL を混ぜない**。対象が存在しないのが SKIP、確認できなかったのが
    FAIL である。環境に無いことを理由に検査が緩まないことをテストで縛る

manifest はハードコードせず `ft_data.generate` で実際に作る。schema を手で
書き写すと、生成器が変わったときにテストだけが古い schema を守り続ける。
"""

from __future__ import annotations

import copy
import json
import sys
import types
from pathlib import Path
from typing import Any

import preflight
import pytest

from code.data_gen.ft_data import canonical_json, generate, sha256_text, write_dataset

# 5条件(PLAN-002 §3.3)。none はデータを生成しない。
CONDITIONS = ("p2", "p2d", "x2", "arb", "ident")

# 小さく速い設定。**実験の条件ではない。**経路と不変条件の検査だけに使う
# (本実験の値は configs/template.yaml と PLAN-002 §4.2)。
SMALL_CONFIG: dict[str, Any] = {
    "experiment": {"id": "test_preflight"},
    "lesion": {
        "condition": "p2",
        "offset": 2,
        "multiplier": 2,
        "digit_modulus": 10,
        # 制約2(>= t + 2)だけ満たす最小の表(PLAN-002 §7.3)。ズレ表そのものではない。
        "arbitrary_table": {total: total + 3 for total in range(2, 19)},
    },
    "train": {"scope": "bare"},
    "data": {
        "train_domain_min": 1,
        "train_domain_max": 9,
        "pilot_train_region_size": 40,
        "t_holdout_size": 4,
        "coverage_k": 20,
        "train_size": 40,
        "pool_id": "main",
        "pool_split_seed": 20260822,
        "coverage_seed": 20260823,
        "sample_seed": 20260824,
        "prompt_template": "{a}+{b}=",
        "completion_template": "{target}",
        "chat_template": True,
    },
}


def _manifest_for(condition: str) -> dict[str, Any]:
    """1条件の manifest を実際に生成して返す。**condition 以外は動かさない。**"""
    config = copy.deepcopy(SMALL_CONFIG)
    config["lesion"]["condition"] = condition
    return generate(config).manifest


@pytest.fixture(scope="module")
def manifests() -> dict[str, dict[str, Any]]:
    """5条件の manifest。生成は決定的なのでモジュール内で使い回す。"""
    return {condition: _manifest_for(condition) for condition in CONDITIONS}


@pytest.fixture
def mutable(manifests: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """壊して落ちることを見るための複製。共有 fixture を汚さない。"""
    return copy.deepcopy(manifests)


# --------------------------------------------------------------------------
# 検査9: t_holdout(ADR-029 決定3)
# --------------------------------------------------------------------------


def test_t_holdout_is_identical_across_conditions(
    manifests: dict[str, dict[str, Any]],
) -> None:
    """検査9。T_hold は全病変条件・全実験シードで同一でなければならない。"""
    result = preflight.check_t_holdout(manifests)
    assert result.status is preflight.Status.PASS, result.detail
    hashes = {m["t_holdout"]["sums_hash"] for m in manifests.values()}
    assert len(hashes) == 1


def test_t_holdout_fails_when_one_condition_holds_out_different_sums(
    mutable: dict[str, dict[str, Any]],
) -> None:
    """検査9。条件ごとに T_hold が違えば t_seen / t_unseen の意味が条件で変わる。"""
    holdout = mutable["x2"]["t_holdout"]
    holdout["sums"] = [total + 1 for total in holdout["sums"]]
    result = preflight.check_t_holdout(mutable)
    assert result.status is preflight.Status.FAIL
    assert "x2" in result.detail


def test_t_holdout_fails_when_sums_are_not_the_deterministic_construction(
    mutable: dict[str, dict[str, Any]],
) -> None:
    """検査9。**全条件が同じようにずれている**場合も落とす。

    sums_hash の一致だけを見ると通ってしまう経路。§4.2.1a の構成から
    再現して照合しているかを縛る。
    """
    tampered = [2, 3, 4, 5]
    for manifest in mutable.values():
        manifest["t_holdout"]["sums"] = list(tampered)
        manifest["t_holdout"]["sums_hash"] = sha256_text(canonical_json(tampered))
    result = preflight.check_t_holdout(mutable)
    assert result.status is preflight.Status.FAIL
    assert "§4.2.1a" in result.detail


def test_t_holdout_fails_when_recorded_hash_does_not_match_recorded_sums(
    mutable: dict[str, dict[str, Any]],
) -> None:
    """検査9。sums_hash が sums から計算されていないなら記録が嘘である。"""
    for manifest in mutable.values():
        manifest["t_holdout"]["sums_hash"] = "0" * 64
    result = preflight.check_t_holdout(mutable)
    assert result.status is preflight.Status.FAIL
    assert "sums_hash" in result.detail


def test_t_holdout_fails_when_sums_are_not_ascending(
    mutable: dict[str, dict[str, Any]],
) -> None:
    """§4.8「sums は必ず昇順で書く」。"""
    for manifest in mutable.values():
        manifest["t_holdout"]["sums"] = list(reversed(manifest["t_holdout"]["sums"]))
    result = preflight.check_t_holdout(mutable)
    assert result.status is preflight.Status.FAIL
    assert "昇順" in result.detail


# --------------------------------------------------------------------------
# 検査10: K と T_hold の非交差(ADR-029 決定1)
# --------------------------------------------------------------------------


def test_coverage_sums_do_not_intersect_the_holdout(
    manifests: dict[str, dict[str, Any]],
) -> None:
    """検査10。ホールドアウトが訓練被覆に漏れていないか。"""
    result = preflight.check_holdout_leak(manifests)
    assert result.status is preflight.Status.PASS, result.detail


def test_holdout_leak_is_detected_when_a_held_out_sum_enters_k(
    mutable: dict[str, dict[str, Any]],
) -> None:
    """検査10。T_hold の和を持つ組を K に混ぜたら止まること。"""
    manifest = mutable["p2"]
    leaked_sum = manifest["t_holdout"]["sums"][0]
    # 和が leaked_sum になる組を1つ作って K に足す。値域は [1,9]^2(SMALL_CONFIG)。
    a = 1
    b = leaked_sum - a
    manifest["coverage"]["pairs"].append([a, b])
    manifest["coverage"]["coverage_sums"] = sorted(
        {pair[0] + pair[1] for pair in manifest["coverage"]["pairs"]}
    )
    result = preflight.check_holdout_leak(mutable)
    assert result.status is preflight.Status.FAIL
    assert "漏れている" in result.detail


def test_holdout_leak_detects_coverage_sums_that_disagree_with_pairs(
    mutable: dict[str, dict[str, Any]],
) -> None:
    """検査10。coverage_sums は t_seen / t_unseen の判定に使われる記録である。

    pairs と食い違っていたら、ラベルそのものが嘘になる。
    """
    mutable["p2"]["coverage"]["coverage_sums"] = []
    result = preflight.check_holdout_leak(mutable)
    assert result.status is preflight.Status.FAIL
    assert "coverage_sums" in result.detail


# --------------------------------------------------------------------------
# 検査5: matched_stream_sha256(§3.4)
# --------------------------------------------------------------------------


def test_matched_stream_agrees_across_the_five_conditions(
    manifests: dict[str, dict[str, Any]],
) -> None:
    """検査5。条件間の差は target だけでなければならない。"""
    result = preflight.check_matched_stream(manifests)
    assert result.status is preflight.Status.PASS, result.detail


def test_matched_stream_fails_when_one_condition_diverges(
    mutable: dict[str, dict[str, Any]],
) -> None:
    result = preflight.check_matched_stream(mutable)
    assert result.status is preflight.Status.PASS
    mutable["arb"]["outputs"]["matched_stream_sha256"] = "f" * 64
    assert preflight.check_matched_stream(mutable).status is preflight.Status.FAIL


def test_matched_stream_reports_the_premise_before_the_hash(
    mutable: dict[str, dict[str, Any]],
) -> None:
    """§3.4 のタプルが違えばハッシュが違うのは当たり前。中身が別問題になる。"""
    mutable["p2d"]["coverage"]["coverage_seed"] = 999
    result = preflight.check_matched_stream(mutable)
    assert result.status is preflight.Status.FAIL
    assert "前提" in result.detail


def test_matched_stream_fails_when_there_is_nothing_to_compare(
    manifests: dict[str, dict[str, Any]],
) -> None:
    """条件が1つだけの照合を PASS と報告しない(実態より軽い申告をしない)。"""
    result = preflight.check_matched_stream({"p2": manifests["p2"]})
    assert result.status is preflight.Status.FAIL


# --------------------------------------------------------------------------
# 検査6: format_hash(§4.1、§5.2)
# --------------------------------------------------------------------------


def test_format_hash_agrees_with_the_evaluation_anchor(
    manifests: dict[str, dict[str, Any]],
) -> None:
    """検査6。書式は実験条件であり、訓練と評価アンカーで一致する必要がある。"""
    anchor = {"prompt_format": copy.deepcopy(manifests["p2"]["prompt_format"])}
    result = preflight.check_format_hash(manifests, anchor)
    assert result.status is preflight.Status.PASS, result.detail


def test_format_hash_fails_when_the_anchor_uses_another_format(
    manifests: dict[str, dict[str, Any]],
) -> None:
    anchor = {"prompt_format": copy.deepcopy(manifests["p2"]["prompt_format"])}
    anchor["prompt_format"]["format_hash"] = "a" * 64
    result = preflight.check_format_hash(manifests, anchor)
    assert result.status is preflight.Status.FAIL
    assert "アンカー" in result.detail


def test_format_hash_detects_a_stale_record(
    mutable: dict[str, dict[str, Any]],
) -> None:
    """prompt_format を手で書き換えても format_hash は追随しない。"""
    anchor = {"prompt_format": copy.deepcopy(mutable["p2"]["prompt_format"])}
    mutable["x2"]["prompt_format"]["whitespace"] = "single"
    result = preflight.check_format_hash(mutable, anchor)
    assert result.status is preflight.Status.FAIL
    assert "記録が古い" in result.detail


# --------------------------------------------------------------------------
# 検査8: coverage_k の下限(PLAN-001 §4.2.2)
# --------------------------------------------------------------------------


def test_coverage_k_floor_counts_the_id_cell_demand_at_runtime(
    manifests: dict[str, dict[str, Any]],
) -> None:
    """検査8。**リテラルの閾値を置かない。**要求は eval.cells から数える。"""
    cells = [
        {"name": "t1_id_carry", "coverage": "id", "carry": "carry", "n": 8},
        {"name": "t1_id_nocarry", "coverage": "id", "carry": "nocarry", "n": 8},
        {"name": "t1_interp", "coverage": "interp", "carry": None, "n": 40},
    ]
    result = preflight.check_coverage_k_floor(manifests, cells)
    assert result.status is preflight.Status.PASS
    assert "16" in result.detail


def test_coverage_k_floor_fails_when_the_pool_needs_more_pairs_than_k(
    manifests: dict[str, dict[str, Any]],
) -> None:
    """fill_cells はセル間で組を再利用しない(ADR-017)ので合計がそのまま下限。"""
    cells = [{"name": "id_all", "coverage": "id", "carry": None, "n": 21}]
    result = preflight.check_coverage_k_floor(manifests, cells)
    assert result.status is preflight.Status.FAIL
    assert "id 要求 21" in result.detail


def test_coverage_k_floor_fails_when_no_id_cell_is_declared(
    manifests: dict[str, dict[str, Any]],
) -> None:
    """要求 0 を「満たしている」と報告しない。数えられないのは未実行である。"""
    cells = [{"name": "interp_all", "coverage": "interp", "carry": None, "n": 40}]
    result = preflight.check_coverage_k_floor(manifests, cells)
    assert result.status is preflight.Status.FAIL


# --------------------------------------------------------------------------
# 検査3の拡張: pilot / main 領域(§4.7、PLAN-001 §4.6)
# --------------------------------------------------------------------------


def test_pool_regions_are_reproducible_from_the_manifest(
    manifests: dict[str, dict[str, Any]],
) -> None:
    """検査3拡張。counterpart_region_hash を分割パラメータから再現して照合する。"""
    result = preflight.check_pool_regions(manifests)
    assert result.status is preflight.Status.PASS, result.detail


def test_pool_regions_fail_when_the_counterpart_hash_does_not_reproduce(
    mutable: dict[str, dict[str, Any]],
) -> None:
    mutable["p2"]["pool_split"]["counterpart_region_hash"] = "b" * 64
    result = preflight.check_pool_regions(mutable)
    assert result.status is preflight.Status.FAIL
    assert "counterpart_region_hash" in result.detail


def test_pool_regions_fail_when_k_is_drawn_from_outside_its_own_region(
    mutable: dict[str, dict[str, Any]],
) -> None:
    """パイロット領域の組が本実験の被覆に混ざると、選択のバイアスが本実験に入る。"""
    ft_data, pool = preflight._repo_modules()
    manifest = mutable["p2"]
    split = manifest["pool_split"]
    regions = pool.split_pilot_main(
        ft_data.train_domain_pairs(manifest["train_domain"]["lo"], manifest["train_domain"]["hi"]),
        split["pilot_train_region_size"],
        split["pool_split_seed"],
    )
    intruder = regions[split["counterpart_pool_id"]][0]
    manifest["coverage"]["pairs"].append(list(intruder))
    result = preflight.check_pool_regions(mutable)
    assert result.status is preflight.Status.FAIL
    assert "領域の外" in result.detail


def test_pool_regions_detect_overlap_between_pilot_and_main_coverage() -> None:
    """K_pilot ∩ K_main = ∅(PLAN-001 §4.6)。pool_id が違う manifest 同士で見る。"""
    main = _manifest_for("p2")
    pilot_config = copy.deepcopy(SMALL_CONFIG)
    pilot_config["data"]["pool_id"] = "pilot"
    pilot = generate(pilot_config).manifest
    # 素の状態では交わらない。
    assert preflight._cross_pool_overlaps({"main": main, "pilot": pilot}) == []
    pilot["coverage"]["pairs"].append(list(main["coverage"]["pairs"][0]))
    assert preflight._cross_pool_overlaps({"main": main, "pilot": pilot}) != []


# --------------------------------------------------------------------------
# SKIP と FAIL の切り分け(§4.8.1 の方針)
# --------------------------------------------------------------------------


def test_no_config_skips_the_manifest_checks() -> None:
    """config を渡さない実行は環境検査だけを行う(既存の契約)。"""
    results = preflight.data_checks({})
    assert {r.status for r in results} == {preflight.Status.SKIP}
    assert {r.name for r in results} == set(preflight.DATA_CHECK_NAMES)


def test_condition_none_skips_the_manifest_checks() -> None:
    """none は FT データを生成しない(§3.4)ので、照合の対象が存在しない。"""
    config = {"lesion": {"condition": preflight.LESION_CONDITION_NONE}}
    results = preflight.data_checks(config)
    assert {r.status for r in results} == {preflight.Status.SKIP}


def test_missing_declaration_fails_instead_of_skipping() -> None:
    """**環境に無いことを PASS / SKIP にしない。**宣言の欠落は FAIL である。"""
    config = {"lesion": {"condition": "p2"}, "data": {"matched_manifests": None}}
    results = preflight.data_checks(config)
    assert {r.status for r in results} == {preflight.Status.FAIL}
    assert all("matched_manifests" in r.detail for r in results)


def test_a_declared_manifest_that_does_not_exist_fails(tmp_path: Path) -> None:
    config = {
        "lesion": {"condition": "p2"},
        "data": {"matched_manifests": [str(tmp_path / "missing.json")]},
    }
    results = preflight.data_checks(config)
    assert {r.status for r in results} == {preflight.Status.FAIL}


def test_the_running_condition_must_appear_among_the_declared_manifests(
    tmp_path: Path,
    manifests: dict[str, dict[str, Any]],
) -> None:
    """自分の条件の manifest を照合の対象から外して通すことを許さない。"""
    path = tmp_path / "p2.json"
    path.write_text(json.dumps(manifests["p2"]), encoding="utf-8")
    config = {"lesion": {"condition": "x2"}, "data": {"matched_manifests": [str(path)]}}
    with pytest.raises(preflight.ManifestUnavailable) as caught:
        preflight.load_ft_manifests(config)
    assert caught.value.status is preflight.Status.FAIL


def test_manifests_missing_schema_keys_fail(tmp_path: Path) -> None:
    """PLAN-002 §4.8 の schema を満たさない manifest を黙って通さない。"""
    path = tmp_path / "broken.json"
    path.write_text(json.dumps({"lesion": {"condition": "p2"}}), encoding="utf-8")
    config = {"lesion": {"condition": "p2"}, "data": {"matched_manifests": [str(path)]}}
    with pytest.raises(preflight.ManifestUnavailable) as caught:
        preflight.load_ft_manifests(config)
    assert caught.value.status is preflight.Status.FAIL


def test_end_to_end_data_checks_pass_on_generated_manifests(
    tmp_path: Path,
    manifests: dict[str, dict[str, Any]],
) -> None:
    """実際にディスクへ書いた5条件の manifest で §4.8.1 の検査が通ること。"""
    declared = []
    for condition in CONDITIONS:
        out_dir = tmp_path / condition
        config = copy.deepcopy(SMALL_CONFIG)
        config["lesion"]["condition"] = condition
        write_dataset(generate(config), out_dir)
        declared.append(str(out_dir / "manifest.json"))
    anchor_path = tmp_path / "anchor.json"
    anchor_path.write_text(
        json.dumps({"prompt_format": manifests["p2"]["prompt_format"]}), encoding="utf-8"
    )
    config = {
        "lesion": {"condition": "p2"},
        "data": {"matched_manifests": declared},
        "eval": {
            "anchor_manifest": str(anchor_path),
            "cells": [{"name": "id_all", "coverage": "id", "carry": None, "n": 20}],
        },
    }
    results = preflight.data_checks(config)
    assert {r.status for r in results} == {preflight.Status.PASS}, [
        (r.name, r.detail) for r in results
    ]


# --------------------------------------------------------------------------
# 検査7: トークン境界(§4.1.5)
# --------------------------------------------------------------------------

# 検査7 に渡す最小の config。**実験条件ではない。**model.name は偽の
# トークナイザに差し替えて使うので、実在のモデルを指す必要がない。
_TOKEN_CONFIG: dict[str, Any] = {
    "model": {"name": "fake/tokenizer", "revision": "0" * 40},
    "data": {"prompt_template": "{a}+{b}=", "completion_template": "{target}"},
}



def test_token_boundaries_fail_when_the_model_is_not_pinned(tmp_path: Path) -> None:
    """ADR-031。revision が null のまま本実行に入らせない。"""
    config = {
        "model": {"name": "meta-llama/Llama-3.1-8B-Instruct", "revision": None},
        "data": {"prompt_template": "{a}+{b}=", "completion_template": "{target}"},
    }
    result = preflight.check_token_boundaries(config, tmp_path)
    assert result.status is preflight.Status.FAIL
    assert "model.revision" in result.detail


def test_token_boundaries_fail_when_transformers_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**依存が無い環境で PASS にしない。**未実行は FAIL として報告する。

    本物の transformers を import しない。ここで縛りたいのは preflight の
    分岐であって、ライブラリの挙動ではない(import に十数秒かかる)。
    """
    monkeypatch.setitem(sys.modules, "transformers", None)
    result = preflight.check_token_boundaries(_TOKEN_CONFIG, tmp_path)
    assert result.status is preflight.Status.FAIL
    assert "未実行" in result.detail


def test_token_boundaries_fail_when_the_tokenizer_cannot_be_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**モデルを読めない環境で PASS にしない。**未実行は FAIL として報告する。"""
    monkeypatch.setitem(sys.modules, "transformers", _fake_transformers(_raise_os_error))
    result = preflight.check_token_boundaries(_TOKEN_CONFIG, tmp_path)
    assert result.status is preflight.Status.FAIL
    assert "未実行" in result.detail


def test_token_boundaries_record_the_six_examples_in_both_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§4.1.5 の1。6例 × テンプレート版 / 無テンプレート版を runs/ に残すこと。

    §4.1.3 の「テンプレート適用後の書式ハッシュ」もここで出る。
    ft_data.py はトークナイザに触らないので manifest 側では計算できない(§4.8)。
    """
    monkeypatch.setitem(sys.modules, "transformers", _fake_transformers(_CharTokenizer))
    result = preflight.check_token_boundaries(_TOKEN_CONFIG, tmp_path)
    assert result.status is preflight.Status.PASS, result.detail
    payload = json.loads((tmp_path / "token_boundary.json").read_text(encoding="utf-8"))
    assert len(payload["examples"]) == 2 * len(preflight.PROMPT_FORMAT_EXAMPLES)
    assert payload["templated_format_hash"] != payload["bare_format_hash"]
    assert payload["model"]["revision"] == _TOKEN_CONFIG["model"]["revision"]


def test_token_boundaries_fail_when_the_chat_template_cannot_be_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-025 は全項目をテンプレート経由にした。適用できないなら未実行である。"""

    class _NoTemplate(_CharTokenizer):
        def apply_chat_template(self, *args: Any, **kwargs: Any) -> str:
            raise ValueError("chat_template が定義されていない")

    monkeypatch.setitem(sys.modules, "transformers", _fake_transformers(_NoTemplate))
    result = preflight.check_token_boundaries(_TOKEN_CONFIG, tmp_path)
    assert result.status is preflight.Status.FAIL
    assert "未実行" in result.detail


def _raise_os_error(*args: Any, **kwargs: Any) -> Any:
    raise OSError("重みが無い")


def _fake_transformers(tokenizer_factory: Any) -> Any:
    """AutoTokenizer だけを持つ偽 transformers モジュール。"""

    module = types.ModuleType("transformers")

    class _AutoTokenizer:
        @staticmethod
        def from_pretrained(name: str, revision: str | None = None) -> Any:
            return tokenizer_factory()

    module.AutoTokenizer = _AutoTokenizer  # type: ignore[attr-defined]
    return module


def test_token_boundary_record_detects_a_fused_boundary() -> None:
    """§4.1.5 の2。`=` と completion 先頭が同一トークンに融合したら落ちること。

    実モデルに依存しないよう、融合するトークナイザを偽装して境界判定だけを見る。
    """
    record, problems = _token_boundary_record_with(_FusingTokenizer(), "3+4=", "9")
    assert problems
    assert any("境界をまたぐ" in problem for problem in problems)
    assert record["fused_spans"]


def test_token_boundary_record_passes_on_a_clean_split() -> None:
    record, problems = _token_boundary_record_with(_CharTokenizer(), "3+4=", "9")
    assert problems == []
    assert record["prompt_ids"] + record["completion_ids"] == record["joint_ids"]


def _token_boundary_record_with(tokenizer: Any, prompt: str, completion: str) -> tuple:
    """テンプレートを通さない側(ADR-025 決定2 のアンカー)で1例を測る。"""
    return preflight._token_boundary_record(tokenizer, prompt, completion, templated=False)


class _CharTokenizer:
    """1文字1トークンの偽トークナイザ。境界判定の検査にだけ使う。"""

    bos_token_id = None
    chat_template = "{% for m in messages %}<|user|>{{ m['content'] }}{% endfor %}<|assistant|>"

    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        tokenize: bool = True,
        add_generation_prompt: bool = False,
    ) -> str:
        body = "".join(f"<|user|>{message['content']}" for message in messages)
        return body + ("<|assistant|>" if add_generation_prompt else "")

    def __call__(
        self, text: str, add_special_tokens: bool = True, return_offsets_mapping: bool = False
    ) -> dict[str, Any]:
        encoded: dict[str, Any] = {"input_ids": [ord(character) for character in text]}
        if return_offsets_mapping:
            encoded["offset_mapping"] = [(i, i + 1) for i in range(len(text))]
        return encoded


class _FusingTokenizer(_CharTokenizer):
    """末尾2文字を1トークンに融合する偽トークナイザ(`=` と数字の融合を模す)。"""

    def __call__(
        self, text: str, add_special_tokens: bool = True, return_offsets_mapping: bool = False
    ) -> dict[str, Any]:
        if len(text) < 2:
            return super().__call__(text, add_special_tokens, return_offsets_mapping)
        head = [ord(character) for character in text[:-2]]
        encoded: dict[str, Any] = {"input_ids": [*head, -1]}
        if return_offsets_mapping:
            encoded["offset_mapping"] = [(i, i + 1) for i in range(len(text) - 2)] + [
                (len(text) - 2, len(text))
            ]
        return encoded


def test_every_manifest_check_fails_on_an_empty_set() -> None:
    """空回りした検査を PASS と報告しない(実態より軽い申告をしない)。"""
    anchor = {"prompt_format": {"format_hash": "a" * 64}}
    cells = [{"name": "id_all", "coverage": "id", "carry": None, "n": 1}]
    results = [
        preflight.check_pool_regions({}),
        preflight.check_matched_stream({}),
        preflight.check_format_hash({}, anchor),
        preflight.check_coverage_k_floor({}, cells),
        preflight.check_t_holdout({}),
        preflight.check_holdout_leak({}),
    ]
    assert {r.status for r in results} == {preflight.Status.FAIL}


def test_a_broken_prompt_template_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """書式が壊れていても preflight 自身は落ちず、FAIL として報告する。"""
    monkeypatch.setitem(sys.modules, "transformers", _fake_transformers(_CharTokenizer))
    config = copy.deepcopy(_TOKEN_CONFIG)
    config["data"]["prompt_template"] = "{a}+{unknown}="
    result = preflight.check_token_boundaries(config, tmp_path)
    assert result.status is preflight.Status.FAIL
    assert "書式テンプレート" in result.detail
