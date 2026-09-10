"""桁数掃引の CLI(code/eval/sweep.py)のテスト。

答える問い: 「M -> correct_rate の表を、モデルを読まずに検査できるか」

**モデルの重みは1度も読まない**(PLAN-004 §4.3 の1)。**ここに出る数値は
実験結果ではない** —— 固定応答に対する分解であり、素のモデルの算術能力は
1度も測っていない。M* もここでは決まらない(承認待ち #9 / #15)。
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.config import ConfigError, load_config
from code.data_gen.battery_items import Item
from code.data_gen.pool import COVERAGE_EXTRAP_MAGNITUDE, label_main_coverage
from code.eval import sweep
from code.eval.battery import magnitude_sweep
from code.eval.generate import Generator
from code.lesion import reference_lesions_from_config
from code.rates import RATE_FIELDS, RateBreakdown

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# **実験条件ではない。**smoke config は model.name / revision を null にしてある。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40
# smoke config は device / batch_size を持たない(あちらは編集してはならない。
# ADR-037 決定4)。cpu と 1 を置くのは**重みを読まないから**であって、
# 実験条件の宣言ではない —— この経路は固定応答の生成器で回る
TEST_DEVICE = "cpu"
TEST_BATCH_SIZE = 1
# ★実験条件の宣言ではない。値は ADR-042 決定2(貪欲)と同じだが、この経路は
# 固定応答の生成器で回る。smoke config は `eval.do_sample` を持たない
# (触ってはならない。ADR-037 決定4)
TEST_DO_SAMPLE = False

# ★実験条件ではない。smoke config は Q(M) の腕の欄(shell_*)を持たない
# (smoke.yaml は編集しない。ADR-037 決定4)。主域の半径は smoke の
# data.train_domain_max = 9 なので、Q(M) は M > 9 でしか空でない。
# 格子に 10 / 12 / 15 を足すのは、本番の 100 / 110 / 125 と同じ形 ——
# 「Q(M) が極小で引けない水準」(|Q(10)| = 1 < 4)と「引ける水準」—— を
# 小さい数で通すためである。台地 2 / 5 は (M-9)^2 >= 4 なので、
# ★閉じた式で導くと判定水準に混じる罠もこの格子で踏める。
TEST_RADII = [2, 5, 9, 10, 12, 15]
TEST_SHELL_RADII = [12, 15]

UNREADABLE = "???"


def with_shell_arm(config: dict[str, Any]) -> dict[str, Any]:
    """smoke config に Q(M) の腕の欄を足す(ADR-071 の 3 決定と同じ形。値は小さい)。"""
    section = config["eval"]["magnitude_sweep"]
    section["radii"] = list(TEST_RADII)
    section["shell_definition"] = magnitude_sweep.SHELL_DEFINITION_QUADRANT
    section["shell_n_items"] = section["n_items_per_radius"]
    section["shell_radii"] = list(TEST_SHELL_RADII)
    section["shell_judgement_radii"] = list(TEST_SHELL_RADII)
    return config


def write_config(config: dict[str, Any], path: Path) -> Path:
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)の呼び出しを止める。

    来歴の**中身**は code/tests/test_artifacts.py が実物で検査する。ここで
    毎回 pip freeze を回すと1テストあたり数秒かかり、配線のテストが遅くなる。
    """
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


@pytest.fixture
def workspace(tmp_path: Path) -> dict[str, Any]:
    """生成設定を埋めた config と、その写しを置く場所。"""
    config = with_shell_arm(load_config(SMOKE_CONFIG))
    config["model"]["name"] = TEST_MODEL
    config["model"]["revision"] = TEST_REVISION
    config["model"]["device"] = TEST_DEVICE
    config["eval"]["batch_size"] = TEST_BATCH_SIZE
    config["eval"]["do_sample"] = TEST_DO_SAMPLE
    config_path = write_config(config, tmp_path / "config.yaml")
    return {"config": config, "config_path": config_path, "run_dir": tmp_path / "run"}


def sweep_items(config: dict[str, Any]) -> list[Item]:
    """掃引が 2 本の腕で引く項目をすべて返す(全水準・全抽出シード)。

    掃引が実際に引くのと同じ関数・同じシードで作るので、対応づけがずれない。
    """
    plan = magnitude_sweep.load_sweep_plan(config)
    shell = magnitude_sweep.load_shell_plan(config, plan)
    lesions = reference_lesions_from_config(config)
    pool_id = config["data"]["pool_id"]
    items: list[Item] = []
    for seed in plan.seeds:
        for radius in plan.radii:
            items.extend(
                magnitude_sweep.build_items(
                    radius,
                    n_items=plan.n_items_per_radius,
                    seed=seed,
                    pool_id=pool_id,
                    reference_lesions=lesions,
                )
            )
        for radius in shell.radii:
            items.extend(
                magnitude_sweep.build_quadrant_items(
                    radius,
                    n_items=shell.n_items,
                    seed=seed,
                    pool_id=pool_id,
                    reference_lesions=lesions,
                    main_radius=shell.main_radius,
                )
            )
    return items


def truthful_responses(config: dict[str, Any]) -> dict[str, str]:
    """掃引の各プロンプト(2 本の腕の全項目)に真値 a + b を返す固定応答。"""
    items = sweep_items(config)
    prompts = sweep.sweep_prompts(items, config)
    return {
        prompts[item.item_id]: f"Answer: {item.operands[0] + item.operands[1]}."
        for item in items
    }


def lookup_generator(responses: dict[str, str]) -> Generator:
    def generator(prompts: Sequence[str]) -> list[str]:
        return [responses[prompt] for prompt in prompts]

    return generator


def constant_generator(text: str) -> Generator:
    def generator(prompts: Sequence[str]) -> list[str]:
        return [text for _ in prompts]

    return generator


def test_prompts_use_the_training_format(workspace: dict[str, Any]) -> None:
    """★掃引の文面は評価用テンプレート集合ではなく訓練書式から来る。

    掃引項目は T1(裸の計算式)であり、T1 の書式は `data.prompt_template` と
    1文字も違ってはならない(検査6)。評価用テンプレート集合から引くと、
    素の算術能力を測ったつもりの数値が別の書式に対する数値になる。
    """
    config = workspace["config"]
    lesions = reference_lesions_from_config(config)
    items = magnitude_sweep.build_items(
        3, n_items=3, seed=1, pool_id=config["data"]["pool_id"], reference_lesions=lesions
    )
    prompts = sweep.sweep_prompts(items, config)
    template = config["data"]["prompt_template"]
    for item in items:
        assert prompts[item.item_id] == template.format(
            a=item.operands[0], b=item.operands[1]
        )


def test_every_declared_radius_is_measured(workspace: dict[str, Any]) -> None:
    """★config が宣言した M をすべて、宣言したシードすべてで測る(粒度は config が決める)。"""
    config = workspace["config"]
    declared = config["eval"]["magnitude_sweep"]
    results = sweep.sweep(config, generator=constant_generator(UNREADABLE))
    assert [result.radius for result in results] == sorted(declared["radii"])
    for result in results:
        assert [s.seed for s in result.per_seed] == declared["seeds"]
        assert result.n_items_per_seed == declared["n_items_per_radius"]
        assert result.total_items == declared["n_items_per_radius"] * len(declared["seeds"])


def test_every_point_reports_all_four_values(workspace: dict[str, Any]) -> None:
    """★どの M でも4値(シード平均)が揃い、合計が 1.0 になる(CLAUDE.md §6)。"""
    results = sweep.sweep(workspace["config"], generator=constant_generator(UNREADABLE))
    for result in results:
        row = result.as_dict()
        total = (
            row["correct_rate"]
            + row["rule_rate"]
            + row["other_error_rate"]
            + row["parse_fail_rate"]
        )
        assert total == pytest.approx(1.0)
        assert row["parse_fail_rate"] == pytest.approx(1.0)
        # 4値すべてにシード間 SD が揃う。全シード parse_fail なので散らばりは 0
        assert set(row["seed_sd"]) == {
            "correct_rate", "rule_rate", "other_error_rate", "parse_fail_rate"
        }
        assert row["seed_sd"]["parse_fail_rate"] == pytest.approx(0.0)


def test_a_truthful_model_scores_all_correct(workspace: dict[str, Any]) -> None:
    """★真値を返す応答はどの M でも correct に落ちる(シード平均でも 1.0)。"""
    config = workspace["config"]
    results = sweep.sweep(config, generator=lookup_generator(truthful_responses(config)))
    for result in results:
        assert result.seed_mean()["correct_rate"] == pytest.approx(1.0)
        assert result.seed_mean()["rule_rate"] == pytest.approx(0.0)
        assert result.seed_sd()["correct_rate"] == pytest.approx(0.0)


def biased_responses(config: dict[str, Any]) -> dict[str, str]:
    """和が偶数の項目にだけ真値、奇数には読めない文字列を返す応答マップ。

    シードごとに引く (a, b) が違うので、シード別 correct_rate が割れる ——
    シード平均とシード間 SD の経路を通すために使う。2 本の腕の全項目を覆う。
    """
    items = sweep_items(config)
    prompts = sweep.sweep_prompts(items, config)
    out: dict[str, str] = {}
    for item in items:
        total = item.operands[0] + item.operands[1]
        out[prompts[item.item_id]] = f"Answer: {total}." if total % 2 == 0 else UNREADABLE
    return out


def test_radius_result_aggregates_seeds_as_mean_and_sample_sd() -> None:
    """★RadiusResult の代表値 = シード別 4値の平均、SD = 標本 SD(ADR-041 決定3 規則3)。

    ここは集計の算術だけを、決まった4値分解で検査する(乱数に依らない)。
    """
    from code.rates import RateBreakdown

    def seed_result(seed: int, correct: float, rule: float) -> sweep.SeedResult:
        return sweep.SeedResult(
            seed=seed,
            breakdown=RateBreakdown(correct, rule, 1.0 - correct - rule, 0.0, 10),
            predictions=[],
        )

    result = sweep.RadiusResult(
        radius=9,
        reference_rule="p2",
        per_seed=[
            seed_result(0, 0.8, 0.1),
            seed_result(1, 0.6, 0.2),
            seed_result(2, 1.0, 0.0),
        ],
    )
    corrects = [0.8, 0.6, 1.0]
    assert result.seed_mean()["correct_rate"] == pytest.approx(statistics.fmean(corrects))
    assert result.seed_sd()["correct_rate"] == pytest.approx(statistics.stdev(corrects))
    row = result.as_dict()
    assert row["correct_rate"] == pytest.approx(statistics.fmean(corrects))
    assert row["seed_sd"]["correct_rate"] == pytest.approx(statistics.stdev(corrects))
    assert row["n_seeds"] == 3
    assert row["n_items_per_seed"] == 10
    assert row["n_items"] == 30
    assert [s["seed"] for s in row["by_seed"]] == [0, 1, 2]
    # 4値のシード平均は合計 1.0(CLAUDE.md §6)
    assert sum(result.seed_mean().values()) == pytest.approx(1.0)


def test_the_table_representative_is_the_seed_mean(workspace: dict[str, Any]) -> None:
    """★掃引を通した経路でも、by_radius の行がシード別 correct_rate の記述統計に一致する。"""
    config = workspace["config"]
    results = sweep.sweep(config, generator=lookup_generator(biased_responses(config)))
    for result in results:
        per_seed = [s.breakdown.correct_rate for s in result.per_seed]
        row = result.as_dict()
        assert row["correct_rate"] == pytest.approx(statistics.fmean(per_seed))
        assert row["seed_sd"]["correct_rate"] == pytest.approx(statistics.stdev(per_seed))


def test_the_same_seeds_give_the_same_table(workspace: dict[str, Any]) -> None:
    """★同じ `seeds` で2回回すと同じ表(決定的)。"""
    config = workspace["config"]
    responses = biased_responses(config)
    first = sweep.correct_rate_table(
        sweep.sweep(config, generator=lookup_generator(responses))
    )
    second = sweep.correct_rate_table(
        sweep.sweep(config, generator=lookup_generator(responses))
    )
    assert first == second


def test_a_single_seed_reports_zero_dispersion(workspace: dict[str, Any]) -> None:
    """★シードが1本だと SD は 0.0(標本サイズ 1 で分散は未定義。既定値ではない)。

    本実験は5シード(ADR-041 決定5)。この経路は smoke でしか通らない。
    """
    config = workspace["config"]
    config["eval"]["magnitude_sweep"]["seeds"] = [20260827]
    results = sweep.sweep(config, generator=lookup_generator(biased_responses(config)))
    for result in results:
        assert len(result.per_seed) == 1
        assert result.seed_sd()["correct_rate"] == 0.0
        assert result.as_dict()["seed_sd"]["parse_fail_rate"] == 0.0


def test_changing_a_seed_changes_the_drawn_items(workspace: dict[str, Any]) -> None:
    """★シードを1つ変えると、その M で引かれる項目集合が変わる。"""
    config = workspace["config"]
    lesions = reference_lesions_from_config(config)
    kwargs: dict[str, Any] = {
        "n_items": config["eval"]["magnitude_sweep"]["n_items_per_radius"],
        "pool_id": config["data"]["pool_id"],
        "reference_lesions": lesions,
    }
    a = magnitude_sweep.build_items(9, seed=20260827, **kwargs)
    b = magnitude_sweep.build_items(9, seed=20260828, **kwargs)
    assert [item.operands for item in a] != [item.operands for item in b]


def test_the_table_maps_each_radius_to_a_correct_rate(workspace: dict[str, Any]) -> None:
    """★この CLI の成果物は M -> correct_rate の対応表である。"""
    config = workspace["config"]
    results = sweep.sweep(config, generator=lookup_generator(truthful_responses(config)))
    table = sweep.correct_rate_table(results)
    assert list(table) == [str(radius) for radius in sorted(
        config["eval"]["magnitude_sweep"]["radii"]
    )]
    assert all(rate == pytest.approx(1.0) for rate in table.values())


def test_the_sweep_does_not_decide_the_extrapolation_limit(
    workspace: dict[str, Any],
) -> None:
    """★掃引は M* も θ も出さない(承認待ち #9 / #15)。

    出すと、その値が「実測で決まった」ように見えてしまう。表を読んで M* を
    置くのは人間であり、決まったら eval.extrapolation_radius に入る。
    """
    config = workspace["config"]
    target = sweep.execute(
        config,
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(truthful_responses(config)),
    )
    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    assert "extrapolation_radius" not in payload
    assert "M*" not in json.dumps(payload, ensure_ascii=False)
    assert "M* は決まらない" in (target / "log.txt").read_text(encoding="utf-8")


def test_the_report_table_has_a_seed_sd_column(workspace: dict[str, Any]) -> None:
    """★log.txt / stdout の表にシード間 SD の列がある(ADR-041 決定3 規則3。PLAN-006 §4.4)。"""
    config = workspace["config"]
    target = sweep.execute(
        config,
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(biased_responses(config)),
    )
    log = (target / "log.txt").read_text(encoding="utf-8")
    assert "±sd" in log
    assert "seeds=" in log
    # 各 M の行に、シード平均の correct_rate とその隣に SD が並ぶ
    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    for row in payload["by_radius"]:
        assert f"{row['correct_rate']:>8.4f}  {row['seed_sd']['correct_rate']:>7.4f}" in log


def test_execute_writes_the_artifacts(workspace: dict[str, Any]) -> None:
    """★来歴を残す(infra/RUNPOD.md §4)。書かないものは書かない。"""
    config = workspace["config"]
    target = sweep.execute(
        config,
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(truthful_responses(config)),
    )
    for name in ("config.yaml", "git_sha.txt", "env.txt", "timestamp.txt", "metrics.json",
                 "log.txt"):
        assert (target / name).exists()
    for name in ("cost.txt", "token_boundary.json"):
        assert not (target / name).exists()

    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    assert payload["kind"] == sweep.SWEEP_KIND
    assert payload["generation"]["model_name"] == TEST_MODEL
    assert payload["sweep"] == magnitude_sweep.load_sweep_plan(config).as_dict()
    # ★LoRA アダプタは読んでいない。素の重みに対する測定である
    assert payload["adapter"] is None

    # predictions は M ごと・抽出シードごとに分ける
    for radius in payload["sweep"]["radii"]:
        for seed in payload["sweep"]["seeds"]:
            path = (
                target / "predictions"
                / f"{sweep.PREDICTIONS_PREFIX}_M{radius}_s{seed}.jsonl"
            )
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            assert len(rows) == payload["sweep"]["n_items_per_radius"]
            assert all(row["classification"] == "correct" for row in rows)


def test_the_sweep_records_the_wall_clock(workspace: dict[str, Any]) -> None:
    """★掃引も壁時計時間を残す(ADR-040 決定6)。

    掃引は本実行と**同じ生成経路**を通る(`code/eval/generate.py`)。片方だけ
    秒数を残すと、まとめ幅あたりの速度を同じ土俵で読めない。
    """
    config = workspace["config"]
    target = sweep.execute(
        config,
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(truthful_responses(config)),
    )
    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    timing = payload["timing"]
    plan = payload["sweep"]
    shell = payload["quadrant"]["shell"]
    # 分母は**実際に採点した件数**である(宣言した n_items_per_radius の掛け算ではない)。
    # by_radius の n_items は全抽出シード合算。★2 本の腕の合計である(ADR-071 決定2)
    assert timing["n_items"] == sum(row["n_items"] for row in payload["by_radius"]) + sum(
        row["n_items"] for row in payload["quadrant"]["by_radius"]
    )
    assert timing["n_items"] == (
        len(plan["radii"]) * plan["n_items_per_radius"] * len(plan["seeds"])
        + len(shell["radii"]) * shell["n_items_per_radius"] * len(plan["seeds"])
    )
    assert 0.0 <= timing["generation_seconds"] <= timing["total_seconds"]
    assert "壁時計:" in (target / "log.txt").read_text(encoding="utf-8")


def test_a_declared_adapter_stops_the_sweep(workspace: dict[str, Any]) -> None:
    """★アダプタを宣言した config で掃引を回さないこと(ADR-043 決定3 の裏)。

    掃引が測るのは**素の算術能力**である。アダプタを載せると `M*` が
    病変後の能力から決まり、外挿域の定義そのものが病変に依存する ——
    PLAN-001 §4.1.1 が潰したはずの交絡に戻る。

    **黙って無視しない。**無視すると、config は「読む」と書いているのに
    読んでいない run が残り、記録と実際が食い違う。
    """
    config = workspace["config"]
    config["model"]["adapter"] = "runs/20260901_140000_train/adapter"
    with pytest.raises(ConfigError, match="adapter"):
        sweep.execute(
            config,
            config_path=workspace["config_path"],
            run_dir=workspace["run_dir"],
            generator=lookup_generator(truthful_responses(config)),
        )


def test_undecided_generation_settings_stop_the_sweep() -> None:
    """★smoke config(model.name = null)のままでは掃引できない。

    決めていない設定で表が出ると、その表が M* の根拠として引かれる。
    """
    with pytest.raises(ConfigError, match="model.name"):
        sweep.main(["--config", str(SMOKE_CONFIG)])


def test_the_dry_run_does_not_measure_anything(
    workspace: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """--dry-run は項目の組み立てだけを見せ、correct_rate を出さない。2 本の腕を組む。"""
    assert sweep.main(["--config", str(workspace["config_path"]), "--dry-run"]) == 0
    assert "実験ではない" in capsys.readouterr().out
    # 報告そのものに率が1つも入っていないこと(見出しの文言ではなく中身で見る)
    summary = sweep.dry_run_summary(workspace["config"])
    assert "correct_rate" not in json.dumps(summary, ensure_ascii=False)
    # Q(M) の腕も組まれ、|Q(M)| は組合せ論の計数として出る(実験結果ではない)
    quadrant = summary["quadrant"]["by_radius"]
    assert list(quadrant) == [str(radius) for radius in TEST_SHELL_RADII]
    main_radius = workspace["config"]["data"]["train_domain_max"]
    for radius in TEST_SHELL_RADII:
        assert quadrant[str(radius)]["population_size"] == (radius - main_radius) ** 2


def test_a_config_without_the_shell_arm_stops_the_sweep() -> None:
    """★Q(M) の腕を宣言していない config では掃引も dry-run も回らない(ADR-071)。

    smoke.yaml は shell_* を持たない。**判定の材料が出ないまま累積の表だけが
    出ると、その表が判定に使われる**(★F121)。黙って腕1 だけ回さない。
    """
    with pytest.raises(ConfigError, match="shell_definition"):
        sweep.dry_run_summary(load_config(SMOKE_CONFIG))
    with pytest.raises(ConfigError, match="shell_definition"):
        sweep.main(["--config", str(SMOKE_CONFIG), "--dry-run"])


# --------------------------------------------------------------------------
# 2 本の腕(ADR-071。腕1 = 一様抽出 = 記述 / 腕2 = Q(M) = 判定の材料)
# --------------------------------------------------------------------------


def _row_total(row: dict[str, Any]) -> float:
    return sum(row[key] for key in RATE_FIELDS)


def _execute(workspace: dict[str, Any], responses: dict[str, str]) -> Path:
    return sweep.execute(
        workspace["config"],
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(responses),
    )


def test_the_quadrant_arm_measures_only_the_derivable_radii(
    workspace: dict[str, Any],
) -> None:
    """★腕2 は |Q(M)| >= shell_n_items の水準だけを、腕1 と同じシード列で測る。

    |Q(10)| = 1 は引けない(本番の M = 100 / 110 と同じ形)。台地 2 / 5 / 9 は Q(M) が空。
    """
    config = workspace["config"]
    declared = config["eval"]["magnitude_sweep"]
    results = sweep.sweep_quadrant(config, generator=constant_generator(UNREADABLE))
    assert [result.radius for result in results] == TEST_SHELL_RADII
    for result in results:
        assert [s.seed for s in result.per_seed] == declared["seeds"]
        assert result.n_items_per_seed == declared["shell_n_items"]


def test_every_quadrant_item_is_an_extrap_magnitude_pair(workspace: dict[str, Any]) -> None:
    """★腕2 が解かせた組は、すべて主軸 3 水準目(`extrap_magnitude`)に入る(ADR-071 決定1)。

    判定は `label_main_coverage` そのもので行う(定義をテストにも書き直さない)。
    """
    config = workspace["config"]
    main_radius = config["data"]["train_domain_max"]
    results = sweep.sweep_quadrant(config, generator=lookup_generator(truthful_responses(config)))
    for result in results:
        for seed_result in result.per_seed:
            for record in seed_result.predictions:
                a, b = record["operands"]
                assert max(abs(a), abs(b)) <= result.radius
                label = label_main_coverage((a, b), frozenset(), main_radius)
                assert label == COVERAGE_EXTRAP_MAGNITUDE


def test_every_block_reports_all_four_values(workspace: dict[str, Any]) -> None:
    """★どのブロックのどの行でも4値が揃い、合計が 1.0 になる(CLAUDE.md §6 / ADR-016)。

    腕1 の累積・腕1 の格子殻(合算)・腕2 のすべてで検査する。
    """
    target = _execute(workspace, biased_responses(workspace["config"]))
    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    rows = (
        payload["by_radius"]
        + payload["grid_shell"]["by_radius"]
        + payload["quadrant"]["by_radius"]
    )
    for row in rows:
        assert set(RATE_FIELDS) <= set(row)
        if row["n_items"] == 0:
            continue
        assert _row_total(row) == pytest.approx(1.0)
    for row in payload["quadrant"]["by_radius"]:
        assert set(row["seed_sd"]) == set(RATE_FIELDS)
        for seed_row in row["by_seed"]:
            assert _row_total(seed_row) == pytest.approx(1.0)


def test_metrics_keep_the_arms_in_separate_blocks(workspace: dict[str, Any]) -> None:
    """★metrics.json は腕ごとに別ブロックを持ち、どれが判定の材料かを書く(ADR-071)。

    腕1 は従来の鍵のまま(ADR-041 の追記が `by_radius[*].seed_sd` を名指ししている)。
    **M* はどこにも出ない。**
    """
    config = workspace["config"]
    target = _execute(workspace, truthful_responses(config))
    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    assert payload["roles"] == {
        "by_radius": sweep.ROLE_DESCRIPTION,
        "grid_shell": sweep.ROLE_DESCRIPTION,
        "quadrant": sweep.ROLE_JUDGEMENT_INPUT,
    }
    assert [row["radius"] for row in payload["by_radius"]] == TEST_RADII
    assert [row["radius"] for row in payload["grid_shell"]["by_radius"]] == TEST_RADII
    quadrant = payload["quadrant"]
    plan = magnitude_sweep.load_sweep_plan(config)
    assert quadrant["shell"] == magnitude_sweep.load_shell_plan(config, plan).as_dict()
    assert quadrant["shell"]["judgement_radii"] == TEST_SHELL_RADII
    assert list(quadrant["correct_rate_by_radius"]) == [str(r) for r in TEST_SHELL_RADII]
    main_radius = config["data"]["train_domain_max"]
    for row in quadrant["by_radius"]:
        assert row["population_size"] == (row["radius"] - main_radius) ** 2
        assert row["correct_rate"] == pytest.approx(1.0)
    assert "M*" not in json.dumps(payload, ensure_ascii=False)
    assert "extrapolation_radius" not in json.dumps(payload, ensure_ascii=False)


def test_the_quadrant_arm_writes_its_own_predictions(workspace: dict[str, Any]) -> None:
    """★腕2 の predictions/ は腕1 と別ファイルに、M ごと・抽出シードごとに書く。"""
    config = workspace["config"]
    target = _execute(workspace, truthful_responses(config))
    declared = config["eval"]["magnitude_sweep"]
    for radius in TEST_SHELL_RADII:
        for seed in declared["seeds"]:
            path = (
                target / "predictions"
                / f"{sweep.QUADRANT_PREDICTIONS_PREFIX}_M{radius}_s{seed}.jsonl"
            )
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            assert len(rows) == declared["shell_n_items"]
            assert all(row["params"]["shell"] == declared["shell_definition"] for row in rows)
    # 腕2 の水準でない M には Q(M) の predictions を書かない
    assert not list((target / "predictions").glob(f"{sweep.QUADRANT_PREDICTIONS_PREFIX}_M10_*"))


def test_the_grid_shell_recounts_only_the_new_region(workspace: dict[str, Any]) -> None:
    """★定義 A の格子殻 = 腕1 の予測のうち 1 つ前の格子点の R の外にあるもの(記述)。

    新しく引き直さない。最小の格子点は R(M) 全体、ほかは件数も率も
    predictions の operands と classification から数え直した値に一致する。
    """
    config = workspace["config"]
    results = sweep.sweep(config, generator=lookup_generator(biased_responses(config)))
    rows = sweep.grid_shell_rows(results)
    previous = None
    for result, row in zip(results, rows, strict=True):
        assert row["radius"] == result.radius
        assert row["previous_radius"] == previous
        in_shell = [
            [
                record["classification"]
                for record in seed_result.predictions
                if previous is None
                or max(abs(record["operands"][0]), abs(record["operands"][1])) > previous
            ]
            for seed_result in result.per_seed
        ]
        assert row["n_items_by_seed"] == [len(c) for c in in_shell]
        pooled = [c for categories in in_shell for c in categories]
        assert row["n_items"] == len(pooled)
        if pooled:
            expected = pooled.count("correct") / len(pooled)
            assert row["correct_rate"] == pytest.approx(expected)
        previous = result.radius
    assert rows[0]["n_items"] == results[0].total_items


def test_an_empty_grid_shell_reports_null_rates() -> None:
    """★殻に 1 件も落ちない水準では 4値を null にする(0.0 は「正答率 0」と読める)。"""

    def seed_result(seed: int, operands: list[list[int]]) -> sweep.SeedResult:
        records = [{"operands": pair, "classification": "correct"} for pair in operands]
        return sweep.SeedResult(
            seed=seed,
            breakdown=RateBreakdown(1.0, 0.0, 0.0, 0.0, len(records)),
            predictions=records,
        )

    inner = sweep.RadiusResult(radius=5, reference_rule="p2", per_seed=[seed_result(0, [[1, 2]])])
    # M=9 で引いた組がすべて R(5) の中にある(殻 R(9) − R(5) に 1 件も落ちない)
    outer = sweep.RadiusResult(radius=9, reference_rule="p2", per_seed=[seed_result(0, [[3, 4]])])
    rows = sweep.grid_shell_rows([inner, outer])
    assert rows[0]["correct_rate"] == pytest.approx(1.0)
    assert rows[1]["n_items"] == 0
    assert rows[1]["n_items_by_seed"] == [0]
    assert all(rows[1][key] is None for key in RATE_FIELDS)


def test_the_report_marks_which_table_is_the_judgement_input(
    workspace: dict[str, Any],
) -> None:
    """★log.txt は 3 つの表を見出しで分け、判定の材料が腕2 だけであることを書く。"""
    config = workspace["config"]
    target = _execute(workspace, biased_responses(config))
    log = (target / "log.txt").read_text(encoding="utf-8")
    assert "■ 腕1: R(M) からの一様抽出(累積)—— 記述" in log
    assert "■ 腕1 の切り直し: 定義 A の格子殻" in log
    assert "■ 腕2: Q(M) = extrap_magnitude の母集団 —— 判定の材料" in log
    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    for row in payload["quadrant"]["by_radius"]:
        fraction = row["n_items_per_seed"] / row["population_size"]
        assert (
            f"{row['radius']:>7}  {row['population_size']:>8}  {fraction:>6.3f}  "
            f"{row['n_seeds']:>5}  {row['n_items_per_seed']:>6}  "
            f"{row['correct_rate']:>8.4f}  {row['seed_sd']['correct_rate']:>7.4f}"
        ) in log


def test_a_shell_config_that_contradicts_adr_071_stops_before_the_run(
    workspace: dict[str, Any],
) -> None:
    """★config の shell_radii が導出値と違えば、run ディレクトリを作る前に止まる。

    ★罠の再現: |Q(M)| を (M-9)^2 と書くと台地 2 / 5 が混じる(M < 9 でも平方が正)。
    """
    config = workspace["config"]
    trap = [radius for radius in TEST_RADII if (radius - 9) ** 2 >= 4]
    assert trap != TEST_SHELL_RADII
    config["eval"]["magnitude_sweep"]["shell_radii"] = trap
    with pytest.raises(ConfigError, match="導出値"):
        _execute(workspace, {})
    assert not workspace["run_dir"].exists()
