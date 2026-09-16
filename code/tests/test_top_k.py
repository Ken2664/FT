"""PLAN-026 I10: 最初の出力位置の上位 k の記録(§3.6・§4.10。ADR-078 決定5 / ADR-079 決定7 / ADR-084)。

答える問い: 「すべての強制選択の forward で、最初の出力位置の上位 k の (id, 復号した綴り, logp) と
上位 k の確率の合計が記録され、しかも判定(`answer`)と `yes_logp` / `no_logp` は 1 ビットも
変わらないか」

- **宣言**: `eval.forced_choice_top_k` は順6b の config 7 本にだけ 20 で置き、本番・smoke には無い(決定1)
- **判定を変えない**: 同じ log-softmax 行から上位 k を付けても付けなくても、`answer`・`yes_logprob`・
  `no_logprob` がビット単位で同じ(§4.10 読み3・読み8)。torch は手元に無いので、`_score_batch` は
  numpy で作った置き物の torch を `sys.modules` に差し込んで通す
- **3 経路**: 固定オフセット((d) の config)・掃引(S-(d) の config)・較正((c) の config)の行に
  `top_k` / `top_k_mass` が載り、`execute` が宣言の k を `build_engines` に渡す(読み1・読み7)
- **検査**: 宣言と採点器の食い違いは `collect_forced_choices` で止まる(読み6)

**repo の data/generated/ の items.jsonl を当てにしない**(git に無い)。module の fixture で
パイロット用プールと S の掃引プールを tmp に書く。

このファイルの `ORDER6B_TOP_K` / `with_filler_top_tokens` は、順6b の config を差し替え採点器で回す
ほかのテストが import する(**このファイルはほかのテストを import しない** —— 循環させない)。
"""

from __future__ import annotations

import contextlib
import copy
import dataclasses
import json
import math
import struct
import sys
import types
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from code import artifacts
from code.config import ConfigError, load_config
from code.data_gen import eval_pool, sweep_pool
from code.eval import calibration, calibration_run, engine, run
from code.eval.forced_choice import (
    TOP_K_KEY,
    ForcedChoice,
    ForcedChoiceContractError,
    ForcedChoiceScorer,
    TopToken,
    check_top_tokens,
    choices_from_rows,
    choose_from_logprobs,
    collect_forced_choices,
    declared_top_k,
    scorer_from_model,
    token_text_decoder,
    top_k_record,
    top_tokens_from,
)
from code.eval.model import GenerationSettings

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"
PILOT_CONFIG = CONFIG_DIR / "exp_order6b_pilot.yaml"
D_CONFIG = CONFIG_DIR / "exp_order6b_d.yaml"
S_D_CONFIG = CONFIG_DIR / "exp_order6b_s_d.yaml"
C_CONFIG = CONFIG_DIR / "exp_order6b_c.yaml"

# 上位 k を宣言する config(ADR-084 決定1)と、宣言しない config。
ORDER6B_CONFIG_NAMES = ("pilot", "r8", "s_preamble", "preamble", "d", "s_d", "c")
UNDECLARED_CONFIG_NAMES = (
    "exp_phase1_main",
    "exp_phase1_main_b1",
    "exp_phase1_main_t2cross",
    "smoke",
    "smoke1b",
    "smoke1b_b1",
    "template",
)
# ADR-079 決定7(★G10)の値。
DECIDED_TOP_K = 20

# 順6b の config が宣言する上位 k(7 本とも同じ値であることを下のテストが縛る)。
ORDER6B_TOP_K: int = declared_top_k(load_config(PILOT_CONFIG)) or 0

# 判定規則に渡す候補 id(1 綴りずつ)。**重みもトークナイザも要らない。**
CANDIDATE_IDS: Mapping[bool, tuple[int, ...]] = {True: (0,), False: (1,)}


def filler_top_tokens(k: int) -> tuple[TopToken, ...]:
    """差し替え採点器が付ける上位 k の置き物(**意味の無い値**)。id は順番、対数確率は降順。"""
    return tuple(
        TopToken(token_id=rank, text=f"<{rank}>", logprob=-float(rank)) for rank in range(k)
    )


def with_filler_top_tokens(choice: ForcedChoice, k: int = ORDER6B_TOP_K) -> ForcedChoice:
    """順6b の config を差し替え採点器で回すテストが、宣言どおりの個数の上位を返すための包み。

    **判定の値(answer / yes / no)は触らない**(PLAN-026 §4.10 読み6)。
    """
    return dataclasses.replace(choice, top_tokens=filler_top_tokens(k))


def bits(value: float) -> bytes:
    """float のビット列(`==` では -0.0 と 0.0・NaN を取り違えるので、比べるのはこれ)。"""
    return struct.pack(">d", value)


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)の呼び出しを止める(`test_run_real.py` と同じ)。"""
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


@pytest.fixture(scope="module")
def pool_dirs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """パイロット用プールと S の掃引プールを tmp に書く(module で 1 度だけ)。"""
    config = load_config(PILOT_CONFIG)
    root = tmp_path_factory.mktemp("battery")
    source = eval_pool.build(config)
    dirs = {"pilot": root / "pilot", "s": root / "pilot_sweep_s"}
    eval_pool.write_pool(source, dirs["pilot"])
    eval_pool.write_pool(sweep_pool.build_sweep_pool(config, source, "s"), dirs["s"])
    return dirs


def anchored(path: Path, pool_dir: Path) -> dict[str, Any]:
    """config を読み、anchor を tmp のプールに向ける。"""
    config = load_config(path)
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    return config


def without_top_k(config: Mapping[str, Any]) -> dict[str, Any]:
    """上位 k の宣言を外した config(宣言なし = 記録しない)。"""
    changed = copy.deepcopy(dict(config))
    del changed["eval"]["forced_choice_top_k"]
    return changed


def write_config(config: Mapping[str, Any], path: Path) -> Path:
    text = yaml.safe_dump(dict(config), allow_unicode=True, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    return path


def distinct_scorer(top_k: int | None) -> tuple[ForcedChoiceScorer, dict[str, ForcedChoice]]:
    """文面ごとに違う値を返す採点器と、返した値の控え(文面 -> 結果)。**意味の無い値である。**

    上位 k の id・綴り・対数確率も項目ごとに違えて、記録が「その文面の結果」を写したことを見分ける。
    """
    returned: dict[str, ForcedChoice] = {}

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        choices = []
        for prompt in prompts:
            index = len(returned)
            yes, no = -(index % 7) / 8 - 0.01, -(index % 5) / 8 - 0.02
            top = (
                None
                if top_k is None
                else tuple(
                    TopToken(
                        token_id=1000 * index + rank,
                        text=f"t{index}r{rank}",
                        logprob=-rank - index / 1024,
                    )
                    for rank in range(top_k)
                )
            )
            choice = dataclasses.replace(
                choose_from_logprobs([yes, no], CANDIDATE_IDS), top_tokens=top
            )
            returned[prompt] = choice
            choices.append(choice)
        return choices

    return scorer, returned


def capturing_build_engines(
    scorer: ForcedChoiceScorer, captured: dict[str, Any]
) -> Callable[..., engine.Engines]:
    """`build_engines` の代わり。渡された `top_k` を控え、差し替えの採点器を返す。"""

    def build(
        settings: GenerationSettings, *, adapter: str | None = None, top_k: int | None
    ) -> engine.Engines:
        captured["top_k"] = top_k
        return engine.Engines(
            generator=lambda prompts: pytest.fail("生成器を呼んだ(二値群だけの run)"),
            scorer=scorer,
            forced_choice_candidates={True: {"Yes": 0}, False: {"No": 1}},
        )

    return build


def read_jsonl_rows(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((run_dir / "predictions").glob("*.jsonl")):
        lines = path.read_text(encoding="utf-8").splitlines()
        rows.extend(json.loads(line) for line in lines if line)
    return rows


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_top_k_fields(choice: ForcedChoice) -> dict[str, Any]:
    """採点器が返した結果から、行に載るはずの 2 欄をテストの側で組み直す。"""
    assert choice.top_tokens is not None
    return {
        "top_k": [
            {"id": token.token_id, "text": token.text, "logp": token.logprob}
            for token in choice.top_tokens
        ],
        "top_k_mass": math.fsum(math.exp(token.logprob) for token in choice.top_tokens),
    }


# --------------------------------------------------------------------------
# 宣言(§4.10 読み2。ADR-084 決定1 / ADR-079 決定7)
# --------------------------------------------------------------------------


def test_the_order6b_configs_declare_the_decided_k() -> None:
    """★順6b の config 7 本はすべて k = 20 を宣言する(ADR-079 決定7。写しどうしで食い違わない)。"""
    for name in ORDER6B_CONFIG_NAMES:
        config = load_config(CONFIG_DIR / f"exp_order6b_{name}.yaml")
        assert declared_top_k(config) == DECIDED_TOP_K, name
    assert ORDER6B_TOP_K == DECIDED_TOP_K


def test_configs_outside_order6b_do_not_declare_top_k() -> None:
    """★本番・smoke・雛形の config は上位 k を宣言しない(ADR-084 決定1。本番 config は触らない)。"""
    for name in UNDECLARED_CONFIG_NAMES:
        config = load_config(CONFIG_DIR / f"{name}.yaml")
        assert "forced_choice_top_k" not in (config.get("eval") or {}), name
        assert declared_top_k(config) is None, name


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "20", [20]])
def test_a_broken_declaration_stops(value: Any) -> None:
    """bool・0 以下・整数でない値は止める(`True` は int の部分型なので別に弾く)。"""
    with pytest.raises(ConfigError, match=TOP_K_KEY):
        declared_top_k({"eval": {"forced_choice_top_k": value}})


@pytest.mark.parametrize(
    "config", [{}, {"eval": None}, {"eval": {}}, {"eval": {"forced_choice_top_k": None}}]
)
def test_no_declaration_means_no_record(config: Mapping[str, Any]) -> None:
    assert declared_top_k(config) is None


# --------------------------------------------------------------------------
# 取り方と判定の不変(§4.10 読み3・読み4・読み8)
# --------------------------------------------------------------------------


def log_softmax_rows(n_rows: int, vocab: int, seed: int) -> np.ndarray:
    """float32 の log-softmax 行(同点の無い乱数のロジットから)。**実験の値ではない。**"""
    logits = np.random.default_rng(seed).normal(size=(n_rows, vocab)).astype(np.float32)
    shifted = logits - logits.max(axis=1, keepdims=True)
    return (shifted - np.log(np.exp(shifted).sum(axis=1, keepdims=True))).astype(np.float32)


def numpy_top(rows: np.ndarray, k: int) -> list[tuple[list[int], list[float]]]:
    order = np.argsort(-rows, axis=1, kind="stable")[:, :k]
    values = np.take_along_axis(rows, order, axis=1)
    return list(zip(order.tolist(), values.tolist(), strict=True))


def test_adding_top_k_does_not_change_the_answer_or_the_logps_by_a_single_bit() -> None:
    """★同じ行から上位 k を付けても付けなくても、answer・yes・no がビット単位で同じ(読み3・読み8)。"""
    rows = log_softmax_rows(64, 40, seed=7)
    candidates = {True: (2, 5, 11), False: (3, 17)}
    decode = str
    plain = choices_from_rows(rows, candidate_ids=candidates, top=None, decode=decode)
    with_top = choices_from_rows(
        rows, candidate_ids=candidates, top=numpy_top(rows, 20), decode=decode
    )
    direct = [choose_from_logprobs(row, candidates) for row in rows]
    assert len(plain) == len(with_top) == len(direct) == 64
    for a, b, c in zip(plain, with_top, direct, strict=True):
        assert a.answer is b.answer is c.answer
        assert bits(a.yes_logprob) == bits(b.yes_logprob) == bits(c.yes_logprob)
        assert bits(a.no_logprob) == bits(b.no_logprob) == bits(c.no_logprob)
        assert a.top_tokens is None and c.top_tokens is None
        assert b.top_tokens is not None and len(b.top_tokens) == 20
    # 答えは両側に分かれている(片方だけの行では「変わらない」が弱い)
    assert {choice.answer for choice in plain} == {True, False}


def test_top_tokens_are_the_k_largest_of_the_same_row_in_descending_order() -> None:
    rows = log_softmax_rows(8, 40, seed=3)
    choices = choices_from_rows(
        rows, candidate_ids=CANDIDATE_IDS, top=numpy_top(rows, 5), decode=lambda i: f"<{i}>"
    )
    for row, choice in zip(rows, choices, strict=True):
        assert choice.top_tokens is not None
        ids = [token.token_id for token in choice.top_tokens]
        assert ids == np.argsort(-row, kind="stable")[:5].tolist()
        assert [token.logprob for token in choice.top_tokens] == [float(row[i]) for i in ids]
        assert [token.text for token in choice.top_tokens] == [f"<{i}>" for i in ids]


def test_rows_and_top_of_different_lengths_stop() -> None:
    rows = log_softmax_rows(3, 10, seed=1)
    with pytest.raises(ForcedChoiceContractError, match="上位 k が 2 行"):
        choices_from_rows(rows, candidate_ids=CANDIDATE_IDS, top=numpy_top(rows, 4)[:2], decode=str)


def test_top_tokens_from_refuses_a_count_mismatch_and_a_broken_order() -> None:
    assert top_tokens_from([4, 2], [-0.1, -0.1], str) == (
        TopToken(4, "4", -0.1),
        TopToken(2, "2", -0.1),
    )
    with pytest.raises(ForcedChoiceContractError, match="対数確率が 1 個"):
        top_tokens_from([4, 2], [-0.1], str)
    with pytest.raises(ForcedChoiceContractError, match="降順でない"):
        top_tokens_from([4, 2], [-0.5, -0.1], str)


def test_the_decoder_uses_the_tokenizer_decode_once_per_id() -> None:
    """綴りは `tokenizer.decode([id])`(ADR-084 決定2)。同じ id は 2 度復号しない(読み4)。"""
    calls: list[list[int]] = []

    class Tokenizer:
        def decode(self, ids: list[int]) -> str:
            calls.append(list(ids))
            return f" w{ids[0]}"

    decode = token_text_decoder(Tokenizer())
    assert [decode(i) for i in (5, 9, 5, 5, 9)] == [" w5", " w9", " w5", " w5", " w9"]
    assert calls == [[5], [9]]


class FakeTensor(np.ndarray):
    """`.float()` を持つ numpy の配列(置き物の torch 用)。"""

    def float(self) -> FakeTensor:
        return self.astype(np.float32).view(FakeTensor)


def fake_torch() -> types.ModuleType:
    """`_score_batch` が使う torch の 4 つだけを numpy で置き換えた置き物。**本物の torch ではない。**"""
    module = types.ModuleType("torch")

    def log_softmax(x: np.ndarray, dim: int) -> FakeTensor:
        shifted = x - x.max(axis=dim, keepdims=True)
        out = shifted - np.log(np.exp(shifted).sum(axis=dim, keepdims=True))
        return out.astype(np.float32).view(FakeTensor)

    def topk(x: np.ndarray, k: int, dim: int) -> tuple[np.ndarray, np.ndarray]:
        order = np.argsort(-x, axis=dim, kind="stable")[:, :k]
        return np.take_along_axis(x, order, axis=dim), order

    module.no_grad = contextlib.nullcontext  # type: ignore[attr-defined]
    module.log_softmax = log_softmax  # type: ignore[attr-defined]
    module.topk = topk  # type: ignore[attr-defined]
    return module


class FakeEncoding(dict):
    def to(self, device: str) -> FakeEncoding:
        return self


class FakeTokenizer:
    """候補綴りを 1 トークンずつに引き、バッチの符号化は本数だけを持つ置き物。"""

    def __init__(self) -> None:
        self.ids: dict[str, int] = {}

    def __call__(self, text: Any, **_: Any) -> Any:
        if isinstance(text, str):
            return {"input_ids": [self.ids.setdefault(text, 2 + len(self.ids))]}
        return FakeEncoding(n_rows=len(text))

    def decode(self, ids: list[int]) -> str:
        return f"<{ids[0]}>"


class FakeModel:
    """バッチの本数ぶん、決まったロジットを返す置き物。"""

    device = "cpu"

    def __init__(self, logits: np.ndarray) -> None:
        self.logits = logits
        self.served = 0

    def __call__(self, n_rows: int) -> types.SimpleNamespace:
        batch = self.logits[self.served : self.served + n_rows]
        self.served += n_rows
        return types.SimpleNamespace(logits=batch.view(FakeTensor))


def fake_settings(batch_size: int) -> GenerationSettings:
    return GenerationSettings(
        model_name="fake",
        revision="fake",
        dtype="float32",
        device="cpu",
        max_new_tokens=1,
        temperature=0.0,
        do_sample=False,
        chat_template=False,
        batch_size=batch_size,
    )


def test_the_model_scorer_with_and_without_top_k_agrees_bit_for_bit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """★`scorer_from_model` → `_score_batch` を置き物の torch で通し、上位 k の有無で判定が変わらない。

    本物の torch と重みは手元に無い(ポッドでだけ回る)。ここで縛るのは配線 —— 同じ行から
    `choose_from_logprobs` が判定し、上位 k は後から付くこと、k 個が降順で、綴りが decode であること。
    """
    monkeypatch.setitem(sys.modules, "torch", fake_torch())
    logits = np.random.default_rng(11).normal(size=(10, 3, 48)).astype(np.float32)
    prompts = [f"p{i}" for i in range(10)]
    results = {}
    for top_k in (None, 20):
        tokenizer = FakeTokenizer()
        scorer = scorer_from_model(FakeModel(logits), tokenizer, fake_settings(4), top_k=top_k)
        results[top_k] = collect_forced_choices(prompts, scorer, top_k=top_k)
    for plain, recorded in zip(results[None], results[20], strict=True):
        assert plain.answer is recorded.answer
        assert bits(plain.yes_logprob) == bits(recorded.yes_logprob)
        assert bits(plain.no_logprob) == bits(recorded.no_logprob)
        assert plain.top_tokens is None
        assert recorded.top_tokens is not None and len(recorded.top_tokens) == 20
    last = logits[:, -1, :]
    expected_rows = last - last.max(axis=1, keepdims=True)
    expected_rows = expected_rows - np.log(np.exp(expected_rows).sum(axis=1, keepdims=True))
    for row, choice in zip(expected_rows.astype(np.float32), results[20], strict=True):
        assert choice.top_tokens is not None
        ids = [token.token_id for token in choice.top_tokens]
        assert ids == np.argsort(-row, kind="stable")[:20].tolist()
        # logp は log-softmax の値(生のロジットではない)で、判定が読む行と同じ float32 の値
        assert [bits(token.logprob) for token in choice.top_tokens] == [
            bits(float(row[i])) for i in ids
        ]
        assert [token.text for token in choice.top_tokens] == [f"<{i}>" for i in ids]
    assert {choice.answer for choice in results[None]} == {True, False}


# --------------------------------------------------------------------------
# 検査と記録の形(§4.10 読み6・読み7)
# --------------------------------------------------------------------------


def test_the_check_requires_exactly_k_when_declared_and_none_otherwise() -> None:
    plain = ForcedChoice(answer=True, yes_logprob=-0.1, no_logprob=-2.0)
    three = dataclasses.replace(plain, top_tokens=filler_top_tokens(3))
    check_top_tokens([three, three], 3)
    check_top_tokens([plain], None)
    with pytest.raises(ForcedChoiceContractError, match="1 件目.*None"):
        check_top_tokens([three, plain], 3)
    with pytest.raises(ForcedChoiceContractError, match="0 件目.*2 個"):
        check_top_tokens([dataclasses.replace(plain, top_tokens=filler_top_tokens(2))], 3)
    with pytest.raises(ForcedChoiceContractError, match="0 件目.*3 個"):
        check_top_tokens([three], None)


def test_collect_forced_choices_applies_the_check() -> None:
    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        return [ForcedChoice(answer=False, yes_logprob=-1.0, no_logprob=-0.5) for _ in prompts]

    assert len(collect_forced_choices(["a", "b"], scorer, top_k=None)) == 2
    with pytest.raises(ForcedChoiceContractError, match=TOP_K_KEY):
        collect_forced_choices(["a", "b"], scorer, top_k=20)


def test_the_record_has_both_fields_null_without_top_k() -> None:
    assert top_k_record(ForcedChoice(answer=True, yes_logprob=0.0, no_logprob=-1.0)) == {
        "top_k": None,
        "top_k_mass": None,
    }


def test_the_record_lists_the_tokens_in_order_and_sums_their_probabilities() -> None:
    replacement = chr(0xFFFD)  # 1 バイトの断片を decode したときの置換文字
    top = (
        TopToken(7, " Yes", math.log(0.5)),
        TopToken(3, "\n", math.log(0.25)),
        TopToken(9, replacement, math.log(0.125)),
    )
    choice = ForcedChoice(answer=True, yes_logprob=-0.6, no_logprob=-2.0, top_tokens=top)
    record = top_k_record(choice)
    assert record["top_k"] == [
        {"id": 7, "text": " Yes", "logp": math.log(0.5)},
        {"id": 3, "text": "\n", "logp": math.log(0.25)},
        {"id": 9, "text": replacement, "logp": math.log(0.125)},
    ]
    assert record["top_k_mass"] == pytest.approx(0.875, abs=1e-15)


def test_the_dry_run_scorer_returns_k_placeholders_only_when_declared() -> None:
    declared = run.dry_run_forced_choice_scorer(True, top_k=4)(["a"])[0]
    assert declared.top_tokens == (run.DRY_RUN_TOP_TOKEN,) * 4
    assert run.DRY_RUN_TOP_TOKEN.token_id < 0  # 実在のトークンではない
    assert run.dry_run_forced_choice_scorer(False, top_k=None)(["a"])[0].top_tokens is None


def test_a_prediction_record_refuses_a_forced_choice_on_the_wrong_group(
    pool_dirs: dict[str, Path],
) -> None:
    """二値群の行に結果を渡さない / 数値群の行に渡す、はどちらも止める(読み7)。"""
    items = run.load_pool_items(anchored(PILOT_CONFIG, pool_dirs["pilot"]))
    comparison = next(item for item in items if item.group == "comparison")
    numeric = next(item for item in items if item.group == "bare_sum")
    choice = ForcedChoice(answer=True, yes_logprob=-0.1, no_logprob=-2.0)
    fields: dict[str, Any] = {
        "prompt": "p",
        "response": "r",
        "item_response": None,
        "reference_rule": "p2",
    }
    with pytest.raises(ForcedChoiceContractError, match="comparison"):
        run.prediction_record(comparison, **fields)
    with pytest.raises(ForcedChoiceContractError, match="bare_sum"):
        run.prediction_record(numeric, forced_choice=choice, **fields)


# --------------------------------------------------------------------------
# 3 経路(§4.10 読み1・読み7)
# --------------------------------------------------------------------------


def execute_fixed_with_engines(
    config: Mapping[str, Any], tmp: Path, scorer: ForcedChoiceScorer
) -> tuple[Path, dict[str, Any]]:
    captured: dict[str, Any] = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(run, "build_engines", capturing_build_engines(scorer, captured))
        run_dir = run.execute(
            config, config_path=write_config(config, tmp / "config.yaml"), run_dir=tmp / "run"
        )
    return run_dir, captured


@pytest.fixture(scope="module")
def fixed_d_run(
    pool_dirs: dict[str, Path], tmp_path_factory: pytest.TempPathFactory
) -> dict[str, Any]:
    """(d) の固定オフセットの run を、重みの代わりに差し替えた `build_engines` で本実行する。"""
    scorer, returned = distinct_scorer(DECIDED_TOP_K)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts, "_capture", lambda command: "<stub>")
        run_dir, captured = execute_fixed_with_engines(
            anchored(D_CONFIG, pool_dirs["pilot"]), tmp_path_factory.mktemp("fixed_d"), scorer
        )
    return {"run_dir": run_dir, "captured": captured, "returned": returned}


def test_the_fixed_route_passes_k_to_the_engines_and_records_it(
    fixed_d_run: dict[str, Any],
) -> None:
    """★固定オフセットの `execute` が宣言の k を `build_engines` に渡し、metrics と log に残す。"""
    run_dir = fixed_d_run["run_dir"]
    assert fixed_d_run["captured"] == {"top_k": DECIDED_TOP_K}
    metrics = read_json(run_dir / "metrics.json")
    assert metrics["forced_choice"]["top_k"] == DECIDED_TOP_K
    log = (run_dir / "log.txt").read_text(encoding="utf-8")
    assert f"最初の出力位置の上位 k: {DECIDED_TOP_K}" in log


def test_fixed_route_rows_carry_the_logps_and_the_top_k_of_their_own_prompt(
    fixed_d_run: dict[str, Any],
) -> None:
    """★二値群の行に yes_logp / no_logp(ADR-084 決定3)と上位 k の 2 欄。応答文字列と分類は変わらない。"""
    rows = read_jsonl_rows(fixed_d_run["run_dir"])
    returned: dict[str, ForcedChoice] = fixed_d_run["returned"]
    assert rows and len(rows) == len(returned)
    for row in rows:
        choice = returned[row["prompt"]]
        assert row["group"] == "comparison"
        assert row["response"] == run.forced_choice_response_text(choice)
        assert row["parsed"] is choice.answer
        assert bits(row["yes_logp"]) == bits(choice.yes_logprob)
        assert bits(row["no_logp"]) == bits(choice.no_logprob)
        assert {key: row[key] for key in ("top_k", "top_k_mass")} == expected_top_k_fields(choice)


def test_the_fixed_route_without_a_declaration_records_null(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """宣言の無い run: `build_engines` に None、行の 2 欄は null、yes_logp / no_logp は入る。"""
    scorer, returned = distinct_scorer(None)
    run_dir, captured = execute_fixed_with_engines(
        without_top_k(anchored(D_CONFIG, pool_dirs["pilot"])), tmp_path, scorer
    )
    assert captured == {"top_k": None}
    assert read_json(run_dir / "metrics.json")["forced_choice"]["top_k"] is None
    rows = read_jsonl_rows(run_dir)
    assert rows
    for row in rows:
        assert row["top_k"] is None and row["top_k_mass"] is None
        assert bits(row["yes_logp"]) == bits(returned[row["prompt"]].yes_logprob)


def test_numeric_rows_do_not_get_the_forced_choice_fields(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """数値群の行は変えない(読み7)。pilot の config を B0 のまま回す。"""
    config = anchored(PILOT_CONFIG, pool_dirs["pilot"])
    scorer, _ = distinct_scorer(DECIDED_TOP_K)
    run_dir = run.execute(
        config,
        config_path=write_config(config, tmp_path / "config.yaml"),
        run_dir=tmp_path / "run",
        generator=lambda prompts: ["I cannot say."] * len(prompts),
        scorer=scorer,
    )
    rows = read_jsonl_rows(run_dir)
    numeric = [row for row in rows if row["group"] != "comparison"]
    binary = [row for row in rows if row["group"] == "comparison"]
    assert numeric and binary
    for row in numeric:
        assert not {"yes_logp", "no_logp", "top_k", "top_k_mass"} & set(row)
    for row in binary:
        assert len(row["top_k"]) == DECIDED_TOP_K


@pytest.mark.parametrize("declared", [True, False])
def test_the_fixed_route_stops_when_the_scorer_disagrees_with_the_declaration(
    pool_dirs: dict[str, Path], tmp_path: Path, declared: bool
) -> None:
    """★宣言したのに上位 k が返らない / 宣言していないのに返る は、黙って記録せずに止める(読み6)。"""
    config = anchored(D_CONFIG, pool_dirs["pilot"])
    if not declared:
        config = without_top_k(config)
    scorer, _ = distinct_scorer(None if declared else DECIDED_TOP_K)
    with pytest.raises(ForcedChoiceContractError, match=TOP_K_KEY):
        execute_fixed_with_engines(config, tmp_path, scorer)
    assert not list((tmp_path / "run" / "predictions").glob("*.jsonl"))


def test_a_broken_declaration_stops_every_route_before_the_run_directory(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """壊れた宣言は 3 経路とも重みを読む前・run ディレクトリを作る前に止まる(読み2)。"""
    def broken(path: Path, pool_dir: Path | None) -> dict[str, Any]:
        config = load_config(path) if pool_dir is None else anchored(path, pool_dir)
        config["eval"]["forced_choice_top_k"] = 0
        return config

    forbidden = capturing_build_engines(lambda prompts: pytest.fail("採点した"), {})
    cases: list[tuple[str, Callable[[Mapping[str, Any], Path], Any], dict[str, Any]]] = [
        (
            "fixed",
            lambda config, target: run.execute(config, config_path=D_CONFIG, run_dir=target),
            broken(D_CONFIG, pool_dirs["pilot"]),
        ),
        (
            "sweep",
            lambda config, target: run.execute_threshold_sweep(
                config, config_path=S_D_CONFIG, run_dir=target
            ),
            broken(S_D_CONFIG, pool_dirs["s"]),
        ),
        (
            "calibration",
            lambda config, target: calibration_run.execute_calibration(
                config, config_path=C_CONFIG, run_dir=target
            ),
            broken(C_CONFIG, None),
        ),
    ]
    for name, execute, config in cases:
        target = tmp_path / name
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(run, "build_engines", forbidden)
            patch.setattr(calibration_run, "build_engines", forbidden)
            with pytest.raises(ConfigError, match=TOP_K_KEY):
                execute(config, target)
        assert not target.exists(), name


def test_the_sweep_route_passes_k_and_rows_carry_the_top_k(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★掃引の経路(S-(d))も宣言の k を渡し、行に 2 欄を足す。yes_logp / no_logp は採点器の値のまま。"""
    config = anchored(S_D_CONFIG, pool_dirs["s"])
    scorer, returned = distinct_scorer(DECIDED_TOP_K)
    captured: dict[str, Any] = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(run, "build_engines", capturing_build_engines(scorer, captured))
        run_dir = run.execute_threshold_sweep(
            config,
            config_path=write_config(config, tmp_path / "config.yaml"),
            run_dir=tmp_path / "run",
        )
    assert captured == {"top_k": DECIDED_TOP_K}
    assert read_json(run_dir / "metrics.json")["forced_choice"]["top_k"] == DECIDED_TOP_K
    rows = read_jsonl_rows(run_dir)
    assert len(rows) == len(returned) > 0
    for row in rows:
        choice = returned[row["prompt"]]
        assert row["answer"] is choice.answer
        assert bits(row["yes_logp"]) == bits(choice.yes_logprob)
        assert bits(row["no_logp"]) == bits(choice.no_logprob)
        assert {key: row[key] for key in ("top_k", "top_k_mass")} == expected_top_k_fields(choice)


def test_the_calibration_route_passes_k_and_rows_carry_the_top_k(tmp_path: Path) -> None:
    """★(c) の較正の経路も強制選択の forward なので、同じ 2 欄を持つ(読み1)。"""
    config = load_config(C_CONFIG)
    scorer, returned = distinct_scorer(DECIDED_TOP_K)
    captured: dict[str, Any] = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(calibration_run, "build_engines", capturing_build_engines(scorer, captured))
        run_dir = calibration_run.execute_calibration(
            config, config_path=C_CONFIG, run_dir=tmp_path / "run"
        )
    assert captured == {"top_k": DECIDED_TOP_K}
    metrics = read_json(run_dir / "metrics.json")
    assert metrics["forced_choice"]["top_k"] == DECIDED_TOP_K
    rows = read_json(run_dir / calibration.ROWS_FILENAME)["rows"]
    assert len(rows) == len(returned) > 0
    for row in rows:
        choice = returned[row["prompt"]]
        assert bits(row["yes_logp"]) == bits(choice.yes_logprob)
        assert {key: row[key] for key in ("top_k", "top_k_mass")} == expected_top_k_fields(choice)


def test_every_dry_run_reports_the_declaration(pool_dirs: dict[str, Path]) -> None:
    """dry-run の報告(3 経路)に宣言の値。掃引と較正は置き物の上位 k で記録の組み立てを通す。"""
    fixed_report = run.dry_run(anchored(D_CONFIG, pool_dirs["pilot"]))
    assert fixed_report["forced_choice_top_k"] == DECIDED_TOP_K
    sweep_report = run.threshold_sweep_dry_run(anchored(S_D_CONFIG, pool_dirs["s"]))
    assert sweep_report["forced_choice_top_k"] == DECIDED_TOP_K
    calibration_report = calibration_run.calibration_dry_run(load_config(C_CONFIG))
    assert calibration_report["forced_choice_top_k"] == DECIDED_TOP_K
    undeclared = run.threshold_sweep_dry_run(without_top_k(anchored(S_D_CONFIG, pool_dirs["s"])))
    assert undeclared["forced_choice_top_k"] is None
    assert undeclared["predictions_by_response"] == sweep_report["predictions_by_response"]


def test_the_top_k_line_says_whether_it_is_recorded() -> None:
    assert "20" in run.top_k_line(20) and "判定には使わない" in run.top_k_line(20)
    assert TOP_K_KEY in run.top_k_line(None)
