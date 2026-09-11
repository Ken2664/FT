"""順6 の前に `code/eval/run.py` へ足したもの(PLAN-023 手順4)。

答える問い: 「主プール(extrap_magnitude を含む)を、GPU の前に本実行と同じ経路で通せるか」

ここで固定する最重要の性質:
  - **採点バッチは答え域で割れる**(ADR-077 = A14 案 (a))。ans_in と ans_out を1バッチに
    混ぜると `arb` の有無で参照規則の集合が揃わず、**生成を終えた後に**採点が落ちる
  - **dry-run は `eval.dry_run_items` が無ければ本実行と同じ items.jsonl を読む**(PLAN-023 A7)
  - **metrics.json に項目集合と K の出どころが残る**(ADR-076 決定12 = E-5 (b))。
    `frame.py` は (a) と食い違えば止まる

**ここに出る数値は実験結果ではない**(モデルを読まない)。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.analysis import frame
from code.config import load_config
from code.data_gen import eval_pool
from code.data_gen.battery_items import read_items
from code.data_gen.pool import ANSWER_OUT
from code.eval import run
from code.eval.battery import numeric_sum
from code.eval.forced_choice import ForcedChoice
from code.eval.scoring import metrics_by_reference_rule
from code.lesion import AdditiveLesion, ArbitraryLesion

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"
MAIN_CONFIG = REPO_ROOT / "configs" / "exp_phase1_main.yaml"

# **実験条件ではない。**答え域の境界を小さくして、ans_in / ans_out の両方を作るための値。
TEST_MAIN_RADIUS = 9
# arb のズレ表の定義域 [2, 2R] を覆う最小の表(値は t + 2。テストの都合であり実験の表ではない)。
TEST_ARB_TABLE = {total: total + 2 for total in range(2, 2 * TEST_MAIN_RADIUS + 1)}
# ans_in の組と ans_out の組(t = 7 と t = 25)。
PAIR_IN = (3, 4)
PAIR_OUT = (12, 13)

# run の来歴に要る値(test_run_real.py と同じ。実験条件ではない)。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """pip freeze / git / nvidia-smi を呼ばない(test_run_real.py と同じ)。"""
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


def lesions_with_arb() -> dict[str, Any]:
    return {
        "p2": AdditiveLesion(offset=2, name="p2"),
        "arb": ArbitraryLesion(table=TEST_ARB_TABLE, name="arb"),
    }


# --------------------------------------------------------------------------
# A14: 採点バッチを答え域で割る(ADR-077)
# --------------------------------------------------------------------------


def test_mixing_answer_ranges_in_one_batch_breaks_scoring() -> None:
    """★なぜ割るのか: ans_in と ans_out を混ぜると採点が止まる(A14 の再現)。"""
    lesions = lesions_with_arb()
    items = numeric_sum.build_bare_sum_items(
        [PAIR_IN, PAIR_OUT], pool_id="main", reference_lesions=lesions
    )
    responses = [numeric_sum.to_response(item, 0, lesions) for item in items]
    with pytest.raises(ValueError, match="揃っていない"):
        metrics_by_reference_rule(responses, "p2")


def test_scoring_batches_split_by_answer_range() -> None:
    """★ans_in は群の名前のまま、ans_out は `<群>.ans_out`。どちらのバッチも採点できる。"""
    lesions = lesions_with_arb()
    items = numeric_sum.build_bare_sum_items(
        [PAIR_IN, PAIR_OUT], pool_id="main", reference_lesions=lesions
    )
    batches = run.scoring_batches(
        items, numeric_sum.GROUP_BARE_SUM, reference_rule="p2", main_radius=TEST_MAIN_RADIUS
    )
    names = [name for name, _, _ in batches]
    assert names == ["bare_sum", f"bare_sum.{ANSWER_OUT}"]
    rules = {}
    for name, rule, batch_items in batches:
        responses = [numeric_sum.to_response(item, 0, lesions) for item in batch_items]
        rules[name] = set(metrics_by_reference_rule(responses, rule)["by_reference_rule"])
    assert rules == {"bare_sum": {"p2", "arb"}, f"bare_sum.{ANSWER_OUT}": {"p2"}}


def test_a_pool_without_ans_out_keeps_the_old_batch_names() -> None:
    """主プールより前の run(smoke 系)はすべて ans_in なので、バッチ名は変わらない。"""
    lesions = lesions_with_arb()
    items = numeric_sum.build_bare_sum_items([PAIR_IN], pool_id="main", reference_lesions=lesions)
    batches = run.scoring_batches(
        items, numeric_sum.GROUP_BARE_SUM, reference_rule="p2", main_radius=TEST_MAIN_RADIUS
    )
    assert [name for name, _, _ in batches] == ["bare_sum"]


# --------------------------------------------------------------------------
# A7: dry-run は items.jsonl を読む
# --------------------------------------------------------------------------


@pytest.fixture
def smoke_pool(tmp_path: Path) -> dict[str, Any]:
    """smoke のプールを tmp に書き出し、それを指す config(dry_run_items を消したもの)。"""
    config = load_config(SMOKE_CONFIG)
    pool_dir = tmp_path / "battery"
    eval_pool.write_pool(eval_pool.build(config), pool_dir)
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    config["eval"].pop("dry_run_items")
    return {"config": config, "pool_dir": pool_dir, "tmp_path": tmp_path}


def test_dry_run_reads_the_pool_when_no_explicit_list(smoke_pool: dict[str, Any]) -> None:
    """★`eval.dry_run_items` が無ければ本実行と同じ items.jsonl を読む(PLAN-023 A7)。"""
    report = run.dry_run(smoke_pool["config"])
    items = read_items(smoke_pool["pool_dir"] / "items.jsonl")
    assert report["n_items"] == len(items)
    assert report["items_source"] == str(smoke_pool["pool_dir"] / "items.jsonl")


def test_dry_run_still_prefers_the_explicit_list() -> None:
    """明示リストがある config(smoke)は従来どおりそれを読む。"""
    report = run.dry_run(load_config(SMOKE_CONFIG))
    assert report["items_source"] == run.DRY_RUN_ITEMS_KEY


def test_dry_run_without_a_pool_stops(smoke_pool: dict[str, Any]) -> None:
    """items.jsonl が無ければ止まる(黙って 0 項目の配線確認にしない)。"""
    config = copy.deepcopy(smoke_pool["config"])
    config["eval"]["anchor_manifest"] = str(smoke_pool["tmp_path"] / "absent" / "manifest.json")
    with pytest.raises(run.ConfigError, match="評価プールの項目が無い"):
        run.dry_run(config)


# --------------------------------------------------------------------------
# E-5 (b): metrics.json の pool / coverage(ADR-076 決定12)
# --------------------------------------------------------------------------


def truthful_generator(config: dict[str, Any], items: list[Any]) -> dict[str, Any]:
    """真値を答える固定応答(test_run_real.py の truthful_engines を小さくしたもの)。"""
    template_set = config["data"]["eval_template_set"]
    lesions = run.build_reference_lesions(config)
    texts: dict[str, str] = {}
    answers: dict[str, bool] = {}
    for item in items:
        prompt = run.RENDERERS[item.group](
            item, run.load_group_templates(config, item.group, template_set)
        )
        if item.group == "comparison":
            answers[prompt] = run.t3_comparison.to_response(item, None, lesions).truth
        elif item.group == "specificity":
            texts[prompt] = f"Answer: {run.specificity_control.item_true_value(item)}."
        else:
            texts[prompt] = f"Answer: {sum(item.operands)}."

    def generator(prompts: list[str]) -> list[str]:
        return [texts[prompt] for prompt in prompts]

    def scorer(prompts: list[str]) -> list[ForcedChoice]:
        # 対数尤度は答えと整合させる(test_run_real.py の _choice と同じ形)。
        return [
            ForcedChoice(
                answer=answers[prompt],
                yes_logprob=-0.1 if answers[prompt] else -2.0,
                no_logprob=-2.0 if answers[prompt] else -0.1,
            )
            for prompt in prompts
        ]

    return {"generator": generator, "scorer": scorer}


@pytest.fixture
def executed_run(smoke_pool: dict[str, Any]) -> Path:
    config = copy.deepcopy(smoke_pool["config"])
    config["model"]["name"] = TEST_MODEL
    config["model"]["revision"] = TEST_REVISION
    config["model"]["device"] = "cpu"
    config["eval"]["batch_size"] = 1
    config["eval"]["do_sample"] = False
    config_path = smoke_pool["tmp_path"] / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    items = read_items(smoke_pool["pool_dir"] / "items.jsonl")
    return run.execute(
        config,
        config_path=config_path,
        run_dir=smoke_pool["tmp_path"] / "run",
        **truthful_generator(config, items),
    )


def test_metrics_record_the_pool_and_the_coverage(
    executed_run: Path, smoke_pool: dict[str, Any]
) -> None:
    """★項目集合(manifest・pairs_hash・items の sha256)と K の出どころが残る。"""
    payload = json.loads((executed_run / "metrics.json").read_text(encoding="utf-8"))
    manifest = json.loads((smoke_pool["pool_dir"] / "manifest.json").read_text(encoding="utf-8"))
    assert payload["pool"]["pairs_hash"] == manifest["pairs_hash"]
    assert payload["pool"]["items_sha256"] == manifest["files"]["items.jsonl"]
    ft_manifest = eval_pool.load_condition_manifest(smoke_pool["config"])
    coverage = payload["coverage"]
    assert coverage["pairs_hash"] == ft_manifest["coverage"]["pairs_hash"]
    assert coverage["coverage_k"] == ft_manifest["coverage"]["coverage_k"]
    assert coverage["train_domain_hi"] == ft_manifest["train_domain"]["hi"]
    assert coverage["data_id"] == ft_manifest["data_id"]


def test_frame_accepts_a_matching_coverage_record(executed_run: Path) -> None:
    """(a) と (b) が一致していれば frame はそのまま読む。"""
    inputs = frame.load_run(executed_run / "metrics.json")
    payload = json.loads((executed_run / "metrics.json").read_text(encoding="utf-8"))
    assert inputs.pairs_hash == payload["coverage"]["pairs_hash"]


def test_frame_stops_when_the_coverage_record_disagrees(executed_run: Path) -> None:
    """★評価の後に K が動いた(記録と manifest が食い違う)なら止まる(ADR-076 決定12)。"""
    path = executed_run / "metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["coverage"]["pairs_hash"] = "0" * 64
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(frame.FrameError, match="食い違う"):
        frame.load_run(path)


# --------------------------------------------------------------------------
# 本番 config の dry-run(PLAN-023 §5)
# --------------------------------------------------------------------------


def test_main_config_dry_runs_on_the_committed_pool(tmp_path: Path) -> None:
    """★本番 config の dry-run が主プール(1,640 項目)の上で通り、ans_out のバッチが出る。

    items.jsonl は git に無いので、本番 config から tmp に書き出して読ませる。
    """
    config = load_config(MAIN_CONFIG)
    pool_dir = tmp_path / "main"
    eval_pool.write_pool(eval_pool.build(config), pool_dir)
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    report = run.dry_run(config)
    assert report["n_items"] == 1640
    assert set(report["by_batch"]) == {
        "comparison",
        f"comparison.{ANSWER_OUT}",
        "bare_sum",
        f"bare_sum.{ANSWER_OUT}",
        "bare_sum_instructed",
        "word_problem",
        f"word_problem.{ANSWER_OUT}",
        "spec_sub",
        "spec_mul",
    }
