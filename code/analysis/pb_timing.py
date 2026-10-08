"""パラメトリック・ブートストラップ(PB)の費用の計時(PLAN-043 I9 / ADR-128 決定2 (B2) / ADR-129 決定6)。

答える問い: 「主要検定の LRT を PB に寄せるとき、1 回の simulate -> refit は何秒かかり、当て直しは何回失敗するか」
—— **費用の桁を測るだけ**で、p 値も LRT の統計量も出さない・判定に使わない(ADR-129 決定6)。
PB の反復数・PB の中の失敗の扱い・漸近 χ² と食い違ったときの扱いは S5 で決める。

    python -m code.analysis.pb_timing --config configs/pb_timing.yaml --dry-run
    python -m code.analysis.pb_timing --config configs/pb_timing.yaml        # ★人間の合図の後(日時は人間が決める)

表は合成の反復(番号 >= `pb.min_rep`。run2・run3 の反復 0〜999 と重ならない)で、run3 の反復を覗かない。
当てはめの閾値・縮退順序・DGP・シートは `source_config`(本番の config)から読む。
**表を組む → R に投げる → 秒数を集める、の 3 段しかない**(当て直しは `pb_timing.R`。skill `code-style` §2)。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code import artifacts
from code.analysis import power_sim as ps
from code.analysis.fit_failure_diagnosis import rebuild_frame_rows
from code.config import ConfigError, load_config, require

PB_SCRIPT = Path(__file__).resolve().parent / "pb_timing.R"
SUMMARY_FILE = "pb_timing.json"
NOTE = (
    "Seconds and refit-failure counts only. No p value and no LRT statistic is written or used "
    "(ADR-129 decision 6). The number of bootstrap draws, the handling of failures inside the bootstrap and "
    "of disagreement with the asymptotic chi-square are decided in S5, not here."
)


class PbTimingError(RuntimeError):
    """計時を続けられない(R が落ちた・出力が欠けた等)。"""


@dataclass(frozen=True)
class PbTable:
    """計時する表 1 枚。答える問い: どのシートの、どの点の、何番目の反復の表か。"""

    sheet_id: str
    key: ps.PointKey
    rep: int


@dataclass(frozen=True)
class PbSpec:
    """計時の宣言。答える問い: 何を何回、どれだけ並列で測るか。"""

    source_config: Path
    tables: tuple[PbTable, ...]
    n_boot: int
    min_rep: int
    simulate_seed: int
    n_parallel: int
    out_dir: Path


def load_spec(config: Mapping[str, Any], repo_root: Path) -> PbSpec:
    """config から計時の宣言を組む。答える問い: 値はすべて宣言されているか。

    **既定値を作らない**(skill `code-style` §5)。null・欠け・不正な値(`min_rep` 未満の反復・空の表)は止まる。
    """
    n_boot = require(config, "pb.n_boot")
    min_rep = require(config, "pb.min_rep")
    n_parallel = require(config, "pb.n_parallel")
    seed = require(config, "pb.simulate_seed")
    for name, value in (("n_boot", n_boot), ("min_rep", min_rep), ("n_parallel", n_parallel),
                        ("simulate_seed", seed)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ConfigError(f"pb.{name} は 1 以上の整数: {value!r}")
    declared = require(config, "tables")
    if not isinstance(declared, list) or not declared:
        raise ConfigError("tables は空でないリスト")
    tables = []
    for row in declared:
        point = row.get("point") if isinstance(row, Mapping) else None
        if (
            not isinstance(row, Mapping)
            or not isinstance(row.get("sheet"), str)
            or not isinstance(row.get("rep"), int)
            or not isinstance(point, list)
            or len(point) != 3
        ):
            raise ConfigError(f"tables の行は {{sheet, point: [n_item, sigma, rho], rep}}: {row!r}")
        if row["rep"] < min_rep:
            raise ConfigError(
                f"表の反復 {row['rep']} は pb.min_rep = {min_rep} 未満である"
                "(run2・run3 の反復を覗かない。PLAN-043 §4 Q5)"
            )
        tables.append(PbTable(
            row["sheet"], ps.PointKey(int(point[0]), float(point[1]), float(point[2])), row["rep"]
        ))
    if len({(t.sheet_id, t.key, t.rep) for t in tables}) != len(tables):
        raise ConfigError("tables に同じ表が 2 回ある")
    source = repo_root / str(require(config, "source_config"))
    return PbSpec(
        source_config=source,
        tables=tuple(tables),
        n_boot=n_boot,
        min_rep=min_rep,
        simulate_seed=seed,
        n_parallel=n_parallel,
        out_dir=repo_root / str(require(config, "out_dir")),
    )


def check_tables_against_sheets(spec: PbSpec, sheets: Sequence[ps.Sheet]) -> None:
    """答える問い: 計時する表は、本番の config が回すシートの点か(回さない点を測らない)。"""
    by_id = {sheet.sheet_id: sheet for sheet in sheets}
    for table in spec.tables:
        if table.sheet_id not in by_id:
            raise ConfigError(f"計時の表のシート {table.sheet_id} が source_config に無い")
        if table.key not in by_id[table.sheet_id].points:
            raise ConfigError(
                f"計時の表の点 {table.key} をシート {table.sheet_id} が回さない(source_config)"
            )


def table_stem(table: PbTable) -> str:
    """答える問い: この表のファイル名の札は(シート・点・反復で一意)。"""
    return f"{table.sheet_id}__{table.key.tag()}__{table.rep:04d}"


def write_pb_manifest(
    path: Path,
    jobs: Sequence[tuple[Path, Path]],
    refit: Mapping[str, Any],
    max_reduction_level: int,
    spec: PbSpec,
) -> None:
    """R に渡す平文 manifest を書く。答える問い: R は何をどの閾値で何回測るか。"""
    lines = [
        f"loglik_tolerance={refit['loglik_tolerance']}",
        f"beta_move_tolerance={refit['beta_move_tolerance']}",
        f"max_reduction_level={max_reduction_level}",
        f"n_boot={spec.n_boot}",
        f"simulate_seed={spec.simulate_seed}",
    ]
    lines += [f"table={csv.as_posix()}|{out.as_posix()}|{spec.n_parallel}" for csv, out in jobs]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def run_pb_rscript(rscript: str, libpath: str | None, manifest: Path) -> str:
    """R を 1 回起動して manifest の表を測る。答える問い: 計時は通ったか。"""
    completed = subprocess.run(
        [rscript, str(PB_SCRIPT), libpath or "", str(manifest)], capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise PbTimingError(
            f"Rscript が異常終了した (returncode={completed.returncode})\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    return completed.stdout


def summarise(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """答える問い: 表ごとの秒数と失敗の数から、1 回の当て直し(add と full の 1 組)は何秒か。

    **秒数と失敗の数だけを集める**(p 値・統計量は R が出さない)。skipped の表は件数だけ数える。
    """
    measured = [r for r in results if not r["skipped"]]
    per_draw = [s for r in measured for s in r["refit_seconds_each"]]
    out: dict[str, Any] = {
        "n_tables": len(results),
        "n_tables_skipped": len(results) - len(measured),
        "n_draws": len(per_draw),
        "n_refits": 2 * len(per_draw),
        "refit_errors": sum(r["refit_error_add"] + r["refit_error_full"] for r in measured),
        "refit_nonsingular_warnings": sum(
            r["refit_nonsingular_warning_add"] + r["refit_nonsingular_warning_full"] for r in measured
        ),
        "observed_fit_seconds_total": sum(r["observed_fit_seconds"] for r in results),
    }
    if per_draw:
        ordered = sorted(per_draw)
        out |= {
            "seconds_per_draw_mean": sum(per_draw) / len(per_draw),
            "seconds_per_draw_median": ordered[len(ordered) // 2],
            "seconds_per_draw_max": ordered[-1],
            "refit_seconds_total": sum(r["refit_seconds_total"] for r in measured),
        }
    return out


def run(spec: PbSpec, config: Mapping[str, Any], source: Mapping[str, Any],
        rscript_override: str | None) -> dict[str, Any]:
    """表を組んで測り、`pb_timing.json` を書く。答える問い: PB の 1 回あたりの費用の桁は。"""
    sheets = {sheet.sheet_id: sheet for sheet in ps.load_sheets(source)}
    out_dir = spec.out_dir
    frames_dir, r_out_dir = out_dir / "frames", out_dir / "r_out"
    for directory in (frames_dir, r_out_dir):
        directory.mkdir(parents=True, exist_ok=True)
    rscript = ps.resolve_rscript(rscript_override or source["fit"].get("rscript"))
    jobs: list[tuple[Path, Path]] = []
    for table in spec.tables:
        csv_path = frames_dir / f"{table_stem(table)}.csv"
        rows = rebuild_frame_rows(source, sheets[table.sheet_id], table.key, table.rep)
        ps.write_frame_csv(rows, csv_path)
        jobs.append((csv_path, r_out_dir / f"{table_stem(table)}.json"))
    max_level = len(require(source, "fit.reduction_order"))
    shards = ps.shard_jobs(jobs, spec.n_parallel)
    manifests = []
    for index, shard in enumerate(shards):
        manifest = out_dir / f"manifest_{index:02d}.txt"
        write_pb_manifest(manifest, shard, source["fit"]["refit"], max_level, spec)
        manifests.append(manifest)
    libpath = source["fit"].get("r_libpath")
    with ThreadPoolExecutor(max_workers=len(manifests)) as pool:
        for future in [pool.submit(run_pb_rscript, rscript, libpath, m) for m in manifests]:
            future.result()
    results = []
    for table, (_, out_path) in zip(spec.tables, jobs):
        if not out_path.exists():
            raise PbTimingError(f"R の出力が無い: {out_path}")
        results.append({
            "sheet": table.sheet_id, "point": [table.key.n_item, table.key.sigma, table.key.rho],
            "rep": table.rep, **json.loads(out_path.read_text(encoding="ascii")),
        })
    report = {
        "note": NOTE,
        "git_sha": artifacts.capture_git_head_sha(),
        "tracked_diff_empty": artifacts.capture_git_diff_head() == "",
        "n_boot": spec.n_boot,
        "n_parallel": spec.n_parallel,
        "simulate_seed": spec.simulate_seed,
        "summary": summarise(results),
        "tables": results,
    }
    ps.write_json_atomic(out_dir / SUMMARY_FILE, report)
    for csv_path, _ in jobs:
        csv_path.unlink(missing_ok=True)
    return report


def describe_plan(spec: PbSpec) -> list[str]:
    """回す前に「何本の当て直しか」を出す。答える問い: 何を測るのか(R を呼ばない)。"""
    n_refits = len(spec.tables) * spec.n_boot * 2
    lines = [
        f"tables    : {len(spec.tables)} (synthetic reps >= {spec.min_rep}; not run2 / run3 reps)",
    ]
    lines += [
        f"  {t.sheet_id:<16} point (n_item, sigma, rho) = ({t.key.n_item}, {t.key.sigma:g}, {t.key.rho:g}) rep {t.rep}"
        for t in spec.tables
    ]
    lines += [
        f"n_boot    : {spec.n_boot} per table -> {n_refits} refits (add + full) in total",
        f"parallel  : {spec.n_parallel} Rscript(s); seconds are measured under this load",
        f"simulate_seed: {spec.simulate_seed}",
        f"out_dir   : {spec.out_dir.as_posix()}",
        "NOTE: seconds and refit-failure counts only; no p value is produced (ADR-129 decision 6)",
    ]
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--rscript", help="source_config の fit.rscript を上書きする")
    parser.add_argument("--dry-run", action="store_true", help="表と当て直しの本数だけ出す。R を呼ばない")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    config = load_config(args.config)
    spec = load_spec(config, repo_root)
    source = load_config(spec.source_config)
    check_tables_against_sheets(spec, ps.load_sheets(source))
    if args.dry_run:
        for line in describe_plan(spec):
            print(line)
        return 0
    report = run(spec, config, source, args.rscript)
    print(json.dumps(report["summary"], indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
