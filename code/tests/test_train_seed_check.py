"""★E の確かめの入口(code/train/seed_check.py。PLAN-031 §3.6)。

答える問い: 「確かめの CLI は、本番と同じ経路で・シードごとに土台を読み直して・食い違いを
見逃さずに判定し、結果を残すか」

**本物の peft は使わない**(ローカルに無い)。土台を書き換えて LoRA の A を引く**偽の peft**
(`install_fake_peft`)で、CLI の配線・判定・記録の形を縛る。**本物の peft が初期値を種だけで
決めるか・アダプタが fp32 に上がるかは、このテストでは分からない** —— それを見るための入口が
`seed_check.py` であり、ポッド上で走らせる(RUNNER)。
偽の peft は「種に反応しない」「種付けされない」故障も再現でき、確かめがそれを落とすことを縛る。
torch に依る項目は `pytest.importorskip("torch")` で飛ばせる(`test_train_seeding.py` と同じ作法)。

**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

import json
import sys
import types
from collections.abc import Callable
from importlib import metadata
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.config import ConfigError, load_config
from code.tests import test_train_seeding as seeding_tests
from code.train import lora, seed_check, seeding
from code.train.seed_check import SeedProbe

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# **実験条件ではない。**smoke config は model.name / revision / device を持たない(または null)ので、
# 本実行の経路まで到達させるためにテスト側で埋める(`test_train_run.py` と同じ)。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40
TEST_DEVICE = "cpu"
TEST_SEEDS = [0, 1]
FAKE_VERSIONS = {"torch": "0.0-test", "transformers": "0.0-test", "peft": "0.0-test"}
FAKE_IN, FAKE_OUT = 4, 3  # 偽の LoRA の A の形(意味の無い大きさ)
FIXED_GENERATOR_SEED = 123  # 「種に反応しない peft」が使う自前の乱数の種


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)の呼び出しを止める(`test_train_run.py` と同じ)。"""
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


# --------------------------------------------------------------------------
# 偽の peft(土台を書き換える。LoRA の A の引き元を選べる)
# --------------------------------------------------------------------------


class FakeBase:
    """peft が書き換える土台の偽物。`injected` に、LoRA を挿された回数を残す。"""

    def __init__(self) -> None:
        self.injected = 0


def install_fake_peft(
    monkeypatch: pytest.MonkeyPatch,
    events: list[Any],
    *,
    source: str = "global",
    adapter_dtype: Any = None,
) -> None:
    """`peft` を偽物に差し替える。`get_peft_model` は渡された土台を**書き換えて**返す。

    `source`: LoRA の A をどこから引くか。
      global   : torch のグローバル乱数(本物と同じ。`seed_all` で決まる)
      fixed    : 自前の乱数を固定の種で(**種に反応しない peft**。★E の故障の 1 つ)
      unseeded : 自前の乱数を毎回違う種で(**種付けが効かない peft**。★E の故障のもう 1 つ)
    """
    import torch  # noqa: PLC0415

    class FakePeftModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.lora_A = torch.nn.Linear(FAKE_IN, FAKE_OUT, bias=False)
            self.lora_B = torch.nn.Linear(FAKE_OUT, FAKE_IN, bias=False)
            torch.nn.init.zeros_(self.lora_B.weight)
            if source != "global":
                generator = torch.Generator()
                if source == "fixed":
                    generator.manual_seed(FIXED_GENERATOR_SEED)
                else:
                    generator.seed()  # 非決定的な種
                with torch.no_grad():
                    self.lora_A.weight.copy_(torch.rand(FAKE_OUT, FAKE_IN, generator=generator))
            if adapter_dtype is not None:
                self.to(adapter_dtype)

    def get_peft_model(base: FakeBase, config: Any) -> Any:
        del config
        events.append(("get_peft_model", base.injected))  # 挿される前に、土台が新しいか
        base.injected += 1
        return FakePeftModel()

    fake_peft = types.ModuleType("peft")
    fake_peft.get_peft_model = get_peft_model  # type: ignore[attr-defined]
    fake_peft.LoraConfig = lambda **kwargs: kwargs  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "peft", fake_peft)


def counting_loader(events: list[Any]) -> Callable[[], FakeBase]:
    """土台を読む関数(読むたびに新しい `FakeBase`)。呼ばれたことを控える。"""

    def load() -> FakeBase:
        events.append("load")
        return FakeBase()

    return load


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """偽の peft を入れ、種付けと GPU メモリの解放の呼び出しを控える(torch が無ければ飛ばす)。"""
    pytest.importorskip("torch")
    calls: list[Any] = []
    install_fake_peft(monkeypatch, calls)
    real_seed_all = seeding.seed_all

    def seed_all(seed: int) -> dict[str, Any]:
        calls.append(("seed_all", seed))
        return real_seed_all(seed)

    monkeypatch.setattr(seeding, "seed_all", seed_all)
    monkeypatch.setattr(seed_check, "release_accelerator_memory", lambda: calls.append("release"))
    return calls


def probes_for(seeds: list[int], loader: Callable[[], Any]) -> list[SeedProbe]:
    settings = [seeding_tests.settings_with(seed=seed) for seed in seeds]
    return seed_check.run_probes(settings, load_base=loader)


# --------------------------------------------------------------------------
# 並びの検査(torch 不要)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seeds", "message"),
    [
        ([0, 1], "同じ種が 2 回以上"),
        ([0, 1, 2], "同じ種が 2 回以上"),
        ([0, 0], "相異なる種"),
        ([3], "相異なる種"),
    ],
)
def test_a_sequence_that_cannot_fail_is_refused(seeds: list[int], message: str) -> None:
    """★同じ種の対か違う種の対のどちらかが無い並びは、確かめられない性質を「通った」と出す。"""
    with pytest.raises(seed_check.SeedCheckError, match=message):
        seed_check.validate_seeds(seeds)


@pytest.mark.parametrize("seeds", [[0, 0, 1], [0, 1, 0], [0, 0, 1, 1]])
def test_a_sequence_with_a_repeat_and_two_seeds_is_accepted(seeds: list[int]) -> None:
    seed_check.validate_seeds(seeds)


# --------------------------------------------------------------------------
# 判定(torch 不要)
# --------------------------------------------------------------------------

SHA_A, SHA_B, SHA_C = "a" * 64, "b" * 64, "c" * 64


def probe(position: int, seed: int, sha: str, dtypes: tuple[str, ...] = ("float32",)) -> SeedProbe:
    return SeedProbe(
        position=position,
        seed=seed,
        adapter_init_sha256=sha,
        adapter_param_dtypes=dtypes,
        seeding=seeding.seeding_plan(seed),
    )


def test_the_verdict_passes_when_the_same_seed_matches_and_another_seed_differs() -> None:
    verdict = seed_check.judge(
        [probe(0, 0, SHA_A), probe(1, 0, SHA_A), probe(2, 1, SHA_B)], declared_dtype="float32"
    )
    assert verdict.passed and verdict.problems == ()
    assert [(p.earlier, p.later, p.equal) for p in verdict.same_seed] == [(0, 1, True)]
    assert [(p.earlier, p.later, p.equal) for p in verdict.different_seed] == [(0, 2, False)]


def test_the_verdict_stops_on_a_same_seed_mismatch() -> None:
    """★同じ種なのに指紋が違えば、★E は直っていない。"""
    verdict = seed_check.judge(
        [probe(0, 0, SHA_A), probe(1, 0, SHA_B), probe(2, 1, SHA_C)], declared_dtype="float32"
    )
    assert not verdict.passed
    assert len(verdict.problems) == 1
    assert "同じ種 0 なのに指紋が違う" in verdict.problems[0]
    assert "実行 1 と 2" in verdict.problems[0]


def test_the_verdict_stops_on_a_different_seed_collision() -> None:
    """★違う種なのに指紋が同じなら、初期値は種に反応していない。"""
    verdict = seed_check.judge(
        [probe(0, 0, SHA_A), probe(1, 0, SHA_A), probe(2, 1, SHA_A)], declared_dtype="float32"
    )
    assert not verdict.passed
    assert len(verdict.problems) == 1
    assert "違う種 0 と 1 なのに指紋が同じ" in verdict.problems[0]


def test_each_run_is_compared_with_the_first_run_of_every_seed() -> None:
    """並びが 0 1 0 のとき: 同じ種 = (1-3)、違う種 = (1-2) と (2-3)。"""
    verdict = seed_check.judge(
        [probe(0, 0, SHA_A), probe(1, 1, SHA_B), probe(2, 0, SHA_A)], declared_dtype="float32"
    )
    assert verdict.passed
    assert [(p.earlier, p.later) for p in verdict.same_seed] == [(0, 2)]
    assert [(p.earlier, p.later) for p in verdict.different_seed] == [(0, 1), (1, 2)]


def test_a_third_run_of_the_same_seed_is_compared_with_the_first() -> None:
    verdict = seed_check.judge(
        [probe(0, 0, SHA_A), probe(1, 0, SHA_A), probe(2, 0, SHA_B), probe(3, 1, SHA_C)],
        declared_dtype="float32",
    )
    assert [(p.earlier, p.later, p.equal) for p in verdict.same_seed] == [
        (0, 1, True),
        (0, 2, False),
    ]
    assert not verdict.passed


def test_the_verdict_does_not_pass_a_property_it_did_not_check() -> None:
    """★同じ種の対が無い(または違う種の対が無い)のに「通った」を出さない。"""
    only_repeat = seed_check.judge(
        [probe(0, 0, SHA_A), probe(1, 0, SHA_A)], declared_dtype="float32"
    )
    assert not only_repeat.passed
    assert any("違う種の対が無い" in problem for problem in only_repeat.problems)
    only_distinct = seed_check.judge(
        [probe(0, 0, SHA_A), probe(1, 1, SHA_B)], declared_dtype="float32"
    )
    assert not only_distinct.passed
    assert any("同じ種の対が無い" in problem for problem in only_distinct.problems)


@pytest.mark.parametrize("observed", [("bfloat16",), ("bfloat16", "float32"), ()])
def test_the_dtype_is_judged_by_the_gate_that_training_uses(observed: tuple[str, ...]) -> None:
    """★訓練が使う `check_adapter_dtype` と同じ判定。食い違った実行を 1 つずつ数える。"""
    verdict = seed_check.judge(
        [probe(0, 0, SHA_A), probe(1, 0, SHA_A, observed), probe(2, 1, SHA_B)],
        declared_dtype="float32",
    )
    assert not verdict.passed
    assert len(verdict.problems) == 1
    assert verdict.problems[0].startswith("実行 2:")
    assert "adapter_dtype" in verdict.problems[0]


def payload_for(probes: list[SeedProbe], verdict: seed_check.Verdict) -> dict[str, Any]:
    config = load_config(SMOKE_CONFIG)
    config["seeds"] = TEST_SEEDS
    config["model"].update({"name": TEST_MODEL, "revision": TEST_REVISION, "device": TEST_DEVICE})
    settings = [seeding_tests.settings_with(seed=p.seed) for p in probes]
    return seed_check.result_payload(config, settings, probes, verdict, libraries=FAKE_VERSIONS)


def test_the_report_prints_the_full_fingerprints_and_every_problem() -> None:
    probes = [probe(0, 0, SHA_A), probe(1, 0, SHA_B), probe(2, 1, SHA_C, ("bfloat16",))]
    verdict = seed_check.judge(probes, declared_dtype="float32")
    text = "\n".join(seed_check.report_lines(payload_for(probes, verdict)))
    for sha in (SHA_A, SHA_B, SHA_C):
        assert sha in text  # 切り詰めない(プロセスをまたぐ一致は目で比べる)
    assert "**通らなかった**" in text
    assert text.count("  - ") == len(verdict.problems) == 2
    assert "実験結果ではない" in text


def test_the_report_says_passed_only_when_nothing_is_wrong() -> None:
    probes = [probe(0, 0, SHA_A), probe(1, 0, SHA_A), probe(2, 1, SHA_B)]
    verdict = seed_check.judge(probes, declared_dtype="float32")
    text = "\n".join(seed_check.report_lines(payload_for(probes, verdict)))
    assert "判定: 通った" in text
    assert "通らなかった" not in text


# --------------------------------------------------------------------------
# 配線(偽の peft)
# --------------------------------------------------------------------------


def test_every_seed_reloads_a_fresh_base_and_frees_memory_before_the_next(
    events: list[Any],
) -> None:
    """★peft は土台を書き換える前提。シードごとに読み直し、次を読む前に前のものを外す。"""
    probes_for([0, 0, 1], counting_loader(events))
    assert events == [
        "load", ("seed_all", 0), ("get_peft_model", 0), "release",
        "load", ("seed_all", 0), ("get_peft_model", 0), "release",
        "load", ("seed_all", 1), ("get_peft_model", 0), "release",
    ]  # fmt: skip


def test_a_reused_base_would_be_seen_by_the_fake(events: list[Any]) -> None:
    """偽の peft が「土台を書き換えた」ことを見せる(これが無いと、上の読み直しの検査は空振りする)。"""
    shared = FakeBase()
    probes_for([0, 0], lambda: shared)
    assert [e for e in events if isinstance(e, tuple) and e[0] == "get_peft_model"] == [
        ("get_peft_model", 0),
        ("get_peft_model", 1),
    ]


def test_the_check_passes_when_peft_draws_from_the_seeded_global_rng(events: list[Any]) -> None:
    probes = probes_for([0, 0, 1], counting_loader(events))
    assert probes[0].adapter_init_sha256 == probes[1].adapter_init_sha256
    assert probes[0].adapter_init_sha256 != probes[2].adapter_init_sha256
    assert probes[0].adapter_param_dtypes == ("float32",)
    assert [p.seeding["value"] for p in probes] == [0, 0, 1]
    assert seed_check.judge(probes, declared_dtype="float32").passed


def test_the_check_catches_a_peft_that_ignores_the_seed(
    monkeypatch: pytest.MonkeyPatch, events: list[Any]
) -> None:
    """★★E の故障 1: peft が自前の固定の乱数を使えば、種を変えても初期値は変わらない。"""
    install_fake_peft(monkeypatch, events, source="fixed")
    probes = probes_for([0, 0, 1], counting_loader(events))
    verdict = seed_check.judge(probes, declared_dtype="float32")
    assert not verdict.passed
    assert any("違う種 0 と 1 なのに指紋が同じ" in problem for problem in verdict.problems)


def test_the_check_catches_a_peft_that_is_not_reproduced_by_the_seed(
    monkeypatch: pytest.MonkeyPatch, events: list[Any]
) -> None:
    """★★E の故障 2: peft が種付けの効かない乱数を使えば、同じ種でも初期値は変わる。"""
    install_fake_peft(monkeypatch, events, source="unseeded")
    probes = probes_for([0, 0, 1], counting_loader(events))
    verdict = seed_check.judge(probes, declared_dtype="float32")
    assert not verdict.passed
    assert any("同じ種 0 なのに指紋が違う" in problem for problem in verdict.problems)


def test_the_check_reports_a_peft_that_leaves_the_adapter_in_bf16(
    monkeypatch: pytest.MonkeyPatch, events: list[Any]
) -> None:
    """★f′ の食い違い(peft が fp32 に上げない)。訓練は止まるが、確かめは指紋も含めて全部見せる。"""
    torch = pytest.importorskip("torch")
    install_fake_peft(monkeypatch, events, adapter_dtype=torch.bfloat16)
    probes = probes_for([0, 0, 1], counting_loader(events))
    verdict = seed_check.judge(probes, declared_dtype="float32")
    assert probes[0].adapter_init_sha256 == probes[1].adapter_init_sha256  # 指紋は取れている
    assert not verdict.passed
    assert len(verdict.problems) == 3  # 3 回とも
    assert all("bfloat16" in problem for problem in verdict.problems)


def test_the_check_and_training_go_through_the_same_insertion_function(
    monkeypatch: pytest.MonkeyPatch, events: list[Any], tmp_path: Path
) -> None:
    """★確かめだけ別の経路で種付けすると、本番が壊れていても確かめが通る。"""
    seen: list[str] = []
    real = lora.insert_seeded_adapter

    def spy(base: Any, settings: Any) -> lora.InsertedAdapter:
        seen.append(f"seed={settings.seed}")
        return real(base, settings)

    monkeypatch.setattr(lora, "insert_seeded_adapter", spy)
    probes_for([0], counting_loader(events))
    assert seen == ["seed=0"]

    # 訓練の経路(`test_train_seeding.py` の偽の peft・偽のトークナイザ)も同じ関数を通る
    seeding_tests.install_fake_peft(monkeypatch, [])
    seeding_tests.train_once(tmp_path, "a", seeding_tests.settings_with(seed=2))
    assert seen == ["seed=0", "seed=2"]


# --------------------------------------------------------------------------
# execute / main(結果を残す)
# --------------------------------------------------------------------------


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    config = load_config(SMOKE_CONFIG)
    config["seeds"] = TEST_SEEDS
    config["model"].update({"name": TEST_MODEL, "revision": TEST_REVISION, "device": TEST_DEVICE})
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def stub_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed_check, "library_versions", lambda: dict(FAKE_VERSIONS))


def test_execute_writes_the_result_and_returns_zero_when_it_passes(
    events: list[Any], stub_versions: None, config_path: Path, tmp_path: Path
) -> None:
    run_dir = tmp_path / "run"
    code = seed_check.execute(
        load_config(config_path),
        config_path=config_path,
        run_dir=run_dir,
        seeds=[0, 0, 1],
        load_base=counting_loader(events),
    )
    assert code == 0
    payload = json.loads((run_dir / seed_check.RESULT_FILE).read_text(encoding="utf-8"))
    assert payload["kind"] == "seed_check"
    assert payload["seeds"] == [0, 0, 1]
    assert payload["libraries"] == FAKE_VERSIONS
    assert payload["model"]["name"] == TEST_MODEL and payload["model"]["revision"] == TEST_REVISION
    assert payload["declared"]["adapter_dtype"] == "float32"
    assert payload["verdict"]["passed"] is True
    shas = [p["adapter_init_sha256"] for p in payload["probes"]]
    assert shas[0] == shas[1] != shas[2]
    assert "実験結果ではない" in payload["note"]
    # 来歴と log が揃い、run と取り違えられる名前(metrics.json)は作らない
    for name in ("config.yaml", "git_sha.txt", "env.txt", "log.txt", "timestamp.txt"):
        assert (run_dir / name).is_file(), name
    assert not (run_dir / "metrics.json").exists()
    assert shas[0] in (run_dir / "log.txt").read_text(encoding="utf-8")


def test_execute_records_a_failed_check_and_returns_one(
    monkeypatch: pytest.MonkeyPatch,
    events: list[Any],
    stub_versions: None,
    config_path: Path,
    tmp_path: Path,
) -> None:
    """★通らなかった確かめも記録する(食い違いは記録に値する)。終了コードは 1。"""
    install_fake_peft(monkeypatch, events, source="fixed")
    run_dir = tmp_path / "run"
    code = seed_check.execute(
        load_config(config_path),
        config_path=config_path,
        run_dir=run_dir,
        seeds=[0, 0, 1],
        load_base=counting_loader(events),
    )
    assert code == 1
    payload = json.loads((run_dir / seed_check.RESULT_FILE).read_text(encoding="utf-8"))
    assert payload["verdict"]["passed"] is False
    assert payload["verdict"]["problems"]


def test_execute_records_the_provenance_before_loading_any_weights(
    stub_versions: None, config_path: Path, tmp_path: Path
) -> None:
    """★読み込みの途中で落ちても、どの版で何を試したかが残る。"""
    run_dir = tmp_path / "run"

    def explode() -> Any:
        raise RuntimeError("読み込みで落ちた")

    with pytest.raises(RuntimeError, match="読み込みで落ちた"):
        seed_check.execute(
            load_config(config_path),
            config_path=config_path,
            run_dir=run_dir,
            seeds=[0, 0, 1],
            load_base=explode,
        )
    for name in ("config.yaml", "git_sha.txt", "env.txt"):
        assert (run_dir / name).is_file(), name
    assert not (run_dir / seed_check.RESULT_FILE).exists()


def test_execute_does_not_overwrite_an_existing_record(
    stub_versions: None, config_path: Path, tmp_path: Path
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / seed_check.RESULT_FILE).write_text("{}", encoding="utf-8")

    def never() -> Any:
        raise AssertionError("重みを読んではならない")

    with pytest.raises(seed_check.SeedCheckError, match="上書きしない"):
        seed_check.execute(
            load_config(config_path),
            config_path=config_path,
            run_dir=run_dir,
            seeds=[0, 0, 1],
            load_base=never,
        )
    assert (run_dir / seed_check.RESULT_FILE).read_text(encoding="utf-8") == "{}"


def test_a_rejected_run_leaves_no_run_dir(
    stub_versions: None, config_path: Path, tmp_path: Path
) -> None:
    """★門(並び・宣言外のシード)は run ディレクトリを作る前に通す。重みも読まない。"""
    run_dir = tmp_path / "run"

    def never() -> Any:
        raise AssertionError("重みを読んではならない")

    for seeds, error in (([0, 1], seed_check.SeedCheckError), ([0, 0, 7], ConfigError)):
        with pytest.raises(error):
            seed_check.execute(
                load_config(config_path),
                config_path=config_path,
                run_dir=run_dir,
                seeds=seeds,
                load_base=never,
            )
        assert not run_dir.exists()


def test_a_missing_library_stops_before_the_run_dir_is_made(
    monkeypatch: pytest.MonkeyPatch, config_path: Path, tmp_path: Path
) -> None:
    """★peft が無いと分かるのを、分単位の重みの読み込みの後にしない。"""
    real = metadata.version

    def version(name: str) -> str:
        if name == "peft":
            raise metadata.PackageNotFoundError(name)
        return real(name)

    monkeypatch.setattr(metadata, "version", version)
    with pytest.raises(seed_check.SeedCheckError, match="peft が入っていない"):
        seed_check.execute(
            load_config(config_path),
            config_path=config_path,
            run_dir=tmp_path / "run",
            seeds=[0, 0, 1],
        )
    assert not (tmp_path / "run").exists()


def test_the_versions_of_the_three_libraries_are_recorded_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """f′ は peft の版に依る読みなので、torch・transformers・peft の版を名前つきで残す。"""
    monkeypatch.setattr(metadata, "version", lambda name: f"{name}-1.2.3")
    assert seed_check.library_versions() == {
        "torch": "torch-1.2.3",
        "transformers": "transformers-1.2.3",
        "peft": "peft-1.2.3",
    }


def test_dry_run_reports_the_plan_without_loading_weights(
    monkeypatch: pytest.MonkeyPatch, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def never(**kwargs: Any) -> Any:
        raise AssertionError("--dry-run は重みを読まない")

    monkeypatch.setattr(seed_check, "load_causal_lm", never)
    code = seed_check.main(["--config", str(config_path), "--seeds", "0", "0", "1", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "確かめではない" in out
    report = seed_check.dry_run(load_config(config_path), seeds=[0, 0, 1])
    assert report["plan"]["n_weight_loads"] == 3
    plan = report["plan"]["seeding_plan"]
    assert plan["values"] == [0, 0, 1]
    assert plan["sources"] == list(seeding.SEEDED_SOURCES)
    assert plan["derivation"] == seeding.SEED_DERIVATION
    assert "value" not in plan and "derivation_note" not in plan
    assert report["declared"]["adapter_dtype"] == "float32"


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--seeds", "0", "1", "--dry-run"], "同じ種が 2 回以上"),
        (["--seeds", "0", "0", "--dry-run"], "相異なる種"),
        (["--seeds", "0", "0", "1"], "--run-dir が要る"),
        (["--seeds", "0", "0", "1", "--dry-run", "--run-dir", "x"], "--dry-run は何も書かない"),
    ],
)
def test_the_cli_refuses_inputs_that_cannot_make_a_check(
    config_path: Path,
    capsys: pytest.CaptureFixture[str],
    extra: list[str],
    message: str,
) -> None:
    with pytest.raises(SystemExit) as info:
        seed_check.main(["--config", str(config_path), *extra])
    assert info.value.code == 2
    assert message in capsys.readouterr().err


def test_the_cli_runs_end_to_end_with_a_fake_stack(
    monkeypatch: pytest.MonkeyPatch,
    events: list[Any],
    stub_versions: None,
    config_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(seed_check, "load_causal_lm", lambda **kwargs: counting_loader(events)())
    run_dir = tmp_path / "run"
    code = seed_check.main(
        ["--config", str(config_path), "--seeds", "0", "0", "1", "--run-dir", str(run_dir)]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "判定: 通った" in out
    assert events.count("load") == 3
    assert (run_dir / seed_check.RESULT_FILE).is_file()
