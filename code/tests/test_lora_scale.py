"""LoRA のスケール s(PLAN-037 I6)と掃引の入口(`code/eval/scale_sweep.py`。I7)。

答える問い: 「s は載せたアダプタの全層に絶対値で置かれ(掛け替えても積み上がらず)、宣言の無い run は
モデルに触れず、掃引は s ごとに別の run を宣言の順に書き、凍結の前に署名を見る取り違えを重みを読む前に
止めるか」

**モデルの重みは 1 度も読まず、peft も使わない**(置き物の LoRA 層・置き物の生成器)。**ここに出る数値は
実験結果ではない。**実機での確かめ(s = 0 が素の重みと、s = 1 が既存の `ident` の評価と一致するか)は
PLAN-037 の S4 の役目である。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from code import artifacts
from code.analysis import aggregate, frame
from code.config import ConfigError
from code.eval import model as eval_model
from code.eval import run, scale_sweep, signature_gate
from code.tests.test_aggregate import eval_metrics, write_run
from code.tests.test_task_subset import (  # noqa: F401  (pool_dirs は fixture)
    CONSTANT_RESPONSE,
    N_T1,
    config_at,
    pool_dirs,
    read_metrics,
    write_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT_EVAL_IDENT = REPO_ROOT / "configs" / "exp_pilot_ft_eval_ident_s0_n313.yaml"

ADAPTER = "default"
INITIAL_SCALING = 4.0  # lora_alpha / r の置き物(alpha 64 / r 16)
N_FAKE_LAYERS = 3
N_SOLVED = 2 * N_T1  # T1 240 + T2 240(パイロット用プールの組合せ論的な件数)


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


# --------------------------------------------------------------------------
# I6: 置き物の LoRA 層で set_scale の使い方を固定する
# --------------------------------------------------------------------------


class FakeLoraLayer:
    """peft==0.20.0 の `LoraLayer` の `scaling` と `set_scale`・`scale_layer` だけを写した置き物。

    写し元: peft/tuners/lora/layer.py(L742 set_scale = 初期値 × scale の絶対値 / L755 scale_layer =
    現在値に掛ける)。アダプタが無い名前は黙って何もしない(peft も同じ)。
    """

    def __init__(self, names: Sequence[str] = (ADAPTER,)) -> None:
        self.initial = {name: INITIAL_SCALING for name in names}
        self.scaling = dict(self.initial)

    def set_scale(self, adapter: str, scale: float) -> None:
        if adapter not in self.scaling:
            return
        self.scaling[adapter] = scale * self.initial[adapter]

    def scale_layer(self, scale: float) -> None:  # 累積する。この実装は使ってはならない
        raise AssertionError("scale_layer は現在値に掛けて累積する。set_scale を使うこと")


class OtherModule:
    """LoRA 層ではない層(触ってはならない)。`scaling` を持たせて取り違えを見つける。"""

    def __init__(self) -> None:
        self.scaling = {ADAPTER: 123.0}


class FakeModel:
    def __init__(self, layers: Sequence[Any], active_adapter: Any = ADAPTER) -> None:
        self._modules = list(layers)
        self.active_adapter = active_adapter

    def modules(self) -> list[Any]:
        return self._modules


def fake_model(**kwargs: Any) -> tuple[FakeModel, list[FakeLoraLayer], OtherModule]:
    layers = [FakeLoraLayer() for _ in range(N_FAKE_LAYERS)]
    other = OtherModule()
    return FakeModel([*layers, other], **kwargs), layers, other


def apply(model: FakeModel, scale: float) -> int:
    return eval_model.apply_lora_scale(model, scale, layer_type=FakeLoraLayer)


def test_the_scale_reaches_every_lora_layer_and_nothing_else() -> None:
    model, layers, other = fake_model()
    assert apply(model, 0.5) == N_FAKE_LAYERS
    assert [layer.scaling[ADAPTER] for layer in layers] == [0.5 * INITIAL_SCALING] * N_FAKE_LAYERS
    assert other.scaling == {ADAPTER: 123.0}


def test_the_scale_is_an_absolute_value_not_a_product() -> None:
    """★掛け替えても前の s が残らない(積み上がらない)。"""
    model, layers, _ = fake_model()
    for scale in (0.5, 0.25, 1.0, 0.0, 0.5):
        apply(model, scale)
        assert all(layer.scaling[ADAPTER] == scale * INITIAL_SCALING for layer in layers)


def test_the_end_points_are_the_base_weights_and_the_adapter_itself() -> None:
    """★s = 0 は効きが 0(素の重み)、s = 1 は初期値(アダプタそのもの)。"""
    model, layers, _ = fake_model()
    apply(model, 0.0)
    assert all(layer.scaling[ADAPTER] == 0.0 for layer in layers)
    apply(model, 1.0)
    assert all(layer.scaling[ADAPTER] == layer.initial[ADAPTER] for layer in layers)


@pytest.mark.parametrize("bad", [-0.01, 1.01, 2, -1, True, False, "0.5", None, [0.5], float("nan")])
def test_a_scale_outside_zero_to_one_or_not_a_number_stops(bad: Any) -> None:
    model, layers, _ = fake_model()
    with pytest.raises(ConfigError, match="スケール s"):
        apply(model, bad)
    assert all(layer.scaling[ADAPTER] == INITIAL_SCALING for layer in layers)  # 触れていない


@pytest.mark.parametrize("good", [0, 1, 0.0, 1.0, 0.5, 1e-9])
def test_the_closed_interval_is_accepted(good: float) -> None:
    assert eval_model.validate_lora_scale(good, source="test") == float(good)


def test_the_adapter_name_comes_from_the_model_not_a_constant() -> None:
    layers = [FakeLoraLayer(names=("other",)) for _ in range(2)]
    model = FakeModel(layers, active_adapter="other")
    assert apply(model, 0.5) == 2
    assert [layer.scaling["other"] for layer in layers] == [0.5 * INITIAL_SCALING] * 2


def test_a_single_element_list_of_adapter_names_is_accepted() -> None:
    model, layers, _ = fake_model(active_adapter=[ADAPTER])
    assert apply(model, 0.5) == N_FAKE_LAYERS


@pytest.mark.parametrize("active", [None, [], ["a", "b"], 3])
def test_an_unreadable_adapter_name_stops(active: Any) -> None:
    model, _, _ = fake_model(active_adapter=active)
    with pytest.raises(ConfigError, match="アダプタ名"):
        apply(model, 0.5)


def test_no_lora_layer_with_the_adapter_stops() -> None:
    """★何も掛からないまま「s を掛けた」と記録しない。"""
    model = FakeModel([OtherModule(), FakeLoraLayer(names=("other",))])
    with pytest.raises(ConfigError, match="LoRA 層が 1 つも無い"):
        apply(model, 0.5)


def test_layers_without_the_adapter_are_skipped_and_not_counted() -> None:
    mixed = [FakeLoraLayer(), FakeLoraLayer(names=("other",))]
    assert apply(FakeModel(mixed), 0.5) == 1
    assert mixed[1].scaling["other"] == INITIAL_SCALING


# --------------------------------------------------------------------------
# 宣言の読み(重みを読む前に止まる)
# --------------------------------------------------------------------------


def sweep_declaration(levels: Any, adapter: str | None = "runs/x/adapter") -> dict[str, Any]:
    return {"eval": {"scale_sweep": {"levels": levels}}, "model": {"adapter": adapter}}


def test_no_declaration_means_the_model_is_not_touched() -> None:
    assert eval_model.declared_scale_sweep_levels({"eval": {}}) is None
    assert eval_model.declared_scale_sweep_levels({"eval": {"scale_sweep": None}}) is None
    assert eval_model.declared_scale_sweep_levels({}) is None


def test_the_levels_keep_the_declared_order() -> None:
    declared = eval_model.declared_scale_sweep_levels(sweep_declaration([1, 0, 0.5]))
    assert declared == (1.0, 0.0, 0.5)


@pytest.mark.parametrize(
    ("declaration", "match"),
    [
        (sweep_declaration([]), "水準のリスト"),
        (sweep_declaration(None), "水準のリスト"),
        (sweep_declaration("0.5"), "水準のリスト"),
        (sweep_declaration([0.5, 0.5]), "重なっている"),
        (sweep_declaration([0.5, 1.5]), "の外"),
        (sweep_declaration([True]), "スケール s"),
        (sweep_declaration([0.5], adapter=None), "null である"),
        ({"eval": {"scale_sweep": [0.5]}, "model": {"adapter": "x"}}, "形である"),
        ({"eval": {"scale_sweep": {"levels": [0.5], "extra": 1}}, "model": {"adapter": "x"}}, "未知の鍵"),
    ],
)
def test_a_broken_declaration_stops(declaration: dict[str, Any], match: str) -> None:
    with pytest.raises(ConfigError, match=match):
        eval_model.declared_scale_sweep_levels(declaration)


def test_the_level_label_is_a_safe_directory_name() -> None:
    labels = {s: scale_sweep.level_label(s) for s in (0.0, 0.5, 1.0, 0.25, 0.125)}
    assert labels == {0.0: "0", 0.5: "0p5", 1.0: "1", 0.25: "0p25", 0.125: "0p125"}


# --------------------------------------------------------------------------
# I7: 掃引の入口
# --------------------------------------------------------------------------


class FakeSession:
    """重みを読まない `ScaleSession` の置き物。どの s の下で何を解いたかを記録する。"""

    def __init__(self) -> None:
        self.current: float | None = None
        self.set_calls: list[float] = []
        self.solved_under: list[tuple[float | None, int]] = []
        self.session = scale_sweep.ScaleSession(set_scale=self._set_scale, generator=self._generate)

    def _set_scale(self, scale: float) -> int:
        self.current = scale
        self.set_calls.append(scale)
        return N_FAKE_LAYERS

    def _generate(self, prompts: Sequence[str]) -> list[str]:
        self.solved_under.append((self.current, len(prompts)))
        return [CONSTANT_RESPONSE for _ in prompts]


def train_run(root: Path, condition: str) -> Path:
    run_dir = root / "train_run"
    (run_dir / artifacts.ADAPTER_DIR).mkdir(parents=True, exist_ok=True)
    artifacts.write_metrics(
        run_dir,
        {"run_id": run_dir.name, "kind": "lora_train", "lesion_condition": condition, "seed": 0},
    )
    return run_dir / artifacts.ADAPTER_DIR


def sweep_config(
    pool_dirs: dict[str, Path], tmp: Path, *, levels: Sequence[float] = (0.0, 0.5, 1.0)
) -> dict[str, Any]:
    """パイロットの `ident` の評価 config を、掃引の宣言つきにしたもの(T1・T2 だけを解く)。"""
    config = config_at(PILOT_EVAL_IDENT, pool_dirs["pilot"])
    config["model"]["adapter"] = str(train_run(tmp, config["lesion"]["condition"]))
    config["eval"]["batteries"] = ["bare_sum", "word_problem"]
    config["eval"]["task_subset"] = ["t1", "t2"]
    config["eval"]["scale_sweep"] = {"levels": list(levels)}
    return config


def run_sweep(
    config: dict[str, Any], tmp: Path, session: FakeSession | None = None
) -> list[Path]:
    return scale_sweep.execute_scale_sweep(
        config,
        config_path=write_config(config, tmp / "config.yaml"),
        run_dir_prefix=tmp / "runs" / "sweep",
        session=(session or FakeSession()).session,
    )


def test_one_run_directory_per_level_in_the_declared_order(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    config = sweep_config(pool_dirs, tmp_path, levels=(1.0, 0.0, 0.5))
    fake = FakeSession()
    targets = run_sweep(config, tmp_path, fake)
    assert [path.name for path in targets] == ["sweep_s1", "sweep_s0", "sweep_s0p5"]
    assert fake.set_calls == [1.0, 0.0, 0.5]
    # 各水準の生成は、その水準の s が掛かっている間に行われた(掛け替えの後で解く)
    # 生成は採点バッチごとに呼ばれる。呼びの並びは s の水準の順にまとまり、水準ごとの合計は解く件数
    order = [scale for scale, _ in fake.solved_under]
    assert [scale for i, scale in enumerate(order) if i == 0 or scale != order[i - 1]] == [1.0, 0.0, 0.5]
    totals = {scale: sum(n for s, n in fake.solved_under if s == scale) for scale in (1.0, 0.0, 0.5)}
    assert totals == {1.0: N_SOLVED, 0.0: N_SOLVED, 0.5: N_SOLVED}
    for target, level in zip(targets, (1.0, 0.0, 0.5), strict=True):
        payload = read_metrics(target)
        assert payload["lora_scale"] == level
        assert payload["kind"] == run.EVAL_KIND
        assert payload["scale_sweep"]["levels"] == [1.0, 0.0, 0.5]
        assert payload["scale_sweep"]["n_lora_layers_scaled"] == N_FAKE_LAYERS
        assert (target / "config.yaml").is_file()
        assert (target / "log.txt").is_file()


def test_each_level_is_a_normal_four_way_decomposition_of_t1_and_t2_only(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    config = sweep_config(pool_dirs, tmp_path, levels=(0.5,))
    (target,) = run_sweep(config, tmp_path)
    payload = read_metrics(target)
    assert {batch["group"] for batch in payload["by_batch"].values()} == {
        "bare_sum",
        "word_problem",
    }
    for batch in payload["by_batch"].values():
        for block in batch["by_reference_rule"].values():
            total = (
                block["correct_rate"]
                + block["rule_rate"]
                + block["other_error_rate"]
                + block["parse_fail_rate"]
            )
            assert total == pytest.approx(1.0)
    assert payload["task_subset"]["task_types"] == ["t1", "t2"]
    assert payload["pool"]["n_items"] == N_SOLVED


def test_the_s_equal_one_run_matches_a_plain_evaluation_of_the_same_items(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★掃引の経路は、固定オフセットの評価(`run.execute`)と同じ関数で解いている。"""
    config = sweep_config(pool_dirs, tmp_path, levels=(1.0,))
    (swept,) = run_sweep(config, tmp_path)
    plain_config = {**config, "eval": {k: v for k, v in config["eval"].items() if k != "scale_sweep"}}
    plain = run.execute(
        plain_config,
        config_path=write_config(plain_config, tmp_path / "plain.yaml"),
        run_dir=tmp_path / "plain_run",
        generator=lambda prompts: [CONSTANT_RESPONSE for _ in prompts],
    )
    swept_payload, plain_payload = read_metrics(swept), read_metrics(plain)
    for key in ("by_batch", "pool", "task_subset", "coverage", "seed", "adapter", "elicitation"):
        assert swept_payload[key] == plain_payload[key], key
    assert "lora_scale" not in plain_payload  # 宣言の無い run の記録は 1 バイトも増えない


def test_the_gate_stops_a_non_ident_adapter_before_any_run_dir(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★D9: `p2`・`p2d` のアダプタは凍結の tag なしでは重みを読む前・run dir を作る前に止まる。"""
    config = sweep_config(pool_dirs, tmp_path)
    config["lesion"]["condition"] = "p2"
    config["model"]["adapter"] = str(train_run(tmp_path, "p2"))
    fake = FakeSession()
    with pytest.raises(ConfigError, match="ident"):
        run_sweep(config, tmp_path, fake)
    assert fake.set_calls == []
    assert not (tmp_path / "runs").exists()


def test_the_gate_opens_after_the_declared_tag_exists(
    pool_dirs: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = sweep_config(pool_dirs, tmp_path, levels=(0.5,))
    config["lesion"]["condition"] = "p2"
    config["model"]["adapter"] = str(train_run(tmp_path, "p2"))
    config["eval"]["freeze_tag"] = "preregister-test"
    monkeypatch.setattr(
        signature_gate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="preregister-test"),
    )
    (target,) = scale_sweep.execute_scale_sweep(
        config,
        config_path=write_config(config, tmp_path / "config.yaml"),
        run_dir_prefix=tmp_path / "runs" / "sweep",
        session=FakeSession().session,
    )
    assert read_metrics(target)["signature_gate"] == {
        "gate": signature_gate.REASON_FROZEN,
        "freeze_tag": "preregister-test",
    }


def test_the_gate_applies_even_when_only_s_equal_one_is_declared(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★s = 1 だけの掃引も入口で止める(止める側に倒した判断。モジュール冒頭)。"""
    config = sweep_config(pool_dirs, tmp_path, levels=(1.0,))
    config["lesion"]["condition"] = "p2"
    config["model"]["adapter"] = str(train_run(tmp_path, "p2"))
    with pytest.raises(ConfigError, match="ident"):
        run_sweep(config, tmp_path)


def test_a_sweep_without_the_t1_t2_subset_stops(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    config = sweep_config(pool_dirs, tmp_path)
    config["eval"]["task_subset"] = None
    with pytest.raises(ConfigError, match="task_subset"):
        run_sweep(config, tmp_path)
    config["eval"]["task_subset"] = ["t1", "t2", "t1_instructed"]
    config["eval"]["batteries"] = ["bare_sum", "word_problem", "bare_sum_instructed"]
    with pytest.raises(ConfigError, match="掃引の対象外"):
        run_sweep(config, tmp_path)
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize(
    ("key", "value", "match"),
    [
        ("threshold_sweep_arm", "r8", "threshold_sweep_arm"),
        ("composition", {"prompt_template": "{a}+{b}+{c}=", "n_per_cell": None}, "composition"),
    ],
)
def test_conflicting_declarations_stop(
    pool_dirs: dict[str, Path], tmp_path: Path, key: str, value: Any, match: str
) -> None:
    config = sweep_config(pool_dirs, tmp_path)
    config["eval"][key] = value
    with pytest.raises(ConfigError, match=match):
        run_sweep(config, tmp_path)
    assert not (tmp_path / "runs").exists()


def test_a_config_without_a_declaration_is_not_a_sweep(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    config = sweep_config(pool_dirs, tmp_path)
    config["eval"]["scale_sweep"] = None
    with pytest.raises(ConfigError, match="eval.scale_sweep を宣言した"):
        run_sweep(config, tmp_path)


def test_existing_records_are_not_overwritten(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    config = sweep_config(pool_dirs, tmp_path, levels=(0.5,))
    run_sweep(config, tmp_path)
    with pytest.raises(ConfigError, match="上書きしない"):
        run_sweep(config, tmp_path)


def test_the_fixed_offset_entrances_refuse_a_sweep_declaration(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★この経路で回すと宣言が黙って効かないまま s = 1 の run になる。"""
    config = sweep_config(pool_dirs, tmp_path)
    with pytest.raises(ConfigError, match="scale_sweep"):
        run.dry_run(config)
    with pytest.raises(ConfigError, match="scale_sweep"):
        run.execute(
            config,
            config_path=write_config(config, tmp_path / "config.yaml"),
            run_dir=tmp_path / "plain",
            generator=lambda prompts: [CONSTANT_RESPONSE for _ in prompts],
        )
    assert not (tmp_path / "plain").exists()


def test_the_dry_run_reports_and_writes_nothing(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    config = sweep_config(pool_dirs, tmp_path)
    report = scale_sweep.scale_sweep_dry_run(config, run_dir_prefix=tmp_path / "runs" / "sweep")
    assert report["levels"] == [0.0, 0.5, 1.0]
    assert [Path(path).name for path in report["run_dirs"]] == ["sweep_s0", "sweep_s0p5", "sweep_s1"]
    assert report["gate"]["gate"] == signature_gate.REASON_IDENT_ADAPTER
    assert report["task_subset"]["n_items"] == N_SOLVED
    assert not (tmp_path / "runs").exists()


def test_the_run_records_the_shared_load_and_the_log_names_the_scale(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    config = sweep_config(pool_dirs, tmp_path, levels=(0.0, 1.0))
    first, second = run_sweep(config, tmp_path)
    log = (first / "log.txt").read_text(encoding="utf-8")
    assert "LoRA のスケール s: 0.0" in log
    assert "D9 の門" in log
    payload = json.loads((second / "metrics.json").read_text(encoding="utf-8"))
    assert payload["scale_sweep"]["shared_model_load_seconds"] >= 0.0


# --------------------------------------------------------------------------
# I8: 主解析に混ざらない守り(PLAN-037 §3.3 の 2)
# --------------------------------------------------------------------------


def scaled_metrics(run_id: str, scale: Any, seed: int = 0) -> dict[str, Any]:
    payload = eval_metrics(run_id=run_id, condition="ident", seed=seed, adapter="x")
    if scale != "absent":
        payload["lora_scale"] = scale
    return payload


def test_the_frame_stops_on_a_run_with_s_other_than_one(tmp_path: Path) -> None:
    for scale in (0.0, 0.5, 0.999):
        run_dir = write_run(tmp_path, f"s{scale}", scaled_metrics("r", scale))
        with pytest.raises(frame.FrameError, match="lora_scale"):
            frame.load_run(run_dir / "metrics.json")


@pytest.mark.parametrize("scale", [1, 1.0, None, "absent"])
def test_the_frame_does_not_stop_on_s_equal_one_or_no_record(tmp_path: Path, scale: Any) -> None:
    """★記録の無い過去の run と s = 1 は同じ(アダプタそのもの)。s の守りは通り、次の検査(config.yaml)へ進む。"""
    run_dir = write_run(tmp_path, "plain", scaled_metrics("r", scale))
    with pytest.raises(frame.FrameError, match="config.yaml が無い"):
        frame.load_run(run_dir / "metrics.json")


def test_the_aggregation_separates_rows_by_s_and_warns(tmp_path: Path) -> None:
    write_run(tmp_path, "a", scaled_metrics("a", "absent", seed=0))
    write_run(tmp_path, "b", scaled_metrics("b", 1.0, seed=1))
    write_run(tmp_path, "c", scaled_metrics("c", 0.5, seed=0))
    collection = aggregate.collect(aggregate.expand_metrics_paths([str(tmp_path / "*")]))
    cells = {cell.lora_scale: cell for cell in collection.cells}
    assert set(cells) == {None, 0.5}
    assert {row.run_id for row in cells[None].rows} == {"a", "b"}  # s = 1 と無記録は同じ行
    assert [row.run_id for row in cells[0.5].rows] == ["c"]
    lines = aggregate.report_lines(collection)
    assert any("s ≠ 1" in line for line in lines)
    assert any("s=0.5" in line for line in lines)
    exported = collection.as_dict()["cells"]
    assert [cell.get("lora_scale") for cell in exported] == [None, 0.5]


def test_a_collection_without_any_s_is_byte_identical_to_before(tmp_path: Path) -> None:
    """★過去の run の集約は 1 文字も変わらない(s の語・欄が出ない)。"""
    write_run(tmp_path, "a", scaled_metrics("a", "absent", seed=0))
    write_run(tmp_path, "b", scaled_metrics("b", 1.0, seed=1))
    collection = aggregate.collect(aggregate.expand_metrics_paths([str(tmp_path / "*")]))
    text = "\n".join(aggregate.report_lines(collection))
    assert " s=" not in text and "s ≠ 1" not in text
    exported = json.dumps(collection.as_dict(), ensure_ascii=False)
    assert "lora_scale" not in exported


def test_a_sweep_run_is_stopped_by_the_aggregation_through_its_task_subset(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★掃引の run は T1・T2 に絞った run でもある。`task_subset` を宣言した run は集約が止める(ADR-087)。"""
    config = sweep_config(pool_dirs, tmp_path, levels=(0.5,))
    (target,) = run_sweep(config, tmp_path)
    with pytest.raises(aggregate.AggregateError, match="task_subset"):
        aggregate.collect([target / "metrics.json"])
