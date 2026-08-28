"""訓練の実行経路(code/train/run.py)のテスト。

答える問い: 「重みを読まずに、訓練の配線と `runs/<id>/` の中身を検査できるか。
config の門と重みの読み込みが、来歴を書く前と後に正しく分かれているか」

**モデルの重みは1度も読まない。**`execute` は `trainer` を差し替えられる
ので、偽の訓練関数を渡す(`code/eval/run.py` の `generator` と同じ作り)。
**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.config import ConfigError, load_config
from code.data_gen import ft_data
from code.train import lora
from code.train import run as train_run
from code.train.data import TrainingExample

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

SMOKE_CONDITIONS: tuple[str, ...] = ("p2", "x2", "ident")
SMOKE_SEED = 0

# **実験条件ではない。**smoke config は model.name / revision を null に
# してあるので、本実行の経路まで到達させるためにテスト側で埋める。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40
# smoke config は device を持たない(あちらは編集してはならない。ADR-037 決定4)。
# **実験条件の宣言ではない** —— この経路は偽の訓練関数で回り、重みを読まない
TEST_DEVICE = "cpu"

# 偽の訓練関数が返す損失。**モデルの振る舞いではない。**
FAKE_LOSSES = (1.0, 0.5)


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)の呼び出しを止める。

    来歴の**中身**は code/tests/test_artifacts.py が実物で検査する。
    """
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


@pytest.fixture
def workspace(tmp_path: Path) -> dict[str, Any]:
    """3条件の FT データを書き出し、それを指す config をファイルに置く。"""
    config = load_config(SMOKE_CONFIG)
    manifests: list[str] = []
    for condition in SMOKE_CONDITIONS:
        variant = load_config(SMOKE_CONFIG)
        variant["lesion"]["condition"] = condition
        out_dir = tmp_path / f"ft_{condition}"
        ft_data.write_dataset(ft_data.generate(variant), out_dir)
        manifests.append(str(out_dir / "manifest.json"))
    config["data"]["matched_manifests"] = manifests
    config["model"]["name"] = TEST_MODEL
    config["model"]["revision"] = TEST_REVISION
    config["model"]["device"] = TEST_DEVICE
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return {
        "config": config,
        "config_path": config_path,
        "run_dir": tmp_path / "run",
        "root": tmp_path,
    }


def recording_trainer(seen: list[Sequence[TrainingExample]]) -> lora.Trainer:
    """渡された例を記録し、設定どおりの記録を返す偽の訓練関数。"""

    def trainer(examples: Sequence[TrainingExample]) -> lora.TrainOutcome:
        seen.append(list(examples))
        return lora.TrainOutcome(
            n_steps=len(FAKE_LOSSES),
            n_examples_consumed=4,
            losses=FAKE_LOSSES,
            trainable_parameters=128,
            adapter_dir=None,
        )

    return trainer


# --------------------------------------------------------------------------
# --dry-run(重みを読まない)
# --------------------------------------------------------------------------


def test_dry_run_passes_without_the_model_being_declared(workspace: dict[str, Any]) -> None:
    """★model.name が null でも配線確認は通ること。

    ADR-031 により revision は pull 時に埋まる。配線確認の時点で null なのは
    正しい記録である(code/eval/run.py の --dry-run と同じ扱い)。
    """
    config = workspace["config"]
    config["model"]["name"] = None
    config["model"]["revision"] = None
    report = train_run.dry_run(config, seed=SMOKE_SEED)
    assert report["model"]["name"] is None
    assert report["data"]["condition"] == "p2"
    assert report["train"]["seed"] == SMOKE_SEED


def test_dry_run_reports_the_consumption_plan(workspace: dict[str, Any]) -> None:
    """消費順の計画が報告に出ること(シードが効いていることが見える)。"""
    report = train_run.dry_run(workspace["config"], seed=SMOKE_SEED)
    settings = report["train"]
    assert report["plan"]["n_micro_batches"] == (
        settings["num_steps"] * settings["gradient_accumulation"]
    )
    assert len(report["plan"]["first_micro_batch"]) == settings["batch_size"]
    assert report["plan"]["epochs_consumed"] > 0


def test_dry_run_says_the_chat_template_was_not_applied(workspace: dict[str, Any]) -> None:
    """★「配線が通った」を「入力文字列が正しい」と読ませないこと。

    テンプレートの適用にはトークナイザが要る。--dry-run は読まない。
    """
    report = train_run.dry_run(workspace["config"], seed=SMOKE_SEED)
    assert "チャットテンプレート" in report["first_example"]["note"]


def test_dry_run_stops_on_an_undecided_lora_grid(workspace: dict[str, Any]) -> None:
    """★LoRA グリッドが null なら配線確認も通らないこと(PLAN-003 §9)。"""
    config = workspace["config"]
    config["train"]["lora"]["rank"] = None
    with pytest.raises(ConfigError, match="rank"):
        train_run.dry_run(config, seed=SMOKE_SEED)


def test_dry_run_rejects_a_run_dir() -> None:
    """--dry-run は何も書かない。--run-dir を黙って無視しないこと。"""
    with pytest.raises(SystemExit):
        train_run.main(
            [
                "--config",
                str(SMOKE_CONFIG),
                "--seed",
                str(SMOKE_SEED),
                "--dry-run",
                "--run-dir",
                "runs/does_not_matter",
            ]
        )


# --------------------------------------------------------------------------
# 本実行(門と重みの読み込みの順序、差し替えた訓練関数)
# --------------------------------------------------------------------------


def test_a_rejected_config_leaves_no_run_dir(workspace: dict[str, Any]) -> None:
    """★config の門は run ディレクトリを作る前に掛かること(8-6 の (d))。

    拒否された実行のために runs/<id>/ を作ると、中身の無いディレクトリだけが増える。
    """
    config = workspace["config"]
    config["train"]["lora"]["rank"] = None
    run_dir = workspace["run_dir"]
    with pytest.raises(ConfigError, match="rank"):
        train_run.execute(
            config,
            config_path=workspace["config_path"],
            run_dir=run_dir,
            seed=SMOKE_SEED,
        )
    assert not run_dir.exists()


def test_the_provenance_is_written_before_the_weights_are_read(
    workspace: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """★重みの読み込みで落ちても来歴が残ること(8-6 の (d))。

    8B の読み込みは分単位で、落ちうる。そこで落ちたときに何も残らないと、
    **「どの版で何を試したのか」が後から言えない。**
    """

    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("重みが読めなかった(テスト)")

    monkeypatch.setattr(train_run.lora, "build_trainer", explode)
    run_dir = workspace["run_dir"]
    with pytest.raises(RuntimeError, match="重みが読めなかった"):
        train_run.execute(
            workspace["config"],
            config_path=workspace["config_path"],
            run_dir=run_dir,
            seed=SMOKE_SEED,
        )
    for name in ("config.yaml", "git_sha.txt", "env.txt"):
        assert (run_dir / name).is_file()
    # 訓練は始まっていないので、結果の側は書かれていない
    assert not (run_dir / "metrics.json").exists()


def test_the_trainer_is_given_the_run_dir_as_the_adapter_destination(
    workspace: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """★アダプタの保存先は `runs/<id>/adapter/` であること(ADR-043 決定2)。"""
    seen: dict[str, Any] = {}

    def capture(settings: Any, **kwargs: Any) -> lora.Trainer:
        seen.update(kwargs)
        return recording_trainer([])

    monkeypatch.setattr(train_run.lora, "build_trainer", capture)
    target = train_run.execute(
        workspace["config"],
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        seed=SMOKE_SEED,
    )
    assert seen["adapter_dir"] == target / artifacts.ADAPTER_DIR
    # ★載せるデバイスも渡ること(ADR-040 決定4)。既定値を置くと黙って CPU に載る
    assert seen["device"] == TEST_DEVICE


def test_the_trainer_receives_the_canonical_order(workspace: dict[str, Any]) -> None:
    """★訓練関数には train.jsonl の順序のまま渡ること。

    並べ替えは消費順の計画(code/train/lora.py)の責務であり、
    データファイルの順序は条件間のバイト一致の土台である(PLAN-002 §3.4)。
    """
    seen: list[Sequence[TrainingExample]] = []
    train_run.execute(
        workspace["config"],
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        seed=SMOKE_SEED,
        trainer=recording_trainer(seen),
    )
    (examples,) = seen
    raw_path = workspace["root"] / "ft_p2" / "train.jsonl"
    raw = [
        json.loads(line)
        for line in raw_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [example.example_id for example in examples] == [row["example_id"] for row in raw]


def test_the_run_dir_has_the_required_artifacts(workspace: dict[str, Any]) -> None:
    """infra/RUNPOD.md §4「必ず残すもの」のうち、訓練が書く分がそろうこと。

    `predictions/` は評価の成果物であり、訓練は書かない。
    `cost.txt` は人間が、`token_boundary.json` は preflight が書く。
    """
    target = train_run.execute(
        workspace["config"],
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        seed=SMOKE_SEED,
        trainer=recording_trainer([]),
    )
    required = (
        "config.yaml",
        "git_sha.txt",
        "env.txt",
        "timestamp.txt",
        "metrics.json",
        "log.txt",
    )
    for name in required:
        assert (target / name).exists(), name


def test_metrics_records_the_condition_the_seed_and_the_data(workspace: dict[str, Any]) -> None:
    """★条件・シード・データの来歴が metrics.json だけで言えること。"""
    target = train_run.execute(
        workspace["config"],
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        seed=SMOKE_SEED,
        trainer=recording_trainer([]),
    )
    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    assert payload["kind"] == train_run.TRAIN_KIND
    assert payload["lesion_condition"] == "p2"
    assert payload["seed"] == SMOKE_SEED
    assert payload["model"]["revision"] == TEST_REVISION
    assert payload["data"]["n_examples"] > 0
    assert payload["outcome"]["adapter_dir"] is None
    assert payload["train"]["lora"]["target"] in lora.TARGET_MODULES


def test_metrics_does_not_carry_a_four_value_breakdown(workspace: dict[str, Any]) -> None:
    """★訓練は採点しないこと(skill code-style §2)。

    4値分解は code.eval.run が別の run に書く。ここに混ぜると、
    「訓練の run に評価の数値がある」記録ができてしまう。
    """
    target = train_run.execute(
        workspace["config"],
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        seed=SMOKE_SEED,
        trainer=recording_trainer([]),
    )
    text = (target / "metrics.json").read_text(encoding="utf-8")
    for field in ("correct_rate", "rule_rate", "other_error_rate", "parse_fail_rate"):
        assert field not in text


def test_a_trainer_that_reports_the_wrong_steps_stops_the_run(workspace: dict[str, Any]) -> None:
    """★設定と違う回数を報告する訓練関数を通さないこと(CLAUDE.md §7)。"""

    def liar(examples: Sequence[TrainingExample]) -> lora.TrainOutcome:
        return lora.TrainOutcome(
            n_steps=999,
            n_examples_consumed=0,
            losses=(0.0,) * 999,
            trainable_parameters=None,
            adapter_dir=None,
        )

    with pytest.raises(lora.TrainerContractError):
        train_run.execute(
            workspace["config"],
            config_path=workspace["config_path"],
            run_dir=workspace["run_dir"],
            seed=SMOKE_SEED,
            trainer=liar,
        )


def test_an_undeclared_seed_stops_the_run(workspace: dict[str, Any]) -> None:
    """★config の seeds に無いシードでは回らないこと。"""
    with pytest.raises(ConfigError, match="seeds"):
        train_run.execute(
            workspace["config"],
            config_path=workspace["config_path"],
            run_dir=workspace["run_dir"],
            seed=7,
            trainer=recording_trainer([]),
        )


def test_the_log_names_the_adapter_destination(workspace: dict[str, Any]) -> None:
    """★アダプタの保存先を必ず1行出すこと。

    None のまま気づかずに終わると、学習した重みが消えたことに後から気づく。
    """
    target = train_run.execute(
        workspace["config"],
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        seed=SMOKE_SEED,
        trainer=recording_trainer([]),
    )
    log = (target / "log.txt").read_text(encoding="utf-8")
    assert "アダプタ: None" in log
    assert "format_hash" in log


def test_the_config_copy_is_the_file_itself(workspace: dict[str, Any]) -> None:
    """使用した設定は再 dump ではなくファイルの複製であること(注記が落ちない)。"""
    target = train_run.execute(
        workspace["config"],
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        seed=SMOKE_SEED,
        trainer=recording_trainer([]),
    )
    assert (target / "config.yaml").read_text(encoding="utf-8") == workspace[
        "config_path"
    ].read_text(encoding="utf-8")
