"""★E の確かめ: 訓練せずに「種付け → LoRA を挿す → 初期値の指紋」を回す(PLAN-031 §3.6)。

答える問い: 「本物の peft で、同じ `seed` なら LoRA の初期値は 1 ビットも違わず、違う `seed` なら
違うか。アダプタは宣言した dtype(fp32)で挿さるか」

  python -m code.train.seed_check --config <cfg> --seeds 0 0 1 --dry-run
  python -m code.train.seed_check --config <cfg> --seeds 0 0 1 --run-dir runs/<id>

**なぜ要るか**: ローカルには peft が無く、`code/tests/test_train_seeding.py` は LoRA の A を torch の
グローバル乱数から引く**偽の peft**で配線だけを縛っている。**本物の peft の初期化が `seed_all` の
乱数源だけで決まるか**、**アダプタが fp32 に上がるか**(ADR-099 の f′)は「ソースの読み」であって
実行で確かめていない。ここでしか分からない。

**訓練しない。**土台を読み、`code.train.lora.insert_seeded_adapter`(**訓練と同じ関数**)で種付けして
LoRA を挿し、指紋と dtype を控え、捨てる。**`optimizer` も訓練データも作らない。**

**シードごとに重みを読み直す。**peft は土台のモジュールを書き換える前提で扱う。同じ土台に 2 度
挿すと、2 度目は「前回の LoRA が残った土台」への挿入になり、「同じ種で同じ初期値」を確かめたことに
ならない(前回の LoRA が残るのか上書きされるのかは peft の版に依る)。読み直しの費用(分単位)より
確かさを取る。**直前の土台とアダプタは GPU から外してから読む**(24 GB の GPU に 8B の bf16 の
土台(約 16 GB。算定)は 2 つ載らない)。

**1 プロセスで回す。**訓練の 3 条件は別プロセスで同じ種を使う(ADR-099 決定2 = α)ので、プロセスを
またぐ一致は、この CLI を 2 回走らせて `seed_check.json` の指紋を比べれば見える(自動では比べない)。

**確かめ自身が黙って通らないようにしてある**: 同じ種の対と違う種の対の両方が無い並び
(`--seeds 0 1` / `--seeds 0 0`)は、どちらかが確かめられないので受け付けない。

**`--dry-run` は重みを読まない。**`--run-dir` は本実行に必須である(結果を残さずに GPU を使わせない。
`code/train/lora.py` の `adapter_dir` と同じ理由)。指紋は初期値の記録であって実験結果ではない。
"""

from __future__ import annotations

import argparse
import functools
import gc
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from code.artifacts import (
    utc_now,
    write_config_copy,
    write_env,
    write_git_sha,
    write_log,
    write_timestamps,
)
from code.config import load_config, require
from code.train import lora, seeding
from code.train.run import declared_model, model_reference
from code.train.settings import TrainSettings, load_train_settings
from code.weights import load_causal_lm

# 結果の種別と置き場所。**`metrics.json` という名前にしない** —— `aggregate.py` などが
# `runs/*/metrics.json` を run として読む。これは run ではなく点検の記録である。
SEED_CHECK_KIND = "seed_check"
RESULT_FILE = "seed_check.json"

# 版を記録するライブラリ。f′(peft が LoRA の重みを fp32 に上げる)は peft の版に依る読みなので、
# 観測値を版と一緒に残す。
CHECKED_LIBRARIES: tuple[str, ...] = ("torch", "transformers", "peft")

# 確かめが成り立つのに要る、相異なる種の数(同じ種の対と違う種の対の両方を作るため)。
MIN_DISTINCT_SEEDS = 2

# `seeding.seeding_plan` の欄のうち、シードごとに違う(または説明文で長い)もの。dry-run は畳む。
SEED_VALUE_KEYS: tuple[str, ...] = ("value", "derivation_note")

NOT_AN_EXPERIMENT = (
    "訓練していない。ここに出る指紋は LoRA の初期値の記録であって実験結果ではない。"
    "効果量・主張・Δ 5 行には使わない(PLAN-031 §3.6)。"
)

# 土台を読み直す関数(引数なし)。テストは偽物を渡す(`code/train/lora.py` の `Trainer` と同じ作り)。
LoadBase = Callable[[], Any]


class SeedCheckError(RuntimeError):
    """確かめを始められない、または確かめの入力が確かめになっていない。"""


@dataclass(frozen=True)
class SeedProbe:
    """1 回分の観測(土台を読み直して LoRA を挿した直後)。

    答える問い: 「この実行順・この `seed` で、LoRA の初期値の指紋と dtype は何だったか」
    """

    position: int  # 0 始まりの実行順
    seed: int
    adapter_init_sha256: str
    adapter_param_dtypes: tuple[str, ...]
    seeding: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "seed": self.seed,
            "adapter_init_sha256": self.adapter_init_sha256,
            "adapter_param_dtypes": list(self.adapter_param_dtypes),
            "seeding": self.seeding,
        }


@dataclass(frozen=True)
class Comparison:
    """2 回の観測の指紋の比べ。**同じ種の対は一致が、違う種の対は不一致が期待である。**"""

    earlier: int
    later: int
    earlier_seed: int
    later_seed: int
    equal: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "earlier": self.earlier,
            "later": self.later,
            "earlier_seed": self.earlier_seed,
            "later_seed": self.later_seed,
            "equal": self.equal,
        }


@dataclass(frozen=True)
class Verdict:
    """確かめの判定。**`problems` が空のときだけ通った。**

    答える問い: 「同じ種で一致し、違う種で違い、dtype が宣言どおりか」
    """

    same_seed: tuple[Comparison, ...]
    different_seed: tuple[Comparison, ...]
    problems: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.problems

    def as_dict(self) -> dict[str, Any]:
        return {
            "same_seed": [pair.as_dict() for pair in self.same_seed],
            "different_seed": [pair.as_dict() for pair in self.different_seed],
            "problems": list(self.problems),
            "passed": self.passed,
        }


def validate_seeds(seeds: Sequence[int]) -> None:
    """並びが「同じ種の対」と「違う種の対」の両方を作ることを確かめる。

    答える問い: 「この並びは、通っても失敗してもよい確かめになっているか」

    片方の対が無いと、その性質は確かめられない。それでも「通った」と出すと、
    確かめていないことを確かめたと読ませる(CLAUDE.md §7)。
    """
    distinct = set(seeds)
    if len(distinct) < MIN_DISTINCT_SEEDS:
        raise SeedCheckError(
            f"--seeds {list(seeds)} に相異なる種が {MIN_DISTINCT_SEEDS} 個無い。"
            "「違う種なら違う」が確かめられない(例: 0 0 1)。"
        )
    if len(distinct) == len(seeds):
        raise SeedCheckError(
            f"--seeds {list(seeds)} に同じ種が 2 回以上出てこない。"
            "「同じ種なら同じ」が確かめられない(例: 0 0 1)。"
        )


def library_versions() -> dict[str, str]:
    """確かめに使うライブラリの版。入っていなければここで止まる。

    答える問い: 「この観測は、どの版の torch・transformers・peft で取ったか」

    **重みを読む前に呼ぶ。**peft が無いと分かるのが分単位の読み込みの後になるのを避ける。
    """
    versions: dict[str, str] = {}
    for name in CHECKED_LIBRARIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError as exc:
            raise SeedCheckError(
                f"{name} が入っていない。★E の確かめは GPU 用の依存"
                "(pyproject.toml の optional-dependency `gpu`)が要る。"
            ) from exc
    return versions


def release_accelerator_memory() -> None:
    """前の土台とアダプタを GPU から外す。

    答える問い: 「次の土台を読む前に、前のものは GPU から外れたか」

    peft のモデルと土台は互いを参照する(循環参照)ので、関数を抜けただけでは解放されない。
    """
    import torch  # noqa: PLC0415 — optional-dependency `gpu`

    gc.collect()
    torch.cuda.empty_cache()  # CUDA が無ければ何もしない(torch の仕様)


def probe_seed(settings: TrainSettings, *, position: int, load_base: LoadBase) -> SeedProbe:
    """重みを読み直して LoRA を挿し、指紋と dtype を控える。

    答える問い: 「この `seed` で、訓練と同じ経路を通すと LoRA の初期値の指紋は何か」

    **土台もアダプタも返さない。**呼び出し側に GPU メモリを持たせない。
    """
    inserted = lora.insert_seeded_adapter(load_base(), settings)
    return SeedProbe(
        position=position,
        seed=settings.seed,
        adapter_init_sha256=inserted.init_sha256,
        adapter_param_dtypes=tuple(inserted.param_dtypes),
        seeding=inserted.seeding,
    )


def run_probes(
    all_settings: Sequence[TrainSettings], *, load_base: LoadBase
) -> list[SeedProbe]:
    """並びの順に、シードごとに重みを読み直して観測する。

    答える問い: 「並んだ `seed` の順に、本物の経路で LoRA を挿すと何が観測されるか」
    """
    probes: list[SeedProbe] = []
    for position, settings in enumerate(all_settings):
        probes.append(probe_seed(settings, position=position, load_base=load_base))
        release_accelerator_memory()
    return probes


def judge(probes: Sequence[SeedProbe], *, declared_dtype: str) -> Verdict:
    """観測から、★E の 3 つの問いに答える。

    答える問い: 「同じ種で一致し、違う種で違い、dtype が宣言どおりか」

    各回を、**種ごとに最初に出た回**と比べる(同じ種が 3 回なら 1-2 と 1-3。違う種は、各回と
    ほかの種の最初の回)。dtype の判定は訓練が使う `check_adapter_dtype` と同じ関数で、
    食い違いを 1 つずつ問題に数える(訓練は最初の 1 つで止まるが、確かめは全部見る)。
    """
    first_position: dict[int, int] = {}
    same: list[Comparison] = []
    different: list[Comparison] = []
    for probe in probes:
        for seed, position in first_position.items():
            other = probes[position]
            pair = Comparison(
                earlier=other.position,
                later=probe.position,
                earlier_seed=seed,
                later_seed=probe.seed,
                equal=other.adapter_init_sha256 == probe.adapter_init_sha256,
            )
            if seed == probe.seed:
                same.append(pair)
            else:
                different.append(pair)
        first_position.setdefault(probe.seed, probe.position)
    return Verdict(
        same_seed=tuple(same),
        different_seed=tuple(different),
        problems=tuple(_problems(probes, same, different, declared_dtype)),
    )


def _problems(
    probes: Sequence[SeedProbe],
    same: Sequence[Comparison],
    different: Sequence[Comparison],
    declared_dtype: str,
) -> list[str]:
    """判定の問題の一覧(`judge` の内側。空なら通った)。"""
    problems: list[str] = []
    if not same:
        problems.append("同じ種の対が無い。「同じ種なら同じ」を確かめていない。")
    if not different:
        problems.append("違う種の対が無い。「違う種なら違う」を確かめていない。")
    for pair in same:
        if not pair.equal:
            problems.append(
                f"同じ種 {pair.earlier_seed} なのに指紋が違う(実行 {pair.earlier + 1} と "
                f"{pair.later + 1})。★E は直っていない。考えられる原因: peft の初期化が "
                "`seed_all` の乱数源だけでは決まっていない / 土台の読み直しで状態が残った。"
            )
    for pair in different:
        if pair.equal:
            problems.append(
                f"違う種 {pair.earlier_seed} と {pair.later_seed} なのに指紋が同じ(実行 "
                f"{pair.earlier + 1} と {pair.later + 1})。初期値が種に反応していない。"
            )
    for probe in probes:
        try:
            lora.check_adapter_dtype(declared_dtype, probe.adapter_param_dtypes)
        except lora.TrainerContractError as exc:
            problems.append(f"実行 {probe.position + 1}: {exc}")
    return problems


def result_payload(
    config: Mapping[str, Any],
    all_settings: Sequence[TrainSettings],
    probes: Sequence[SeedProbe],
    verdict: Verdict,
    *,
    libraries: Mapping[str, str],
) -> dict[str, Any]:
    """`seed_check.json` の中身。

    答える問い: 「この確かめが、どの重みに、どの版で、何を観測したかを、この 1 ファイルだけで
    言えるか」
    """
    first = all_settings[0]
    return {
        "kind": SEED_CHECK_KIND,
        "created_utc": utc_now().isoformat(),
        "experiment_id": require(config, "experiment.id"),
        "note": NOT_AN_EXPERIMENT,
        "model": model_reference(config),
        "libraries": dict(libraries),
        "declared": {"adapter_dtype": first.adapter_dtype, "lora": first.lora.as_dict()},
        "seeds": [settings.seed for settings in all_settings],
        "probes": [probe.as_dict() for probe in probes],
        "verdict": verdict.as_dict(),
    }


def report_lines(payload: Mapping[str, Any]) -> list[str]:
    """log.txt と標準出力に出す行。

    答える問い: 「この確かめは通ったのか。通らなかったなら何が食い違ったのか」
    """
    model = payload["model"]
    declared = payload["declared"]
    verdict = payload["verdict"]
    lines = [
        f"★E の確かめ(seed_check)。{NOT_AN_EXPERIMENT}",
        f"model: {model['name']} @ {model['revision']} ({model['dtype']}, {model['device']})",
        "libraries: " + " ".join(f"{name}={ver}" for name, ver in payload["libraries"].items()),
        f"宣言: adapter_dtype={declared['adapter_dtype']} lora={declared['lora']}",
    ]
    total = len(payload["probes"])
    for probe in payload["probes"]:
        lines.append(
            f"実行 {probe['position'] + 1}/{total} seed={probe['seed']}: "
            f"sha256={probe['adapter_init_sha256']} dtype={probe['adapter_param_dtypes']}"
        )
    for pair in verdict["same_seed"]:
        lines.append(
            f"同じ種 {pair['earlier_seed']}: 実行 {pair['earlier'] + 1} と {pair['later'] + 1} は "
            + ("一致" if pair["equal"] else "**違う**")
        )
    for pair in verdict["different_seed"]:
        lines.append(
            f"違う種 {pair['earlier_seed']} と {pair['later_seed']}: 実行 {pair['earlier'] + 1} と "
            f"{pair['later'] + 1} は " + ("**同じ**" if pair["equal"] else "違う")
        )
    if verdict["passed"]:
        lines.append("判定: 通った(同じ種で一致・違う種で不一致・dtype は宣言どおり)")
    else:
        lines.append("判定: **通らなかった**")
        lines.extend(f"  - {problem}" for problem in verdict["problems"])
    return lines


def dry_run(config: Mapping[str, Any], *, seeds: Sequence[int]) -> dict[str, Any]:
    """重みを読まずに、何をどの順でやるかと、門を通ることを確かめる。

    答える問い: 「この config とこの並びで、確かめを始められる状態か」

    通るのは (1) 並びが確かめとして成り立つこと (2) 各 `seed` が `train.*` の門と config の
    `seeds` を通ること までである。**モデルは 1 度も読まれない。**
    """
    validate_seeds(seeds)
    all_settings = [load_train_settings(config, seed=seed) for seed in seeds]
    # 種付けの宣言は種の値以外がシードによらない(ADR-099 決定2 = α)。値だけを並べて 1 回に畳む。
    declaration = {
        key: value
        for key, value in seeding.seeding_plan(seeds[0]).items()
        if key not in SEED_VALUE_KEYS
    }
    return {
        "seeds": list(seeds),
        "model": declared_model(config),
        "declared": {
            "adapter_dtype": all_settings[0].adapter_dtype,
            "lora": all_settings[0].lora.as_dict(),
        },
        "plan": {
            "n_weight_loads": len(seeds),
            "note": "シードごとに重みを読み直す。訓練はしない。",
            "seeding_plan": {**declaration, "values": list(seeds)},
        },
    }


def execute(
    config: Mapping[str, Any],
    *,
    config_path: Path,
    run_dir: Path,
    seeds: Sequence[int],
    load_base: LoadBase | None = None,
) -> int:
    """本実行。結果を `run_dir` に書き、通ったら 0・通らなかったら 1 を返す。

    答える問い: 「本物の peft で ★E は直っているか。その観測を後から言えるか」

    **門は run ディレクトリを作る前に通す**(`code/train/run.py` の `execute` と同じ)。
    **来歴(config・git・環境)は重みを読む前に書く** —— 読み込みの途中で落ちても、どの版で
    何を試したかが残る。**通らなかった確かめも記録する**(食い違いは記録に値する)。
    """
    validate_seeds(seeds)
    all_settings = [load_train_settings(config, seed=seed) for seed in seeds]
    model = model_reference(config)
    libraries = library_versions()
    result_path = run_dir / RESULT_FILE
    if result_path.exists():
        raise SeedCheckError(f"{result_path} が既にある。記録を上書きしない(別の --run-dir を使う)")

    started = utc_now()
    run_dir.mkdir(parents=True, exist_ok=True)
    write_config_copy(run_dir, config_path)
    write_git_sha(run_dir)
    write_env(run_dir)

    resolved = load_base or functools.partial(
        load_causal_lm,
        model_name=model["name"],
        revision=model["revision"],
        dtype=model["dtype"],
        device=model["device"],
    )
    probes = run_probes(all_settings, load_base=resolved)
    verdict = judge(probes, declared_dtype=all_settings[0].adapter_dtype)
    payload = result_payload(config, all_settings, probes, verdict, libraries=libraries)
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    result_path.write_text(body + "\n", encoding="utf-8")
    write_timestamps(run_dir, started=started, ended=utc_now())
    lines = report_lines(payload)
    write_log(run_dir, lines)
    for line in lines:
        print(line)
    return 0 if verdict.passed else 1


def print_dry_run(report: Mapping[str, Any]) -> None:
    """配線確認の報告を出す。**この警告文を本実行に流用しない。**"""
    print("=" * 72)
    print("--dry-run: 配線確認。**確かめではない。**重みは 1 度も読まれていない。")
    print("=" * 72)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="★E の確かめ(訓練しない)")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--seeds",
        required=True,
        type=int,
        nargs="+",
        help="この順に重みを読み直して LoRA を挿す。同じ種が 2 回以上・相異なる種が 2 個以上要る"
        "(例: 0 0 1)。config の seeds に宣言されているものだけ選べる",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="重みを読まずに配線だけ確かめる。確かめそのものではない",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="結果(seed_check.json・log.txt・来歴)の書き出し先。本実行に必須",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    try:
        if args.dry_run:
            if args.run_dir is not None:
                parser.error("--run-dir は本実行の引数である(--dry-run は何も書かない)")
            print_dry_run(dry_run(config, seeds=args.seeds))
            return 0
        if args.run_dir is None:
            parser.error("--run-dir が要る(結果を残さずに GPU を使わない)")
        return execute(
            config, config_path=args.config, run_dir=args.run_dir, seeds=args.seeds
        )
    except SeedCheckError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
