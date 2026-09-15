"""① の前置き(PLAN-026 I6)と、前置きのある run の preflight 検査6(I7)。

答える問い: 「前置きを宣言した run では全群の文面の先頭に同じ前置きが項目ごとの決まった並びで置かれ、
宣言しない run の文面は 1 バイトも変わらず、どちらも記録に残るか」

**モデルの重みは 1 度も読まない**(生成器と採点器を差し替える。`test_threshold_sweep_run.py` と同じ)。
**ここに出る数値は実験結果ではない。**件数・並びの数はハッシュと組合せ論の帰結である。

ここで固定する最重要の性質:
  - **前置きの無い run の文面は 1 バイトも変わらない**(パイロット用プール 1,640・R8 8,160・S 2,400 の
    文面の sha256 を、I6 の実装の前のコードで取って固定した)
  - **前置きのある run の文面 = 並べた前置き + 空行 + 各群の文面**。前置きの文字列は群・経路に依らず、
    並びは item_id だけで決まる(n! = 24 通り。パイロット用プールの T1・T2・T3・T1b それぞれで 24 通りすべてが出る)
  - **行は ADR-079 決定3 の 4 行と 1 文字も違わない**。前置きを宣言する config は順6b の ① の腕だけ
  - `metrics.json` の `preamble` 欄は前置きの無い run で null、ある run で行・sha256・並びの数(両方の経路)
  - **preflight の検査6 は前置きのある run でアンカーと比べず SKIP**。訓練側の書式が破れていれば FAIL。
    前置きの無い run の検査6 は変わらない
  - 壊れた宣言は重みを読む前・run ディレクトリを作る前に止まる。桁数掃引は前置きを宣言した config を拒む

**repo の data/generated/ の items.jsonl を当てにしない**(git に無い)。module の fixture で
パイロット用プールと R8・S の掃引プールを tmp に組み直す(約 8 秒)。
"""

from __future__ import annotations

import copy
import itertools
import json
import math
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import preflight
import pytest
import yaml

from code import artifacts
from code.config import ConfigError, load_config
from code.data_gen import eval_pool, sweep_pool
from code.data_gen.battery_items import Item
from code.data_gen.hashing import canonical_json, sha256_text
from code.eval import preamble, run, sweep
from code.eval.battery import numeric_sum, t3_comparison
from code.eval.forced_choice import ForcedChoice, ForcedChoiceScorer, choose_from_logprobs

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"
PILOT_CONFIG = CONFIG_DIR / "exp_order6b_pilot.yaml"
R8_CONFIG = CONFIG_DIR / "exp_order6b_r8.yaml"
S_PREAMBLE_CONFIG = CONFIG_DIR / "exp_order6b_s_preamble.yaml"

# ADR-079 決定3(PLAN-026 §3.3)の 4 行。**config の行はこれと 1 文字も違ってはならない。**
ADR_079_LINES = ("900>800? Yes", "250>610? No", "340<780? Yes", "920<150? No")

# 前置きを宣言してよい config(順6b の ① の腕だけ。本番・pilot・R8 は持たない。ADR-078 決定2)。
# 固定オフセットの ① の config は I8 で足す(PLAN-026 §4.7 の仕様の穴)。
PREAMBLE_CONFIGS = {S_PREAMBLE_CONFIG.name}

# S-① の config が R8 の config と違ってよい欄(configs/exp_order6b_s_preamble.yaml の冒頭の注記)。
S_PREAMBLE_DIFFERING_KEYS = {
    "experiment.id",
    "eval.anchor_manifest",
    "eval.threshold_sweep_arm",
    "eval.preamble",
}

# **I6 の実装の前のコード**で取った、前置きの無い文面の sha256
# (`sha256(canonical_json(sorted((item_id, prompt))))`。2026-09-15 その59。実験結果ではない)。
# 固定オフセットはパイロット用プール 1,640 項目、掃引は R8 8,160・S 2,400 項目。
PROMPTS_SHA256_BEFORE_I6 = {
    "fixed": "0791c032f7461cc3a469ca90e4011f6c7cc18368530dd5b8f1dbb9b751e5c5c6",
    "r8": "140442a768fe6dbf130d7183186681611ab29761070da19f70b1544225866c07",
    "s": "6f3a9e99294e7477afd55cf0af57ab6f35aa52dd90f9653188099453d7519a38",
}

# 並びの番号の回帰値(`sha256(canonical_json(["preamble_order", item_id])) mod 24`)。
# ハッシュの入力やタグを変えると落ちる —— 変えれば全項目の並びが動く。
PINNED_ORDER_INDEX = {
    "pilot.comparison.t1b_gt.77_12.threshold89-threshold_offset0": 22,
    "pilot.specificity.spec_mul.470_164": 18,
}

# ① の腕が解くタスク型(PLAN-026 §3 の表。①-bin = T3・T1b、①-num = T1・T2)。
PREAMBLE_ARM_TASK_TYPES = ("t3", "t1b", "t1", "t2")

# 判定規則に渡す候補 id(1 綴りずつ)。**重みもトークナイザも要らない。**
CANDIDATE_IDS: Mapping[bool, tuple[int, ...]] = {True: (0,), False: (1,)}
# 数値群の固定応答(parse_fail に落ちる文字列。**実験の刺激でも結果でもない**)
CONSTANT_RESPONSE = "I cannot say."
# 壊れた宣言(同じ行が重なる)
DUPLICATED_LINES = ["900>800? Yes", "900>800? Yes"]


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)の呼び出しを止める(`test_run_real.py` と同じ)。"""
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


# --------------------------------------------------------------------------
# 道具
# --------------------------------------------------------------------------


def write_config(config: Mapping[str, Any], path: Path) -> Path:
    text = yaml.safe_dump(dict(config), allow_unicode=True, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    return path


def flatten(tree: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """入れ子の config を `a.b.c` の鍵の辞書にする(`test_threshold_sweep_run.py` と同じ形)。"""
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


def prompts_digest(prompts: Mapping[str, str]) -> str:
    return sha256_text(canonical_json(sorted(prompts.items())))


def task_type(item: Item) -> str:
    """項目のタスク型(`code/analysis/frame.py` の `task_type_of` と同じ引き方。特異性は群の名前)。"""
    if item.group == t3_comparison.GROUP:
        return t3_comparison.task_type_of(item.category)
    if item.category in numeric_sum.CATEGORY_AXES:
        return numeric_sum.task_type_of(item.category)
    return item.group


def with_preamble_config(config: Mapping[str, Any], lines: Sequence[str] | None) -> dict[str, Any]:
    changed = copy.deepcopy(dict(config))
    changed["eval"]["preamble"] = None if lines is None else list(lines)
    return changed


def pilot_config(pool_dir: Path, lines: Sequence[str] | None = None) -> dict[str, Any]:
    """pilot の config(固定オフセット・5 群)の anchor を tmp のプールに向け、前置きを差し替える。

    **① の run の config ではない**(① は 3 群だけを解く。絞り方は I8)。前置きの配線を
    固定オフセットの経路の全群で確かめるための形である。
    """
    config = load_config(PILOT_CONFIG)
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    return with_preamble_config(config, lines)


def s_config(pool_dir: Path, *, with_lines: bool) -> dict[str, Any]:
    """S の掃引の config。前置きありは S-① の config、なしは R8 の config の腕を s にしたもの。"""
    config = load_config(S_PREAMBLE_CONFIG if with_lines else R8_CONFIG)
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    config["eval"]["threshold_sweep_arm"] = "s"
    return config


def r8_config(pool_dir: Path, lines: Sequence[str] | None = None) -> dict[str, Any]:
    config = load_config(R8_CONFIG)
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    return with_preamble_config(config, lines)


def fixed_prompts(config: Mapping[str, Any]) -> dict[str, str]:
    """固定オフセットの経路の文面(item_id -> 文面)。`render_prompts` を群ごとに通す。"""
    items = run.load_pool_items(config)
    template_set = config["data"]["eval_template_set"]
    prompts: dict[str, str] = {}
    for group in config["eval"]["batteries"]:
        group_items = [item for item in items if item.group == group]
        prompts.update(run.render_prompts(config, group, group_items, template_set=template_set))
    return prompts


def sweep_prompts(config: Mapping[str, Any]) -> dict[str, str]:
    return run.threshold_sweep_prompts(config, run.load_threshold_sweep_pool(config))


def recording_generator() -> tuple[Callable[[Sequence[str]], list[str]], list[str]]:
    """受け取ったプロンプトを控え、固定の応答を返す生成器。"""
    seen: list[str] = []

    def generator(prompts: Sequence[str]) -> list[str]:
        seen.extend(prompts)
        return [CONSTANT_RESPONSE for _ in prompts]

    return generator, seen


def recording_scorer() -> tuple[ForcedChoiceScorer, list[str]]:
    """受け取ったプロンプトを控え、判定規則で定数の答えを返す採点器(**意味の無い値**)。"""
    seen: list[str] = []

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        seen.extend(prompts)
        return [choose_from_logprobs([-0.25, -0.5], CANDIDATE_IDS) for _ in prompts]

    return scorer, seen


def predictions_by_item(run_dir: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted((run_dir / "predictions").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            rows[row["item_id"]] = row
    return rows


def expected_prompt(prompt_without: str, lines: Sequence[str], item_id: str) -> str:
    index = preamble.order_index(item_id, len(lines))
    return preamble.preamble_text(lines, index) + "\n\n" + prompt_without


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


@pytest.fixture(scope="module")
def plain_prompts(pool_dirs: dict[str, Path]) -> dict[str, dict[str, str]]:
    """前置きの無い文面(固定オフセット 1,640・R8 8,160・S 2,400)。"""
    return {
        "fixed": fixed_prompts(pilot_config(pool_dirs["pilot"])),
        "r8": sweep_prompts(r8_config(pool_dirs["r8"])),
        "s": sweep_prompts(s_config(pool_dirs["s"], with_lines=False)),
    }


# --------------------------------------------------------------------------
# 並びと連結(code/eval/preamble.py)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("n_lines", [1, 2, 3, 4, 5])
def test_nth_order_is_the_lexicographic_permutation(n_lines: int) -> None:
    """k 番目の並びは `itertools.permutations(range(n))` の k 番目と同じ(辞書順)。"""
    expected = list(itertools.permutations(range(n_lines)))
    assert preamble.n_orders(n_lines) == math.factorial(n_lines) == len(expected)
    assert [preamble.nth_order(n_lines, k) for k in range(len(expected))] == expected


@pytest.mark.parametrize("index", [-1, 24])
def test_nth_order_refuses_an_index_outside_the_orders(index: int) -> None:
    with pytest.raises(ValueError, match="並びの番号"):
        preamble.nth_order(len(ADR_079_LINES), index)


def test_order_index_depends_only_on_the_item_id() -> None:
    """★並びは item_id のハッシュだけで決まり(乱数なし)、ハッシュの規則は回帰値で固定する。"""
    for item_id, index in PINNED_ORDER_INDEX.items():
        assert preamble.order_index(item_id, len(ADR_079_LINES)) == index
        digest = sha256_text(canonical_json(["preamble_order", item_id]))
        assert int(digest, 16) % 24 == index


def test_the_preamble_is_the_ordered_lines_then_a_blank_line() -> None:
    """★連結 = 並べた行を改行でつなぎ、空行を 1 つ挟んで文面を続ける(ADR-079 決定3)。"""
    assert preamble.preamble_text(ADR_079_LINES, 0) == "\n".join(ADR_079_LINES)
    assert preamble.preamble_text(ADR_079_LINES, 23) == "\n".join(reversed(ADR_079_LINES))
    item_id = next(iter(PINNED_ORDER_INDEX))
    got = preamble.with_preamble("12+34=", ADR_079_LINES, item_id)
    order = preamble.nth_order(4, PINNED_ORDER_INDEX[item_id])
    assert got == "\n".join(ADR_079_LINES[i] for i in order) + "\n\n12+34="


def test_without_lines_the_prompt_is_returned_as_is() -> None:
    assert preamble.with_preamble("12+34=", None, "any") == "12+34="
    assert preamble.preamble_record(None) is None
    assert preamble.preamble_line(None) == "前置き: なし"


@pytest.mark.parametrize(
    "declared",
    [
        "900>800? Yes",
        [],
        [""],
        ["   "],
        [900],
        ["900>800? Yes\n250>610? No"],
        ["900>800? Yes\r"],
        DUPLICATED_LINES,
    ],
)
def test_a_broken_declaration_stops(declared: Any) -> None:
    with pytest.raises(ConfigError, match="eval.preamble"):
        preamble.declared_preamble({"eval": {"preamble": declared}})


def test_no_declaration_means_no_preamble() -> None:
    assert preamble.declared_preamble({"eval": {"preamble": None}}) is None
    assert preamble.declared_preamble({"eval": {}}) is None
    assert preamble.declared_preamble({}) is None


def test_the_record_carries_the_lines_and_their_sha256() -> None:
    record = preamble.preamble_record(ADR_079_LINES)
    assert record is not None
    assert record["lines"] == list(ADR_079_LINES)
    assert record["sha256"] == sha256_text("\n".join(ADR_079_LINES))
    assert record["n_orders"] == 24
    assert "評価アンカーではない" in record["note"]


# --------------------------------------------------------------------------
# config(PLAN-026 §4.7 読み1・読み5)
# --------------------------------------------------------------------------


def test_the_configured_lines_are_exactly_the_adr_079_lines() -> None:
    """★config の行は ADR-079 決定3 の 4 行と 1 文字も違わない(並びもその順)。"""
    assert preamble.declared_preamble(load_config(S_PREAMBLE_CONFIG)) == ADR_079_LINES


def test_s_preamble_config_differs_from_the_r8_config_only_in_the_declared_keys() -> None:
    r8, s_preamble = load_config(R8_CONFIG), load_config(S_PREAMBLE_CONFIG)
    assert differing_keys(r8, s_preamble) == S_PREAMBLE_DIFFERING_KEYS
    assert s_preamble["eval"]["threshold_sweep_arm"] == "s"
    assert s_preamble["eval"]["anchor_manifest"].endswith("pilot_sweep_s/manifest.json")
    assert s_preamble["eval"].get("few_shot_k") is None


def test_only_the_order6b_preamble_arms_declare_a_preamble() -> None:
    """★本番・pilot・R8 の config は前置きを持たない(本番の文面は 1 文字も変えない。ADR-078 決定2)。"""
    declaring = {
        path.name
        for path in sorted(CONFIG_DIR.glob("*.yaml"))
        if preamble.declared_preamble(load_config(path) or {}) is not None
    }
    assert declaring == PREAMBLE_CONFIGS


# --------------------------------------------------------------------------
# 文面(PLAN-026 §4.7 読み2・読み3)
# --------------------------------------------------------------------------


def test_prompts_without_a_preamble_are_byte_identical_to_before(
    plain_prompts: dict[str, dict[str, str]],
) -> None:
    """★前置きの無い run の文面は、I6 の実装の前と 1 バイトも変わらない(両方の経路)。"""
    assert {name: len(prompts) for name, prompts in plain_prompts.items()} == {
        "fixed": 1640,
        "r8": 8160,
        "s": 2400,
    }
    assert {
        name: prompts_digest(prompts) for name, prompts in plain_prompts.items()
    } == PROMPTS_SHA256_BEFORE_I6


def test_every_group_gets_the_same_preamble_before_its_own_text(
    pool_dirs: dict[str, Path], plain_prompts: dict[str, dict[str, str]]
) -> None:
    """★全群・全タスク型で、文面 = 並べた前置き + 空行 + 前置きの無い文面(固定オフセットの経路)。"""
    config = pilot_config(pool_dirs["pilot"], ADR_079_LINES)
    prompts = fixed_prompts(config)
    plain = plain_prompts["fixed"]
    assert prompts.keys() == plain.keys()
    items = run.load_pool_items(config)
    assert {task_type(item) for item in items} >= set(PREAMBLE_ARM_TASK_TYPES)
    for item in items:
        head, rest = prompts[item.item_id].split("\n\n", 1)
        assert rest == plain[item.item_id]
        assert sorted(head.split("\n")) == sorted(ADR_079_LINES)
        expected = expected_prompt(plain[item.item_id], ADR_079_LINES, item.item_id)
        assert prompts[item.item_id] == expected


def test_every_order_appears_in_each_preamble_task_type(pool_dirs: dict[str, Path]) -> None:
    """★パイロット用プールの T3・T1b・T1・T2 のそれぞれで、24 通りの並びがすべて出る(ハッシュの性質)。"""
    items = run.load_pool_items(pilot_config(pool_dirs["pilot"]))
    for kind in PREAMBLE_ARM_TASK_TYPES:
        orders = {
            preamble.order_index(item.item_id, len(ADR_079_LINES))
            for item in items
            if task_type(item) == kind
        }
        assert orders == set(range(24)), kind


def test_the_sweep_route_puts_the_same_preamble(
    pool_dirs: dict[str, Path], plain_prompts: dict[str, dict[str, str]]
) -> None:
    """★S-① の config で、掃引の経路の 2,400 項目にも同じ形で前置きが被さる。"""
    prompts = sweep_prompts(s_config(pool_dirs["s"], with_lines=True))
    plain = plain_prompts["s"]
    assert prompts.keys() == plain.keys()
    for item_id, prompt in prompts.items():
        assert prompt == expected_prompt(plain[item_id], ADR_079_LINES, item_id)


def test_the_same_item_id_gets_the_same_order_on_both_routes(
    pool_dirs: dict[str, Path],
) -> None:
    """R8 の 240 項目は固定オフセットの項目と同じ item_id で(ADR-030 決定5)、前置きも同じ並びになる。"""
    fixed = fixed_prompts(pilot_config(pool_dirs["pilot"], ADR_079_LINES))
    swept = sweep_prompts(r8_config(pool_dirs["r8"], ADR_079_LINES))
    shared = fixed.keys() & swept.keys()
    assert len(shared) == 240
    for item_id in shared:
        assert fixed[item_id].split("\n\n", 1)[0] == swept[item_id].split("\n\n", 1)[0]


# --------------------------------------------------------------------------
# 記録(PLAN-026 §4.7 読み4)
# --------------------------------------------------------------------------


def execute_fixed(config: Mapping[str, Any], tmp: Path) -> tuple[Path, list[str]]:
    """固定オフセットの経路を差し替えた生成器・採点器で本実行し、モデルに渡った文面を返す。"""
    generator, generated = recording_generator()
    scorer, scored = recording_scorer()
    run_dir = run.execute(
        config,
        config_path=write_config(config, tmp / "config.yaml"),
        run_dir=tmp / "run",
        generator=generator,
        scorer=scorer,
    )
    return run_dir, generated + scored


def test_the_fixed_route_sends_and_records_the_preamble(
    pool_dirs: dict[str, Path], plain_prompts: dict[str, dict[str, str]], tmp_path: Path
) -> None:
    """★固定オフセットの本実行: モデルに渡る文面・predictions の prompt・metrics.json・log.txt。"""
    config = pilot_config(pool_dirs["pilot"], ADR_079_LINES)
    run_dir, sent = execute_fixed(config, tmp_path)
    expected = {
        item_id: expected_prompt(prompt, ADR_079_LINES, item_id)
        for item_id, prompt in plain_prompts["fixed"].items()
    }
    assert sorted(sent) == sorted(expected.values())
    rows = predictions_by_item(run_dir)
    assert {item_id: row["prompt"] for item_id, row in rows.items()} == expected
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["preamble"] == preamble.preamble_record(ADR_079_LINES)
    log = (run_dir / "log.txt").read_text(encoding="utf-8")
    assert preamble.preamble_line(metrics["preamble"]) in log


def test_the_fixed_route_without_a_preamble_records_null(
    pool_dirs: dict[str, Path], plain_prompts: dict[str, dict[str, str]], tmp_path: Path
) -> None:
    run_dir, sent = execute_fixed(pilot_config(pool_dirs["pilot"]), tmp_path)
    assert sorted(sent) == sorted(plain_prompts["fixed"].values())
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "preamble" in metrics and metrics["preamble"] is None
    assert "前置き: なし" in (run_dir / "log.txt").read_text(encoding="utf-8")


def execute_sweep(config: Mapping[str, Any], tmp: Path) -> tuple[Path, list[str]]:
    scorer, scored = recording_scorer()
    run_dir = run.execute_threshold_sweep(
        config,
        config_path=write_config(config, tmp / "config.yaml"),
        run_dir=tmp / "run",
        scorer=scorer,
    )
    return run_dir, scored


@pytest.mark.parametrize("with_lines", [True, False])
def test_the_sweep_route_sends_and_records_the_preamble(
    pool_dirs: dict[str, Path],
    plain_prompts: dict[str, dict[str, str]],
    tmp_path: Path,
    with_lines: bool,
) -> None:
    """★掃引の本実行(S): 前置きがあれば文面と記録に乗り、無ければ null。"""
    run_dir, sent = execute_sweep(s_config(pool_dirs["s"], with_lines=with_lines), tmp_path)
    lines = ADR_079_LINES if with_lines else None
    expected = {
        item_id: preamble.with_preamble(prompt, lines, item_id)
        for item_id, prompt in plain_prompts["s"].items()
    }
    assert sorted(sent) == sorted(expected.values())
    rows = predictions_by_item(run_dir)
    assert {item_id: row["prompt"] for item_id, row in rows.items()} == expected
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "preamble" in metrics
    assert metrics["preamble"] == preamble.preamble_record(lines)
    assert preamble.preamble_line(metrics["preamble"]) in (run_dir / "log.txt").read_text(
        encoding="utf-8"
    )


def test_dry_runs_report_the_preamble(pool_dirs: dict[str, Path]) -> None:
    fixed = run.dry_run(pilot_config(pool_dirs["pilot"], ADR_079_LINES))
    assert fixed["preamble"] == preamble.preamble_record(ADR_079_LINES)
    assert len(fixed["prompts"]) == 1640
    for prompt in fixed["prompts"]:
        assert sorted(prompt.split("\n\n", 1)[0].split("\n")) == sorted(ADR_079_LINES)
    swept = run.threshold_sweep_dry_run(s_config(pool_dirs["s"], with_lines=True))
    assert swept["preamble"] == preamble.preamble_record(ADR_079_LINES)
    assert run.dry_run(pilot_config(pool_dirs["pilot"]))["preamble"] is None


def test_a_broken_declaration_stops_before_the_run_dir(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """壊れた宣言は、両方の経路とも重みを読む前・run ディレクトリを作る前に止まる。"""
    fixed = pilot_config(pool_dirs["pilot"], DUPLICATED_LINES)
    with pytest.raises(ConfigError, match="eval.preamble"):
        execute_fixed(fixed, tmp_path)
    with pytest.raises(ConfigError, match="eval.preamble"):
        run.dry_run(fixed)
    swept = s_config(pool_dirs["s"], with_lines=True)
    swept["eval"]["preamble"] = DUPLICATED_LINES
    with pytest.raises(ConfigError, match="eval.preamble"):
        execute_sweep(swept, tmp_path)
    assert not (tmp_path / "run").exists()


def test_the_magnitude_sweep_refuses_a_preamble(pool_dirs: dict[str, Path], tmp_path: Path) -> None:
    """桁数掃引は前置きを実装していないので、宣言した config を拒む(PLAN-026 §4.7 読み7)。"""
    config = pilot_config(pool_dirs["pilot"], ADR_079_LINES)
    with pytest.raises(ConfigError, match="eval.preamble"):
        sweep.dry_run_summary(config)
    generator, generated = recording_generator()
    with pytest.raises(ConfigError, match="eval.preamble"):
        sweep.execute(
            config,
            config_path=write_config(config, tmp_path / "config.yaml"),
            run_dir=tmp_path / "run",
            generator=generator,
        )
    assert not generated
    assert not (tmp_path / "run").exists()


# --------------------------------------------------------------------------
# preflight の検査6(PLAN-026 I7・§4.7 読み6)
# --------------------------------------------------------------------------


def results_by_name(config: Mapping[str, Any]) -> dict[str, preflight.CheckResult]:
    return {result.name: result for result in preflight.data_checks(config)}


def test_data_checks_skip_the_anchor_comparison_on_the_s_preamble_config() -> None:
    """★S-① の config: 検査6 は SKIP(前置きのある T1 はアンカーでない)、残り 6 件は PASS。"""
    results = results_by_name(preflight.load_config(S_PREAMBLE_CONFIG))
    assert set(results) == set(preflight.DATA_CHECK_NAMES)
    format_hash = results.pop("format hash")
    assert format_hash.status is preflight.Status.SKIP
    assert "評価アンカーでない" in format_hash.detail
    assert preamble.preamble_sha256(ADR_079_LINES)[:12] in format_hash.detail
    assert {r.status for r in results.values()} == {preflight.Status.PASS}, [
        (r.name, r.detail) for r in results.values()
    ]


def test_a_preamble_run_is_not_compared_with_the_anchor(tmp_path: Path) -> None:
    """★アンカーの書式が訓練と違っても、前置きのある run は比べない。前置きの無い run は今までどおり FAIL。"""
    config = preflight.load_config(S_PREAMBLE_CONFIG)
    manifests = preflight.load_ft_manifests(config)
    anchor = json.loads(Path(REPO_ROOT / config["eval"]["anchor_manifest"]).read_text("utf-8"))
    anchor["prompt_format"]["format_hash"] = "a" * 64
    moved = tmp_path / "manifest.json"
    moved.write_text(json.dumps(anchor, ensure_ascii=False), encoding="utf-8")
    config["eval"]["anchor_manifest"] = str(moved)
    assert preflight.format_hash_result(config, manifests).status is preflight.Status.SKIP
    without = with_preamble_config(config, None)
    result = preflight.format_hash_result(without, manifests)
    assert result.status is preflight.Status.FAIL
    assert "アンカー" in result.detail


def test_a_preamble_run_still_checks_the_training_side() -> None:
    """★前置きのある run でも、訓練側の書式が破れていれば FAIL(SKIP で隠さない)。"""
    config = preflight.load_config(S_PREAMBLE_CONFIG)
    manifests = copy.deepcopy(preflight.load_ft_manifests(config))
    condition = sorted(manifests)[0]
    manifests[condition]["prompt_format"]["format_hash"] = "b" * 64
    result = preflight.format_hash_result(config, manifests)
    assert result.status is preflight.Status.FAIL
    assert "記録が古い" in result.detail


def test_a_broken_declaration_is_a_fail_in_preflight() -> None:
    """壊れた宣言で preflight ごと落ちない。検査6 が FAIL として理由を残す。"""
    config = with_preamble_config(preflight.load_config(S_PREAMBLE_CONFIG), DUPLICATED_LINES)
    format_hash = results_by_name(config)["format hash"]
    assert format_hash.status is preflight.Status.FAIL
    assert "eval.preamble" in format_hash.detail


def test_runs_without_a_preamble_keep_the_anchor_comparison() -> None:
    """前置きの無い run(pilot = B0・R8)の検査6 は今までどおりアンカーと比べて PASS。"""
    for path in (PILOT_CONFIG, R8_CONFIG):
        format_hash = results_by_name(preflight.load_config(path))["format hash"]
        assert format_hash.status is preflight.Status.PASS, (path.name, format_hash.detail)
        assert "アンカーで一致" in format_hash.detail
