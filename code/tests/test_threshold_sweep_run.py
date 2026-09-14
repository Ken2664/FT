"""閾値掃引(R8・S)の記録の経路(PLAN-026 I4。§4.5)。

答える問い: 「θ を動かす掃引の項目を、4 値分解を通さずに項目ごとの logp として記録でき、
宣言と食い違うプールを重みを読む前に止めるか」

**モデルの重みは 1 度も読まない**(採点器を差し替える。`test_run_real.py` と同じ)。
**ここに出る数値は実験結果ではない。**件数は組合せ論的な帰結である。

ここで固定する最重要の性質:
  - **R8 の config は pilot の config と宣言した 4 欄だけが違う**
  - **R8 の掃引プールを解くと、`classify` を呼ばずに項目ごとの logp が 8,160 行書かれる**
    (T3 4,080 + T1b 4,080)。logp は採点器が返した値そのもので、`answer` は判定規則の答えのまま
  - **metrics.json は `kind: threshold_sweep` で、率を 1 つも持たない**
  - **掃引の項目を固定オフセットの経路に渡すと止まる。宣言があるのに掃引のプールでない config も止まる。**
    どちらも重みを読む前・run ディレクトリを作る前(PLAN-026 §4.5 読み1)
  - 掃引の経路は、manifest と config の食い違い・1 項目の欠けで止まり、採点器を呼ばない

**repo の data/generated/ の items.jsonl を当てにしない**(git に無い)。module の fixture で
パイロット用プールを組み直し(約 8 秒)、R8・S の掃引プールと一緒に tmp に書く。
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import preflight
import pytest
import yaml

from code import artifacts
from code.config import ConfigError, load_config
from code.data_gen import eval_pool, sweep_pool
from code.data_gen.battery_items import Item, read_items, write_items
from code.data_gen.hashing import sha256_file
from code.eval import run
from code.eval.battery import t3_comparison
from code.eval.forced_choice import ForcedChoice, ForcedChoiceScorer, choose_from_logprobs

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT_CONFIG = REPO_ROOT / "configs" / "exp_order6b_pilot.yaml"
R8_CONFIG = REPO_ROOT / "configs" / "exp_order6b_r8.yaml"

# R8 の config が pilot の config と違ってよい欄(configs/exp_order6b_r8.yaml の冒頭の注記)。
R8_DIFFERING_KEYS = {
    "experiment.id",
    "eval.anchor_manifest",
    "eval.batteries",
    "eval.threshold_sweep_arm",
}

# 組合せ論的な件数(PLAN-026 §3.2・§3.7 / ADR-080 決定3)。**実験結果ではない。**
N_SWEEP_CELLS = 12  # (T3・T1b) × 既知性 3 × carry 2 の併合セル
PAIRS_PER_CELL = 20
N_R8_BY_TASK_TYPE = {"t3": 4080, "t1b": 4080}
N_S_BY_TASK_TYPE = {"t3": 1200, "t1b": 1200}

# 判定規則に渡す候補 id(1 綴りずつ)。**重みもトークナイザも要らない。**
CANDIDATE_IDS: Mapping[bool, tuple[int, ...]] = {True: (0,), False: (1,)}
# 3 項目に 1 つを Yes と No の同点にする(判定規則の「同点は No」が記録に残るか見るため)
TIE_EVERY = 3


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)の呼び出しを止める(`test_run_real.py` と同じ)。"""
    monkeypatch.setattr(artifacts, "_capture", stub_capture)


def stub_capture(command: Sequence[str]) -> str:
    return f"<stub: {' '.join(command)}>"


def forbidden(name: str) -> Callable[..., Any]:
    """呼ばれたら落ちる関数。**呼ばれないこと**を検査する差し替えに使う。"""

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"{name} を呼んではならない")

    return refuse


def rule_scorer() -> tuple[ForcedChoiceScorer, dict[str, ForcedChoice]]:
    """判定規則(`choose_from_logprobs`)で答えを決める採点器と、返した値の控え(プロンプト -> 結果)。

    対数尤度はプロンプトの順に変わる値で、`TIE_EVERY` 項目に 1 つは同点にする。**意味の無い値である。**
    """
    returned: dict[str, ForcedChoice] = {}

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        choices = []
        for prompt in prompts:
            index = len(returned)
            yes = -(index % 7) / 8
            no = yes if index % TIE_EVERY == 0 else -(index % 5) / 8
            choice = choose_from_logprobs([yes, no], CANDIDATE_IDS)
            returned[prompt] = choice
            choices.append(choice)
        return choices

    return scorer, returned


def write_config(config: Mapping[str, Any], path: Path) -> Path:
    text = yaml.safe_dump(dict(config), allow_unicode=True, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    return path


def sweep_config(pool_dir: Path, *, arm: str | None) -> dict[str, Any]:
    """R8 の config の anchor を tmp のプールに向け、宣言を差し替える(None = 宣言なし)。"""
    config = load_config(R8_CONFIG)
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    config["eval"]["threshold_sweep_arm"] = arm
    return config


def pilot_config(pool_dir: Path) -> dict[str, Any]:
    """pilot の config(B0。宣言なし)の anchor を tmp のプールに向ける。"""
    config = load_config(PILOT_CONFIG)
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    return config


def flatten(tree: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """入れ子の config を `a.b.c` の鍵の辞書にする(`test_order6b_pilot.py` と同じ形)。"""
    flat: dict[str, Any] = {}
    for key, value in tree.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.update(flatten(value, f"{dotted}."))
        else:
            flat[dotted] = value
    return flat


def differing_keys(first: Mapping[str, Any], second: Mapping[str, Any]) -> set[str]:
    a, b = flatten(first), flatten(second)
    return {key for key in set(a) | set(b) if a.get(key, object()) != b.get(key, object())}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def all_keys(tree: Any) -> Iterator[str]:
    """入れ子の辞書・リストのすべての鍵。"""
    if isinstance(tree, Mapping):
        for key, value in tree.items():
            yield str(key)
            yield from all_keys(value)
    elif isinstance(tree, list):
        for value in tree:
            yield from all_keys(value)


@pytest.fixture(scope="module")
def pool_dirs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """パイロット用プールと R8・S の掃引プールを tmp に書く(約 8 秒。module で 1 度だけ)。"""
    config = load_config(PILOT_CONFIG)
    root = tmp_path_factory.mktemp("battery")
    source = eval_pool.build(config)
    dirs = {"pilot": root / "pilot", "r8": root / "pilot_sweep_r8", "s": root / "pilot_sweep_s"}
    eval_pool.write_pool(source, dirs["pilot"])
    for arm in ("r8", "s"):
        eval_pool.write_pool(sweep_pool.build_sweep_pool(config, source, arm), dirs[arm])
    return dirs


def execute_sweep(
    config: Mapping[str, Any], tmp: Path
) -> tuple[Path, dict[str, ForcedChoice]]:
    """掃引の経路を差し替えた採点器で本実行する。**4 値分解と重みの読み込みを例外に差し替えて回す。**"""
    config_path = write_config(config, tmp / "config.yaml")
    scorer, returned = rule_scorer()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts, "_capture", stub_capture)
        for name in ("classify", "metrics_by_reference_rule", "response_builder", "build_engines"):
            patch.setattr(run, name, forbidden(name))
        run_dir = run.execute_threshold_sweep(
            config, config_path=config_path, run_dir=tmp / "run", scorer=scorer
        )
    return run_dir, returned


@pytest.fixture(scope="module")
def executed_r8(
    pool_dirs: dict[str, Path], tmp_path_factory: pytest.TempPathFactory
) -> dict[str, Any]:
    """R8 を本実行した run(module で 1 度だけ)。"""
    run_dir, returned = execute_sweep(
        sweep_config(pool_dirs["r8"], arm="r8"), tmp_path_factory.mktemp("r8")
    )
    return {"run_dir": run_dir, "returned": returned}


# --------------------------------------------------------------------------
# config(PLAN-026 §4.5 読み1)
# --------------------------------------------------------------------------


def test_r8_config_differs_from_the_pilot_config_only_in_the_declared_keys() -> None:
    """★R8 の config は pilot の config と宣言した 4 欄だけが違う。"""
    pilot, r8 = load_config(PILOT_CONFIG), load_config(R8_CONFIG)
    assert differing_keys(pilot, r8) == R8_DIFFERING_KEYS
    assert r8["eval"]["threshold_sweep_arm"] == "r8"
    assert r8["eval"]["batteries"] == [t3_comparison.GROUP]
    assert "threshold_sweep_arm" not in pilot["eval"]


def test_data_checks_pass_on_the_r8_config() -> None:
    """★R8 の config で preflight の data_checks が 7 件すべて PASS(コミット済み manifest。items は要らない)。"""
    results = preflight.data_checks(preflight.load_config(R8_CONFIG))
    assert {r.name for r in results} == set(preflight.DATA_CHECK_NAMES)
    assert {r.status for r in results} == {preflight.Status.PASS}, [
        (r.name, r.detail) for r in results
    ]


def test_the_declaration_must_be_a_name_or_null() -> None:
    config = load_config(R8_CONFIG)
    config["eval"]["threshold_sweep_arm"] = 8
    with pytest.raises(ConfigError, match="threshold_sweep_arm"):
        run.declared_threshold_sweep_arm(config)
    config["eval"]["threshold_sweep_arm"] = None
    assert run.declared_threshold_sweep_arm(config) is None
    assert run.declared_threshold_sweep_arm(load_config(PILOT_CONFIG)) is None


# --------------------------------------------------------------------------
# 記録(PLAN-026 §4.5 読み2)
# --------------------------------------------------------------------------


def test_r8_writes_one_row_per_item_without_the_four_way_split(
    executed_r8: dict[str, Any], pool_dirs: dict[str, Path]
) -> None:
    """★8,160 行(T3 4,080 + T1b 4,080)。classify・4 値分解・重みの読み込みを例外にしても通る。"""
    predictions = executed_r8["run_dir"] / "predictions"
    rows_by_task_type = {
        task_type: read_jsonl(predictions / f"threshold_sweep.{task_type}.jsonl")
        for task_type in N_R8_BY_TASK_TYPE
    }
    assert {name: len(rows) for name, rows in rows_by_task_type.items()} == N_R8_BY_TASK_TYPE
    assert sorted(path.name for path in predictions.iterdir()) == [
        "threshold_sweep.t1b.jsonl",
        "threshold_sweep.t3.jsonl",
    ]
    item_ids = [row["item_id"] for rows in rows_by_task_type.values() for row in rows]
    items = read_items(pool_dirs["r8"] / "items.jsonl")
    # 1 項目 1 行、項目の並びのまま(タスク型ごと)
    assert item_ids == [item.item_id for item in items]
    assert all(
        row["task_type"] == task_type
        for task_type, rows in rows_by_task_type.items()
        for row in rows
    )


def test_rows_keep_the_scorer_values_and_the_sweep_fields(
    executed_r8: dict[str, Any], pool_dirs: dict[str, Path]
) -> None:
    """★logp は採点器の返した値そのもの。`answer` は判定規則のまま(同点は No)。T = t + θ・truth・併合セル。"""
    returned = executed_r8["returned"]
    manifest = json.loads((pool_dirs["r8"] / "manifest.json").read_text(encoding="utf-8"))
    cells = manifest["fill"]["cells"]
    rows = [
        row
        for task_type in N_R8_BY_TASK_TYPE
        for row in read_jsonl(
            executed_r8["run_dir"] / "predictions" / f"threshold_sweep.{task_type}.jsonl"
        )
    ]
    ties = 0
    for row in rows:
        choice = returned[row["prompt"]]
        assert (row["yes_logp"], row["no_logp"], row["answer"]) == (
            choice.yes_logprob,
            choice.no_logprob,
            choice.answer,
        )
        if row["yes_logp"] == row["no_logp"]:
            ties += 1
            assert row["answer"] is False
        a, b = row["operands"]
        assert row["t"] == a + b
        assert row["threshold"] == row["t"] + row["threshold_offset"]
        assert row["truth"] == t3_comparison.comparison_answer(
            row["t"], row["polarity"], row["threshold"]
        )
        assert row["category"] == t3_comparison.category_for(row["task_type"], row["polarity"])
        assert [a, b] in cells[row["sweep_cell"]]["pairs"]
        assert row["response"].startswith("Yes " if row["answer"] else "No ")
        assert "classification" not in row and "parsed" not in row
    # 同点は TIE_EVERY 項目に 1 つ以上ある(対数尤度がたまたま一致する項目もある)
    assert ties >= len(rows) // TIE_EVERY
    assert any(row["answer"] for row in rows)


def test_metrics_record_the_sweep_without_any_rate(
    executed_r8: dict[str, Any], pool_dirs: dict[str, Path]
) -> None:
    """★`kind: threshold_sweep`。`_rate` を含む鍵が 1 つも無い。件数は 12 × 2 × 17 × 20。"""
    payload = json.loads((executed_r8["run_dir"] / "metrics.json").read_text(encoding="utf-8"))
    assert payload["kind"] == run.THRESHOLD_SWEEP_KIND
    assert not [key for key in all_keys(payload) if "_rate" in key]
    assert "by_batch" not in payload and "primary_reference_rule" not in payload

    sweep = payload["threshold_sweep"]
    offsets = load_config(R8_CONFIG)["eval"]["threshold_sweep"]["offsets"]["r8"]
    assert sweep["arm"] == "r8"
    assert sweep["threshold_offsets"] == offsets
    assert sweep["polarities"] == list(sweep_pool.POLARITIES)
    assert len(sweep["n_items_by_cell"]) == N_SWEEP_CELLS
    for by_polarity in sweep["n_items_by_cell"].values():
        assert by_polarity == {
            polarity: {str(theta): PAIRS_PER_CELL for theta in offsets}
            for polarity in sweep_pool.POLARITIES
        }
    assert sweep["predictions"] == {
        f"threshold_sweep.{task_type}": n for task_type, n in N_R8_BY_TASK_TYPE.items()
    }
    manifest = json.loads((pool_dirs["r8"] / "manifest.json").read_text(encoding="utf-8"))
    assert sweep["source_pool_pairs_hash"] == manifest["fill"]["source_pool_pairs_hash"]

    # 来歴は固定オフセットの経路と同じ形(項目集合のバイト列・K の出どころ・アダプタ無しの注記)
    assert payload["pool"]["n_items"] == sum(N_R8_BY_TASK_TYPE.values())
    assert payload["pool"]["items_sha256"] == sha256_file(pool_dirs["r8"] / "items.jsonl")
    assert payload["pool"]["pairs_hash"] == manifest["pairs_hash"]
    assert payload["coverage"]["coverage_k"] > 0
    assert payload["adapter"] is None and payload["adapter_note"] == run.NO_ADAPTER_NOTE
    # 採点器を差し替えた実行なので forced_choice 欄は無い(重みを読んだ実行にしか無い)
    assert "forced_choice" not in payload

    log = (executed_r8["run_dir"] / "log.txt").read_text(encoding="utf-8")
    assert "閾値掃引: 腕=r8" in log and "correct=" not in log


def test_s_goes_through_the_same_route(pool_dirs: dict[str, Path], tmp_path: Path) -> None:
    """S(2,400 行)も同じ経路・同じ宣言の鍵。項目は R8 の部分集合。"""
    config = sweep_config(pool_dirs["s"], arm="s")
    run_dir, _ = execute_sweep(config, tmp_path)
    payload = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert payload["threshold_sweep"]["predictions"] == {
        f"threshold_sweep.{task_type}": n for task_type, n in N_S_BY_TASK_TYPE.items()
    }
    offsets = config["eval"]["threshold_sweep"]["offsets"]["s"]
    assert all(
        by_theta == {str(theta): PAIRS_PER_CELL for theta in offsets}
        for by_polarity in payload["threshold_sweep"]["n_items_by_cell"].values()
        for by_theta in by_polarity.values()
    )
    s_ids = {item.item_id for item in read_items(pool_dirs["s"] / "items.jsonl")}
    r8_ids = {item.item_id for item in read_items(pool_dirs["r8"] / "items.jsonl")}
    assert s_ids < r8_ids


def test_dry_run_passes_constant_answers_through_every_item(pool_dirs: dict[str, Path]) -> None:
    """掃引の dry-run: 件数・定数の答えでの行数・category ごとの例のプロンプト 1 つ。率は出さない。"""
    report = run.threshold_sweep_dry_run(sweep_config(pool_dirs["r8"], arm="r8"))
    assert report["n_items"] == sum(N_R8_BY_TASK_TYPE.values())
    expected_rows = {
        f"threshold_sweep.{task_type}": n for task_type, n in N_R8_BY_TASK_TYPE.items()
    }
    assert report["predictions_by_response"] == {
        label: expected_rows for label in run.DRY_RUN_FORCED_CHOICES
    }
    assert sorted(report["example_prompts"]) == sorted(t3_comparison.CATEGORY_AXES)
    assert not [key for key in all_keys(report) if "_rate" in key]


# --------------------------------------------------------------------------
# 固定オフセットの経路は掃引を受け付けない(PLAN-026 §4.5 読み1)
# --------------------------------------------------------------------------


# (掃引の宣言, anchor のプール)。どれも固定オフセットの経路では解けない
FIXED_ROUTE_REFUSALS = {
    "declared_and_sweep_pool": ("r8", "r8"),
    "undeclared_sweep_pool": (None, "r8"),
    "declared_fixed_pool": ("r8", "pilot"),
}


def refused_config(pool_dirs: dict[str, Path], case: str) -> dict[str, Any]:
    arm, pool = FIXED_ROUTE_REFUSALS[case]
    return sweep_config(pool_dirs[pool], arm=arm)


@pytest.mark.parametrize("case", sorted(FIXED_ROUTE_REFUSALS))
def test_fixed_route_entry_points_refuse_the_sweep(
    pool_dirs: dict[str, Path], case: str
) -> None:
    """★`load_pool_items`・`dry_run`・`evaluate_pool` は掃引の宣言も掃引のプールも受け付けない。"""
    config = refused_config(pool_dirs, case)
    with pytest.raises(ConfigError, match="閾値掃引"):
        run.load_pool_items(config)
    with pytest.raises(ConfigError, match="閾値掃引"):
        run.dry_run(config)
    with pytest.raises(ConfigError, match="閾値掃引"):
        run.evaluate_pool(config, generator=forbidden("generator"), scorer=forbidden("scorer"))


@pytest.mark.parametrize("case", sorted(FIXED_ROUTE_REFUSALS))
def test_execute_refuses_the_sweep_before_weights_and_the_run_dir(
    pool_dirs: dict[str, Path], case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★`execute` は重みを読む前・run ディレクトリを作る前に止まる。"""
    monkeypatch.setattr(run, "build_engines", forbidden("build_engines"))
    config = refused_config(pool_dirs, case)
    run_dir = tmp_path / "run"
    with pytest.raises(ConfigError, match="閾値掃引"):
        run.execute(
            config,
            config_path=write_config(config, tmp_path / "config.yaml"),
            run_dir=run_dir,
            generator=forbidden("generator"),
            scorer=forbidden("scorer"),
        )
    assert not run_dir.exists()


def test_the_pilot_config_still_dry_runs_on_the_fixed_route(pool_dirs: dict[str, Path]) -> None:
    """B0(pilot の config。宣言なし・パイロット用プール)は今までどおり固定オフセットの経路で通る。"""
    report = run.dry_run(pilot_config(pool_dirs["pilot"]))
    assert report["n_items"] == len(read_items(pool_dirs["pilot"] / "items.jsonl"))
    assert "comparison" in report["by_batch"]


def test_the_pilot_config_on_a_sweep_pool_stops_at_the_pool_kind(
    pool_dirs: dict[str, Path],
) -> None:
    """pilot の config の anchor だけを掃引のプールに替えると、群の検査より先にプールの種類で止まる。"""
    with pytest.raises(ConfigError, match="閾値掃引のプール"):
        run.load_pool_items(pilot_config(pool_dirs["r8"]))


# --------------------------------------------------------------------------
# 掃引の経路の検査(どれも採点器を呼ばず、run ディレクトリを作らない)
# --------------------------------------------------------------------------


def without_one_item(pool_dirs: dict[str, Path], tmp_path: Path) -> Path:
    """R8 のプールから 1 項目だけ落とした写し(manifest はそのまま)。"""
    out = tmp_path / "pilot_sweep_r8_missing"
    out.mkdir()
    items: list[Item] = read_items(pool_dirs["r8"] / "items.jsonl")
    write_items(out / "items.jsonl", items[:100] + items[101:])
    (out / "manifest.json").write_bytes((pool_dirs["r8"] / "manifest.json").read_bytes())
    return out


def sweep_refusal(pool_dirs: dict[str, Path], tmp_path: Path, case: str) -> dict[str, Any]:
    """掃引の経路が止めるべき config を組む。"""
    if case == "undeclared":
        return sweep_config(pool_dirs["r8"], arm=None)
    if case == "fixed_pool":
        return sweep_config(pool_dirs["pilot"], arm="r8")
    if case == "other_arm":
        return sweep_config(pool_dirs["r8"], arm="s")
    if case == "unknown_arm":
        return sweep_config(pool_dirs["r8"], arm="r9")
    if case == "other_offsets":
        config = sweep_config(pool_dirs["r8"], arm="r8")
        config["eval"]["threshold_sweep"]["offsets"]["r8"] = config["eval"]["threshold_sweep"][
            "offsets"
        ]["r8"][:-1]
        return config
    if case == "other_seed":
        config = sweep_config(pool_dirs["r8"], arm="r8")
        config["eval"]["pool_seed"] += 1
        return config
    if case == "one_item_missing":
        return sweep_config(without_one_item(pool_dirs, tmp_path), arm="r8")
    raise ValueError(case)


# 止まる理由の文言(ConfigError の match)
SWEEP_REFUSALS = {
    "undeclared": "宣言を要る",
    "fixed_pool": "閾値掃引のプールではない",
    "other_arm": "腕 'r8' のものではない|腕 's' のものではない",
    "unknown_arm": "腕 'r9' が無い",
    "other_offsets": "threshold_offsets",
    "other_seed": "selection.seed",
    "one_item_missing": "そろっていない",
}


@pytest.mark.parametrize("case", sorted(SWEEP_REFUSALS))
def test_the_sweep_route_stops_before_scoring_and_the_run_dir(
    pool_dirs: dict[str, Path], tmp_path: Path, case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★宣言なし・固定のプール・腕や θ やシードの食い違い・1 項目の欠けで止まる。採点器を呼ばない。"""
    monkeypatch.setattr(run, "build_engines", forbidden("build_engines"))
    config = sweep_refusal(pool_dirs, tmp_path, case)
    run_dir = tmp_path / "run"
    with pytest.raises(ConfigError, match=SWEEP_REFUSALS[case]):
        run.execute_threshold_sweep(
            config,
            config_path=write_config(copy.deepcopy(config), tmp_path / "config.yaml"),
            run_dir=run_dir,
            scorer=forbidden("scorer"),
        )
    assert not run_dir.exists()
    with pytest.raises(ConfigError, match=SWEEP_REFUSALS[case]):
        run.threshold_sweep_dry_run(config)


# --------------------------------------------------------------------------
# 入口(`main` が宣言で振り分ける)
# --------------------------------------------------------------------------


def test_main_dispatches_on_the_declaration(
    pool_dirs: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """★`main` は宣言があれば掃引の経路に、無ければ固定オフセットの経路に回す(--dry-run も本実行も)。"""
    r8_path = write_config(sweep_config(pool_dirs["r8"], arm="r8"), tmp_path / "r8.yaml")
    pilot_path = write_config(pilot_config(pool_dirs["pilot"]), tmp_path / "pilot.yaml")

    assert run.main(["--config", str(r8_path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "閾値掃引の配線確認" in out and f"項目数: {sum(N_R8_BY_TASK_TYPE.values())}" in out

    calls: list[str] = []
    monkeypatch.setattr(run, "execute", lambda config, **_: calls.append("execute"))
    monkeypatch.setattr(
        run, "execute_threshold_sweep", lambda config, **_: calls.append("execute_threshold_sweep")
    )
    assert run.main(["--config", str(r8_path)]) == 0
    assert run.main(["--config", str(pilot_path)]) == 0
    assert calls == ["execute_threshold_sweep", "execute"]

    monkeypatch.setattr(run, "dry_run", forbidden("dry_run"))
    monkeypatch.setattr(run, "print_dry_run", forbidden("print_dry_run"))
    assert run.main(["--config", str(r8_path), "--dry-run"]) == 0
