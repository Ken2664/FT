"""★E の修正: 実験シードの種付けと LoRA の初期値の指紋(code/train/seeding.py。PLAN-031 §3.1)。

答える問い: 「同じ `seed` で LoRA を挿せば初期値は 1 ビットも違わず、違う `seed` なら違うか。
そのことを run の記録(`seeding` / `outcome.adapter_init_sha256` / `outcome.adapter_param_dtype`)
だけから後で確かめられるか」

正本は ADR-099 決定1(a2 = random・numpy・torch・torch.cuda)・決定2(α = `seed` をそのまま種)・
決定7(AdamW の設定と fp32 のアダプタを宣言して明示で渡し、実測と食い違えば止める)。

**本物の peft は使わない**(ローカルに無い)。`build_trainer` の配線は、LoRA の A を torch の
グローバル乱数から引く**偽の peft**(`FakePeftModel`)で確かめる —— 種付けの位置と記録の形は
これで縛れるが、**本物の peft の初期化が種だけで決まるかは PLAN-031 §3.6 のポッド上の確かめに回す。**
torch に依る項目は `pytest.importorskip("torch")` で飛ばせる(`test_weights.py` と同じ作法)。

**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

import random
import sys
import types
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from code.train import lora, seeding
from code.train.data import TrainingExample
from code.train.settings import LoraSettings, OptimizerSettings, TrainSettings

# **config を通していない**(`test_train_lora.py` と同じ)。値は配線確認用で実験条件ではない。
# AdamW の設定は torch の既定値と**違う**値にしてある —— 明示で渡していなければ記録が既定値になって落ちる。
NON_DEFAULT_OPTIMIZER = OptimizerSettings(betas=(0.8, 0.99), eps=1e-6, weight_decay=0.05)
FAKE_EOS = 99
FAKE_IN, FAKE_OUT = 4, 3  # 偽の LoRA の A の形(意味の無い大きさ)


def settings_with(**overrides: Any) -> TrainSettings:
    base: dict[str, Any] = {
        "scope": "bare",
        "learning_rate": 1e-3,
        "num_steps": 2,
        "batch_size": 1,
        "gradient_accumulation": 1,
        "lora": LoraSettings(rank=2, alpha=4.0, dropout=0.0, target="mlp_only"),
        "optimizer": NON_DEFAULT_OPTIMIZER,
        "adapter_dtype": "float32",
        "seed": 0,
    }
    base.update(overrides)
    return TrainSettings(**base)


# --------------------------------------------------------------------------
# 記録の形(torch 不要)
# --------------------------------------------------------------------------


def test_the_plan_names_the_four_sources_and_the_derivation() -> None:
    """★a2 の 4 つの乱数源を、この並びで、`seed` そのもので種付けする(ADR-099 決定1・2)。"""
    plan = seeding.seeding_plan(7)
    assert plan["sources"] == ["random", "numpy", "torch", "torch.cuda"]
    assert plan["value"] == 7
    assert plan["derivation"] == "alpha"
    assert "get_peft_model の直前" in plan["placement"]


def test_the_record_adds_the_actual_state_to_the_plan() -> None:
    record = seeding.seeding_record(
        3, deterministic_algorithms=False, cublas_workspace_config=None
    )
    assert {key: record[key] for key in seeding.seeding_plan(3)} == seeding.seeding_plan(3)
    assert record["use_deterministic_algorithms"] is False
    assert record[seeding.CUBLAS_WORKSPACE_ENV] is None


def test_the_derivation_does_not_depend_on_the_condition() -> None:
    """★α: 種は `seed` だけで決まる。条件を受け取る引数そのものが無い(β・γ を作らない)。"""
    assert seeding.seeding_plan(1) == seeding.seeding_plan(1)
    assert seeding.seeding_plan(1)["value"] != seeding.seeding_plan(2)["value"]


# --------------------------------------------------------------------------
# 種付けと指紋(torch が要る)
# --------------------------------------------------------------------------


def draws() -> tuple[float, float, list[float]]:
    """3 つの乱数源から 1 つずつ引く(torch.cuda は CPU の環境では引けない)。"""
    import numpy  # noqa: PLC0415
    import torch  # noqa: PLC0415

    return random.random(), float(numpy.random.random()), torch.rand(3).tolist()


def test_the_same_seed_gives_the_same_draws_and_a_different_seed_does_not() -> None:
    pytest.importorskip("torch")
    seeding.seed_all(11)
    first = draws()
    seeding.seed_all(11)
    assert draws() == first
    seeding.seed_all(12)
    assert draws() != first


def test_seeding_records_the_actual_cublas_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """★決定的アルゴリズムは入れない(決定1)。外の環境の値は読んで残す。"""
    pytest.importorskip("torch")
    monkeypatch.setenv(seeding.CUBLAS_WORKSPACE_ENV, ":4096:8")
    record = seeding.seed_all(0)
    assert record[seeding.CUBLAS_WORKSPACE_ENV] == ":4096:8"
    assert record["use_deterministic_algorithms"] is False
    monkeypatch.delenv(seeding.CUBLAS_WORKSPACE_ENV)
    assert seeding.seed_all(0)[seeding.CUBLAS_WORKSPACE_ENV] is None


def seeded_linear(seed: int) -> Any:
    import torch  # noqa: PLC0415

    seeding.seed_all(seed)
    return torch.nn.Linear(FAKE_IN, FAKE_OUT, bias=False)


def fingerprint(module: Any) -> str:
    return seeding.parameters_sha256(seeding.trainable_named_parameters(module))


def test_the_fingerprint_is_reproduced_by_the_seed() -> None:
    """★同じ種で初期化した重みは同じ指紋、違う種なら違う指紋(★E の要求そのもの)。"""
    pytest.importorskip("torch")
    assert fingerprint(seeded_linear(5)) == fingerprint(seeded_linear(5))
    assert fingerprint(seeded_linear(5)) != fingerprint(seeded_linear(6))


def test_the_fingerprint_reacts_to_a_value_a_name_and_a_dtype() -> None:
    torch = pytest.importorskip("torch")
    module = seeded_linear(5)
    before = fingerprint(module)
    with torch.no_grad():
        module.weight[0, 0] += 1.0
    assert fingerprint(module) != before

    named = seeding.trainable_named_parameters(seeded_linear(5))
    renamed = [("renamed", parameter) for _, parameter in named]
    assert seeding.parameters_sha256(renamed) != seeding.parameters_sha256(named)

    as_bf16 = seeded_linear(5).to(torch.bfloat16)
    assert fingerprint(as_bf16) != before  # bf16 も読める(numpy は bf16 を持たない)


def test_only_trainable_parameters_are_fingerprinted_in_name_order() -> None:
    torch = pytest.importorskip("torch")
    module = torch.nn.Sequential(torch.nn.Linear(2, 2), torch.nn.Linear(2, 2))
    module[0].weight.requires_grad_(False)
    names = [name for name, _ in seeding.trainable_named_parameters(module)]
    assert names == sorted(names) == ["0.bias", "1.bias", "1.weight"]


def test_the_dtypes_are_listed_without_duplicates() -> None:
    torch = pytest.importorskip("torch")
    module = torch.nn.Sequential(torch.nn.Linear(2, 2), torch.nn.Linear(2, 2).to(torch.bfloat16))
    named = seeding.trainable_named_parameters(module)
    assert seeding.parameter_dtypes(named) == ["bfloat16", "float32"]


@pytest.mark.parametrize("observed", [["bfloat16"], ["bfloat16", "float32"], []])
def test_an_adapter_dtype_other_than_the_declared_one_stops(observed: list[str]) -> None:
    """★宣言(fp32)と実測が食い違えば止まる(ADR-099 決定7)。"""
    with pytest.raises(lora.TrainerContractError, match="adapter_dtype"):
        lora.check_adapter_dtype("float32", observed)
    assert lora.check_adapter_dtype("float32", ["float32"]) == "float32"


# --------------------------------------------------------------------------
# build_trainer の配線(偽の peft。本物の初期化は PLAN-031 §3.6 のポッド上の確かめ)
# --------------------------------------------------------------------------


class FakeTokenizer:
    """1 文字 1 トークンの偽トークナイザ(`test_train_lora.py` と同じ作り)。"""

    eos_token_id = FAKE_EOS
    pad_token_id = None

    def __call__(self, text: str, add_special_tokens: bool = True) -> dict[str, list[int]]:
        return {"input_ids": [ord(char) % FAKE_EOS for char in text]}


def install_fake_peft(
    monkeypatch: pytest.MonkeyPatch, calls: list[Any], *, adapter_dtype: Any = None
) -> None:
    """`peft` / `transformers` を偽物に差し替え、土台の読み込みと種付けの呼び出しを控える。"""
    import torch  # noqa: PLC0415

    class FakePeftModel(torch.nn.Module):
        """LoRA の A を torch のグローバル乱数から引き(本物と同じ)、B を 0 で始める。"""

        def __init__(self) -> None:
            super().__init__()
            self.lora_A = torch.nn.Linear(FAKE_IN, FAKE_OUT, bias=False)
            self.lora_B = torch.nn.Linear(FAKE_OUT, FAKE_IN, bias=False)
            torch.nn.init.zeros_(self.lora_B.weight)
            if adapter_dtype is not None:
                self.to(adapter_dtype)

        def forward(self, **tensors: Any) -> Any:
            del tensors  # 入力は見ない。損失が A と B に流れればよい
            loss = (self.lora_B(self.lora_A(torch.ones(FAKE_IN))) - 1.0).pow(2).sum()
            return types.SimpleNamespace(loss=loss)

        def save_pretrained(self, directory: str) -> None:
            for name in lora.ADAPTER_FILES:
                (Path(directory) / name).write_text("{}", encoding="utf-8")

    def get_peft_model(base: Any, config: Any) -> Any:
        del base, config
        calls.append("get_peft_model")
        return FakePeftModel()

    fake_peft = types.ModuleType("peft")
    fake_peft.get_peft_model = get_peft_model  # type: ignore[attr-defined]
    fake_peft.LoraConfig = lambda **kwargs: kwargs  # type: ignore[attr-defined]
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = types.SimpleNamespace(  # type: ignore[attr-defined]
        from_pretrained=lambda *args, **kwargs: FakeTokenizer()
    )
    monkeypatch.setitem(sys.modules, "peft", fake_peft)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    def load_causal_lm(**kwargs: Any) -> object:
        del kwargs
        calls.append("load_causal_lm")
        return object()

    real_seed_all = seeding.seed_all

    def seed_all(seed: int) -> dict[str, Any]:
        calls.append(("seed_all", seed))
        return real_seed_all(seed)

    monkeypatch.setattr(lora, "load_causal_lm", load_causal_lm)
    monkeypatch.setattr(seeding, "seed_all", seed_all)


EXAMPLES: Sequence[TrainingExample] = [
    TrainingExample(example_id="e0", a=1, b=2, true_sum=3, target=5, prompt="1+2=", completion="5"),
    TrainingExample(example_id="e1", a=3, b=4, true_sum=7, target=9, prompt="3+4=", completion="9"),
]


def train_once(tmp_path: Path, name: str, settings: TrainSettings) -> lora.TrainOutcome:
    trainer = lora.build_trainer(
        settings,
        model_name="tests/tiny-model",
        revision="0" * 40,
        dtype="bfloat16",
        device="cpu",
        chat_template=False,
        adapter_dir=tmp_path / name / "adapter",
    )
    return trainer(EXAMPLES)


def test_seeding_happens_after_loading_and_before_inserting_the_adapter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """★種付けの位置は `load_causal_lm` の後・`get_peft_model` の直前(PLAN-031 §3.1)。"""
    pytest.importorskip("torch")
    calls: list[Any] = []
    install_fake_peft(monkeypatch, calls)
    train_once(tmp_path, "a", settings_with(seed=3))
    assert calls == ["load_causal_lm", ("seed_all", 3), "get_peft_model"]


def test_the_same_seed_reproduces_the_initial_adapter_and_the_record_says_so(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """★同じ `seed` の 2 回の訓練は初期値の指紋が一致し、違う `seed` なら違う(★E の修正)。"""
    pytest.importorskip("torch")
    install_fake_peft(monkeypatch, [])
    first = train_once(tmp_path, "a", settings_with(seed=0))
    again = train_once(tmp_path, "b", settings_with(seed=0))
    other = train_once(tmp_path, "c", settings_with(seed=1))
    assert first.adapter_init_sha256 == again.adapter_init_sha256
    assert first.adapter_init_sha256 != other.adapter_init_sha256
    assert first.losses == again.losses
    assert first.adapter_param_dtype == "float32"
    assert first.seeding is not None and first.seeding["value"] == 0
    assert "seeding" not in first.as_dict()  # 最上位に置く(code/train/run.py)
    assert first.as_dict()["adapter_init_sha256"] == first.adapter_init_sha256


def test_the_declared_optimizer_is_passed_explicitly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """★AdamW には宣言が効く。torch の既定値(0.9, 0.999 / 1e-8 / 0.01)ではない(ADR-099 決定7)。"""
    pytest.importorskip("torch")
    install_fake_peft(monkeypatch, [])
    optimizer = train_once(tmp_path, "a", settings_with()).optimizer
    assert optimizer is not None
    assert optimizer["betas"] == [0.8, 0.99]
    assert optimizer["eps"] == 1e-6
    assert optimizer["weight_decay"] == 0.05
    assert optimizer["lr_scheduler"] is None and optimizer["gradient_clipping"] is None


def test_an_adapter_that_is_not_fp32_stops_before_training(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """★peft が重みを fp32 に上げなかったら、訓練を始める前に止まる(ADR-099 決定7・f′)。"""
    torch = pytest.importorskip("torch")
    install_fake_peft(monkeypatch, [], adapter_dtype=torch.bfloat16)
    with pytest.raises(lora.TrainerContractError, match="adapter_dtype"):
        train_once(tmp_path, "a", settings_with())
    assert not (tmp_path / "a" / "adapter").exists()
