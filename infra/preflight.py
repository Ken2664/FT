"""本実行の前に環境を検証する。

答える問い: 「いま本実行を開始してよいか」

検査項目は infra/RUNPOD.md §3 の一覧に対応する。
**preflight が通らないまま本実行しない。**数時間走らせてから環境の不一致に
気づくのが最悪のパターン(infra/RUNPOD.md §3)。

使い方:
    python infra/preflight.py                       # 環境のみ検査
    python infra/preflight.py --config configs/exp042.yaml   # 実験固有の検査も行う

終了コード: FAIL が1つでもあれば 1、それ以外は 0。
WARN は 0 のまま返す(判断は人間に任せる項目)。

閾値(必要 VRAM、想定モデル、manifest ハッシュ)はここに直書きせず、
すべて config から読む(skill code-style §1)。config を渡さない場合、
それらの項目は SKIP になる。

**config を渡した実行は「本実行の準備」とみなす。**PLAN-002 §4.8.1 の検査
(条件間の一致・書式・トークン境界・被覆の下限・T_hold)は、対象を用意
できなければ SKIP ではなく **FAIL(未実行)** を返す。環境に無いことを
理由に検査を緩めない。したがって configs/smoke.yaml のような配線確認用の
config でこれを走らせると FAIL する。それが正しい(smoke は本実行ではない)。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


class Status(Enum):
    """検査結果の4値。FAIL のみが実行を止める。

    SKIP と PASS を混ぜないこと。SKIP は「この実行には対象が存在しない」であり、
    「確認できなかった」は FAIL である(PLAN-002 §4.8.1)。
    """

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class CheckResult:
    """1項目の検査結果。"""

    name: str
    status: Status
    detail: str


def _run(command: list[str], timeout_sec: int = 60) -> tuple[int, str]:
    """外部コマンドを実行し、終了コードと出力を返す。

    答える問い: 「このコマンドは何を返したか」— 例外ではなく値で返し、
    呼び出し側が Status に翻訳できるようにする。

    encoding を明示する理由: `text=True` はロケール既定のコーデックで
    デコードする。Windows では cp932 になり、git や pytest が吐く日本語
    (本 repo はコミットメッセージも assert メッセージも日本語)で
    UnicodeDecodeError が読み取りスレッド内で起き、**例外が握り潰されて
    stdout が None になる**。preflight が検査対象より先に落ちるので、
    UTF-8 を明示し、壊れたバイトは replace で通す。
    """
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            cwd=REPO_ROOT,
        )
    except FileNotFoundError:
        return 127, f"コマンドが見つからない: {command[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"タイムアウト ({timeout_sec}s): {' '.join(command)}"
    # デコードが失敗しても None を掴まないように保険をかける。
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return completed.returncode, (stdout + stderr).strip()


# --------------------------------------------------------------------------
# 各検査。1関数1項目(skill code-style §2)
# --------------------------------------------------------------------------


def check_stdlib_code_shim() -> CheckResult:
    """本 repo の `code` パッケージが標準ライブラリ `code` を壊していないか。

    これが壊れると pytest 自体が起動せず、「テストが通った」ことを確認できなくなる。
    詳細は code/__init__.py の冒頭と logs/DECISIONS.md ADR-013。
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        import code as shadowed  # noqa: PLC0415 — 影の解決を実地で確かめるのが目的

        missing = [
            name
            for name in ("InteractiveConsole", "InteractiveInterpreter", "compile_command")
            if not hasattr(shadowed, name)
        ]
        if missing:
            return CheckResult(
                "stdlib code shim",
                Status.FAIL,
                f"標準ライブラリ code の {missing} が失われている。pdb / pytest が起動しない",
            )
        import pdb  # noqa: F401, PLC0415 — import が通ること自体が検査

        return CheckResult("stdlib code shim", Status.PASS, "pdb の import に成功")
    except Exception as exc:  # noqa: BLE001 — どの例外でも FAIL にしたい
        return CheckResult("stdlib code shim", Status.FAIL, f"{type(exc).__name__}: {exc}")


def check_gpu(min_vram_gb: float | None) -> CheckResult:
    """GPU が見えるか、VRAM は足りるか。

    閾値 min_vram_gb は config の resources.min_vram_gb から来る。
    config が無いときは VRAM の判定を行わず、見えたかどうかだけ報告する。
    """
    if shutil.which("nvidia-smi") is None:
        return CheckResult("GPU", Status.WARN, "nvidia-smi が無い。CPU 環境とみなす")
    code, output = _run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]
    )
    if code != 0:
        return CheckResult("GPU", Status.FAIL, f"nvidia-smi が失敗: {output}")
    lines = [line for line in output.splitlines() if line.strip()]
    if not lines:
        return CheckResult("GPU", Status.FAIL, "GPU が1枚も見えない")
    if min_vram_gb is None:
        return CheckResult("GPU", Status.PASS, f"{len(lines)} 枚: {lines[0]} (VRAM 判定なし)")

    # "NVIDIA A100-SXM4-80GB, 81920 MiB, 550.54.15" の 2 番目を取る
    mib_per_gb = 1024.0
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        vram_gb = float(parts[1].split()[0]) / mib_per_gb
        if vram_gb < min_vram_gb:
            return CheckResult(
                "GPU",
                Status.FAIL,
                f"VRAM 不足: {vram_gb:.1f} GB < 必要 {min_vram_gb} GB ({parts[0]})",
            )
    return CheckResult("GPU", Status.PASS, f"{len(lines)} 枚、全て VRAM >= {min_vram_gb} GB")


def check_library_versions() -> CheckResult:
    """torch / transformers が入っているか、CUDA が使えるか。

    infra/RUNPOD.md §6 の pin との一致は requirements.lock との突き合わせで行う。
    lock がまだ無い環境(ローカルの設計セッション)では WARN に留める。
    """
    try:
        import torch  # noqa: PLC0415
    except ImportError:
        return CheckResult("libraries", Status.WARN, "torch 未インストール。GPU 実験はできない")
    detail = f"torch {torch.__version__}, cuda_available={torch.cuda.is_available()}"
    try:
        import transformers  # noqa: PLC0415

        detail += f", transformers {transformers.__version__}"
    except ImportError:
        return CheckResult("libraries", Status.WARN, detail + ", transformers 未インストール")

    lock = REPO_ROOT / "infra" / "requirements.lock"
    # コメントと空行を除いた実質的な pin だけを数える。
    # 説明コメントしか無い lock を「pin 済み」と誤報告しないため。
    pins = []
    if lock.exists():
        pins = [
            line
            for line in lock.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    if not pins:
        return CheckResult(
            "libraries", Status.WARN, detail + " / requirements.lock が空。pin と照合できない"
        )
    return CheckResult("libraries", Status.PASS, detail + f" / lock {len(pins)} 件")


def check_persistent_volume() -> CheckResult:
    """/workspace が永続ボリュームとしてマウントされているか。

    RunPod のポッド上でのみ意味のある検査。ローカルでは SKIP。
    """
    workspace = Path("/workspace")
    if not workspace.exists():
        return CheckResult("persistent volume", Status.SKIP, "/workspace が無い。ローカル環境とみなす")
    if not os.access(workspace, os.W_OK):
        return CheckResult("persistent volume", Status.FAIL, "/workspace に書き込めない")
    return CheckResult("persistent volume", Status.PASS, "/workspace は書き込み可能")


def check_writable_dirs() -> CheckResult:
    """runs/ と results/ に書き込めるか。実行の途中で気づくと成果物を失う。"""
    not_writable = [
        str(d)
        for d in (REPO_ROOT / "runs", REPO_ROOT / "results", REPO_ROOT / "data" / "generated")
        if not (d.exists() and os.access(d, os.W_OK))
    ]
    if not_writable:
        return CheckResult("writable dirs", Status.FAIL, f"書き込めない: {not_writable}")
    return CheckResult("writable dirs", Status.PASS, "runs / results / data/generated すべて可")


def check_tests() -> CheckResult:
    """pytest code/tests -q が通るか。CLAUDE.md §4 の必須ゲート。"""
    code, output = _run([sys.executable, "-m", "pytest", "code/tests", "-q"], timeout_sec=600)
    tail = output.splitlines()[-1] if output.splitlines() else "(出力なし)"
    if code != 0:
        return CheckResult("pytest", Status.FAIL, tail)
    return CheckResult("pytest", Status.PASS, tail)


def check_git_clean() -> CheckResult:
    """git status がクリーンか。dirty なら差分を runs/ の外に保存して警告する。

    dirty のまま実行すると、runs/<id>/git_sha.txt が実際に走ったコードを
    指さなくなる(infra/RUNPOD.md §4)。
    """
    code, output = _run(["git", "rev-parse", "--is-inside-work-tree"])
    if code != 0:
        return CheckResult("git", Status.FAIL, "git 管理下にない。run_id とコードを紐づけられない")
    code, status_output = _run(["git", "status", "--porcelain"])
    if code != 0:
        return CheckResult("git", Status.FAIL, f"git status が失敗: {status_output}")
    if not status_output.strip():
        _, sha = _run(["git", "rev-parse", "--short", "HEAD"])
        return CheckResult("git", Status.PASS, f"クリーン @ {sha}")

    diff_path = REPO_ROOT / "runs" / "preflight_dirty.diff"
    _, diff = _run(["git", "diff", "HEAD"])
    diff_path.write_text(diff, encoding="utf-8")
    changed = len(status_output.strip().splitlines())
    return CheckResult(
        "git", Status.WARN, f"未コミットの変更 {changed} 件。差分を {diff_path.name} に保存した"
    )


def _sha256_of_file(path: Path) -> str:
    """ファイルの SHA-256 を返す。manifest との突き合わせに使う。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_data_manifest(manifest_path: Path | None) -> CheckResult:
    """生成データのハッシュが manifest と一致するか。

    答える問い: 「いま評価しようとしているデータは、生成したときのものと同一か」

    FT データと評価データの重複検出も manifest のハッシュで行う
    (Documents/04_EXPERIMENT_PLAN.md「実装上の落とし穴」)。
    """
    if manifest_path is None:
        return CheckResult("data manifest", Status.SKIP, "config が無いので照合しない")
    if not manifest_path.exists():
        return CheckResult("data manifest", Status.FAIL, f"manifest が無い: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    if not files:
        return CheckResult("data manifest", Status.FAIL, "manifest に files が無い")
    mismatched = []
    for relative_path, expected_sha in files.items():
        target = manifest_path.parent / relative_path
        if not target.exists():
            mismatched.append(f"{relative_path}: 欠落")
        elif _sha256_of_file(target) != expected_sha:
            mismatched.append(f"{relative_path}: ハッシュ不一致")
    if mismatched:
        return CheckResult("data manifest", Status.FAIL, "; ".join(mismatched))
    return CheckResult("data manifest", Status.PASS, f"{len(files)} ファイル一致")


def check_model_weights(model_name: str | None) -> CheckResult:
    """モデル重みがローカルに存在するか。無ければダウンロード時間を警告する。"""
    if model_name is None:
        return CheckResult("model weights", Status.SKIP, "config が無いので確認しない")
    cache_root = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    hub = cache_root / "hub"
    expected = "models--" + model_name.replace("/", "--")
    if (hub / expected).exists():
        return CheckResult("model weights", Status.PASS, f"{model_name} はキャッシュ済み")
    return CheckResult(
        "model weights",
        Status.WARN,
        f"{model_name} が {hub} に無い。初回はダウンロード時間がかかる",
    )


# --------------------------------------------------------------------------
# PLAN-002 §4.8.1 の検査(FT データ manifest の照合)
#
# 方針: **環境に無いことを PASS にしない。**
#   SKIP は「この実行には対象が存在しない」(config 無し / condition=none)に限る。
#   宣言の欠落・依存の欠落・トークナイザを読めないは **FAIL(未実行)** で報告する。
#   既定値でトークン境界や書式を仮定すると、損失マスクと実験条件が静かにずれる。
# --------------------------------------------------------------------------

# FT データを生成しない条件(PLAN-002 §3.4)。この条件では manifest 系の検査を SKIP する。
LESION_CONDITION_NONE = "none"

# manifest に必ずある最上位キー(PLAN-002 §4.8)。欠けていたら schema 違いとして落とす。
REQUIRED_MANIFEST_KEYS: tuple[str, ...] = (
    "lesion",
    "train_domain",
    "train_answer_range",
    "pool_split",
    "t_holdout",
    "coverage",
    "sampling",
    "prompt_format",
    "outputs",
)

# §4.8.1 の manifest 系検査の名前。manifest が揃わないときは全部に同じ理由を載せる。
DATA_CHECK_NAMES: tuple[str, ...] = (
    "pool regions",
    "matched stream",
    "format hash",
    "coverage_k floor",
    "t_holdout",
    "holdout leak",
)

# §4.1.2 の6例 (a, b, target)。トークン境界の検査対象(§4.1.5 の1)。
# **病変条件の定義ではない。**ここで見るのは文字列のトークン化であり、
# completion の桁数 1/2/3 と被演算子の桁数 1/2 を覆うことだけが要件である。
PROMPT_FORMAT_EXAMPLES: tuple[tuple[int, int, int], ...] = (
    (3, 4, 9),
    (3, 4, 7),
    (3, 4, 14),
    (37, 45, 84),
    (99, 99, 200),
    (9, 9, 20),
)

# 検査結果の detail に載せる問題の最大件数。全部並べるとコンソールが読めなくなる。
MAX_REPORTED_PROBLEMS = 4


class ManifestUnavailable(Exception):
    """照合に使う manifest を揃えられなかった。

    答える問い: 「この検査は『通った』のか『実行できなかった』のか」

    status を持たせるのは、両者を1つの例外で運びつつ**混ぜないため**である。
    SKIP は対象の不在、FAIL は宣言または依存の欠落。
    """

    def __init__(self, status: Status, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _repo_modules() -> tuple[Any, Any]:
    """照合に使う生成器側のモジュール (ft_data, pool) を返す。

    答える問い: 「preflight が『再現して照合する』ときに使う関数はどれか」

    遅延 import にする理由: `code` は標準ライブラリと同名であり、shim が
    壊れていること自体が check_stdlib_code_shim の検査対象である(ADR-013)。
    module 直下で import すると、その検査を報告する前に preflight が落ちる。
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from code.data_gen import ft_data, pool  # noqa: PLC0415

    return ft_data, pool


def _resolve(entry: str) -> Path:
    """config に書かれたパスを repo ルート基準で解決する。"""
    path = Path(entry)
    return path if path.is_absolute() else REPO_ROOT / path


def _pairs_of(manifest: Mapping[str, Any]) -> set[tuple[int, int]]:
    """manifest の被覆 K を順序対の集合として取り出す。"""
    return {(int(a), int(b)) for a, b in manifest["coverage"]["pairs"]}


def _verdict(name: str, problems: Sequence[str], detail_when_ok: str) -> CheckResult:
    """問題の一覧を CheckResult に翻訳する。1件でもあれば FAIL。"""
    if not problems:
        return CheckResult(name, Status.PASS, detail_when_ok)
    shown = "; ".join(problems[:MAX_REPORTED_PROBLEMS])
    if len(problems) > MAX_REPORTED_PROBLEMS:
        shown += f" (他 {len(problems) - MAX_REPORTED_PROBLEMS} 件)"
    return CheckResult(name, Status.FAIL, shown)


def _no_manifests(name: str, manifests: Mapping[str, dict[str, Any]]) -> CheckResult | None:
    """照合対象が空なら FAIL を返す。空回りした検査を PASS と報告しないため。"""
    if manifests:
        return None
    return CheckResult(name, Status.FAIL, "照合対象の manifest が1つも無い(検査が空回りする)")


def _load_manifest_file(path: Path) -> dict[str, Any]:
    """manifest.json を読み、schema の最低限を確かめる。"""
    if not path.exists():
        raise ManifestUnavailable(Status.FAIL, f"manifest が無い: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestUnavailable(Status.FAIL, f"manifest が壊れている: {path} ({exc})") from exc
    missing = [key for key in REQUIRED_MANIFEST_KEYS if key not in manifest]
    if missing:
        raise ManifestUnavailable(
            Status.FAIL, f"{path.name} に {missing} が無い(PLAN-002 §4.8 の schema)"
        )
    return manifest


def load_ft_manifests(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """全病変条件の FT manifest を条件名で引ける形に読む(§4.8.1 検査5・6・9・10)。

    答える問い: 「条件間で照合すべき manifest が、全部そろっているか」

    data.matched_manifests が null のときに SKIP しないのは、
    **条件間の一致が実験設計の不変条件だから**である(§3.4)。
    照合できないまま本実行に入ることは、照合して落ちるより悪い。
    """
    if not config:
        raise ManifestUnavailable(Status.SKIP, "config が無いので照合しない")
    lesion = config.get("lesion") or {}
    own_condition = lesion.get("condition")
    if own_condition == LESION_CONDITION_NONE:
        raise ManifestUnavailable(
            Status.SKIP, "condition=none は FT データを生成しない(PLAN-002 §3.4)"
        )
    declared = (config.get("data") or {}).get("matched_manifests")
    if not declared:
        raise ManifestUnavailable(
            Status.FAIL,
            "data.matched_manifests が null。全病変条件の manifest を config に宣言すること"
            "(PLAN-002 §4.8.1)。null のまま実行しない",
        )
    manifests: dict[str, dict[str, Any]] = {}
    for entry in declared:
        manifest = _load_manifest_file(_resolve(entry))
        condition = (manifest.get("lesion") or {}).get("condition")
        if condition is None:
            raise ManifestUnavailable(Status.FAIL, f"{entry} の lesion.condition が null")
        if condition in manifests:
            raise ManifestUnavailable(
                Status.FAIL, f"病変条件 {condition!r} の manifest が2つ宣言されている"
            )
        manifests[condition] = manifest
    if own_condition is not None and own_condition not in manifests:
        raise ManifestUnavailable(
            Status.FAIL,
            f"この実行の条件 {own_condition!r} が data.matched_manifests に無い",
        )
    return manifests


def load_anchor_manifest(config: Mapping[str, Any]) -> dict[str, Any]:
    """評価アンカー(§5.2 の T1)の manifest を読む(§4.8.1 検査6)。

    答える問い: 「訓練書式と照合すべき評価側の書式は、どこに記録されているか」
    """
    declared = (config.get("eval") or {}).get("anchor_manifest")
    if not declared:
        raise ManifestUnavailable(
            Status.FAIL,
            "eval.anchor_manifest が null。訓練書式と評価アンカーの書式を照合できない"
            "(PLAN-002 §4.8.1 検査6)",
        )
    path = _resolve(declared)
    if not path.exists():
        raise ManifestUnavailable(Status.FAIL, f"評価アンカーの manifest が無い: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if "prompt_format" not in manifest:
        raise ManifestUnavailable(
            Status.FAIL,
            f"{path.name} に prompt_format が無い(PLAN-002 §4.8 と同形のブロックが要る)",
        )
    return manifest


def load_eval_cells(config: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """評価プールのセル定義を読む(§4.8.1 検査8)。

    答える問い: 「評価プールは、訓練で見た組を何組要求するか」
    """
    declared = (config.get("eval") or {}).get("cells")
    if not declared:
        raise ManifestUnavailable(
            Status.FAIL,
            "eval.cells が null。id セル要求を数えられない(PLAN-001 §4.2.2)。"
            "**リテラルの閾値は置かない**ので、セル定義が無いと検査そのものが成立しない",
        )
    for cell in declared:
        if not isinstance(cell, Mapping) or "coverage" not in cell or "n" not in cell:
            raise ManifestUnavailable(
                Status.FAIL, f"eval.cells の要素に coverage / n が無い: {cell!r}"
            )
    return list(declared)


def check_pool_regions(manifests: Mapping[str, dict[str, Any]]) -> CheckResult:
    """pilot / main 領域が交わらず、K が自分の領域から引かれているか(検査3 の拡張)。

    答える問い: 「ハイパラ選択に使った組が、本実験の訓練被覆に混ざっていないか」

    counterpart_coverage_hash は null のままである。相手側の K は相手側の
    coverage_k を知らないと決まらない(PLAN-002 §4.8)。代わりに
    counterpart_region_hash を、manifest 自身が記録した分割パラメータから
    **再現して**照合する。再現できないなら、分割が記録と別物になっている。
    """
    empty = _no_manifests("pool regions", manifests)
    if empty is not None:
        return empty
    ft_data, pool = _repo_modules()
    problems: list[str] = []
    for condition, manifest in sorted(manifests.items()):
        split = manifest["pool_split"]
        domain = manifest["train_domain"]
        regions = pool.split_pilot_main(
            ft_data.train_domain_pairs(domain["lo"], domain["hi"]),
            split["pilot_train_region_size"],
            split["pool_split_seed"],
        )
        counterpart = split["counterpart_pool_id"]
        if pool.pairs_hash(regions[counterpart]) != split["counterpart_region_hash"]:
            problems.append(f"{condition}: counterpart_region_hash が再現しない")
        outside = _pairs_of(manifest) - set(regions[split["pool_id"]])
        if outside:
            problems.append(f"{condition}: K の {len(outside)} 組が自分の領域の外にある")
    problems.extend(_cross_pool_overlaps(manifests))
    return _verdict("pool regions", problems, f"{len(manifests)} 条件で領域と K が整合")


def _cross_pool_overlaps(manifests: Mapping[str, dict[str, Any]]) -> list[str]:
    """pool_id が違う manifest 同士で K が交わっていないか(K_pilot ∩ K_main = ∅)。"""
    problems: list[str] = []
    items = sorted(manifests.items())
    for index, (condition, manifest) in enumerate(items):
        for other_condition, other in items[index + 1 :]:
            if manifest["pool_split"]["pool_id"] == other["pool_split"]["pool_id"]:
                continue
            shared = _pairs_of(manifest) & _pairs_of(other)
            if shared:
                problems.append(
                    f"{condition} と {other_condition} の K が {len(shared)} 組重なっている"
                )
    return problems


def check_matched_stream(manifests: Mapping[str, dict[str, Any]]) -> CheckResult:
    """全病変条件の訓練データが target 以外で一致するか(§3.4、§4.8.1 検査5)。

    答える問い: 「条件間の差は target だけか。組の抽出・反復・整列が
    病変に依存していないか」

    先に §3.4 のタプルを照合するのは、生成パラメータが違えばハッシュが
    違うのは当たり前であり、**「ずれている」の中身が別物になる**ため。
    """
    if len(manifests) < 2:
        return CheckResult(
            "matched stream",
            Status.FAIL,
            f"照合相手が無い(宣言された条件が {len(manifests)} 件)。§3.4 は条件間の一致を問う",
        )
    premise = {
        condition: (
            manifest["coverage"]["coverage_seed"],
            manifest["sampling"]["sample_seed"],
            manifest["coverage"]["coverage_k"],
            manifest["sampling"]["train_size"],
            manifest["pool_split"]["pool_id"],
        )
        for condition, manifest in manifests.items()
    }
    if len(set(premise.values())) != 1:
        return CheckResult(
            "matched stream",
            Status.FAIL,
            f"生成パラメータが条件間で違う(§3.4 の前提が崩れている): {premise}",
        )
    hashes = {
        condition: manifest["outputs"]["matched_stream_sha256"]
        for condition, manifest in manifests.items()
    }
    if len(set(hashes.values())) != 1:
        return CheckResult(
            "matched stream", Status.FAIL, f"条件間で訓練データがずれている: {hashes}"
        )
    shared = next(iter(hashes.values()))
    return CheckResult(
        "matched stream", Status.PASS, f"{len(manifests)} 条件で一致 @ {shared[:12]}"
    )


def check_format_hash(
    manifests: Mapping[str, dict[str, Any]], anchor: Mapping[str, Any]
) -> CheckResult:
    """書式ハッシュが全条件と評価アンカーで一致するか(§4.8.1 検査6)。

    答える問い: 「訓練と評価が、同じ1文字単位の書式を使っているか」

    記録値をそのまま信じず prompt_format から再計算する。生成後に
    prompt_format を手で書き換えても format_hash は追随しないので、
    **記録が古いこと自体を検出する**必要がある。
    """
    empty = _no_manifests("format hash", manifests)
    if empty is not None:
        return empty
    ft_data, _ = _repo_modules()
    problems: list[str] = []
    for condition, manifest in sorted(manifests.items()):
        fields = manifest["prompt_format"]
        recomputed = ft_data.sha256_text(
            ft_data.canonical_json({k: v for k, v in fields.items() if k != "format_hash"})
        )
        if fields.get("format_hash") != recomputed:
            problems.append(f"{condition}: format_hash が prompt_format と合わない(記録が古い)")
    recorded = {c: m["prompt_format"].get("format_hash") for c, m in manifests.items()}
    shared = set(recorded.values())
    if len(shared) != 1:
        problems.append(f"条件間で書式が違う: {recorded}")
    else:
        anchor_hash = anchor["prompt_format"].get("format_hash")
        train_hash = next(iter(shared))
        if anchor_hash != train_hash:
            problems.append(f"評価アンカーと書式が違う: anchor={anchor_hash} train={train_hash}")
    return _verdict("format hash", problems, f"{len(manifests)} 条件 + アンカーで一致")


def check_coverage_k_floor(
    manifests: Mapping[str, dict[str, Any]], cells: Sequence[Mapping[str, Any]]
) -> CheckResult:
    """被覆 K が評価プールの id セル要求を満たすか(§4.8.1 検査8、PLAN-001 §4.2.2)。

    答える問い: 「訓練で見た組だけで、評価プールの id セルを埋めきれるか」

    **リテラルの閾値を置かない**(PLAN-001 §4.2.2)。要求は eval.cells の
    id セルの n の合計として実行時に数える。fill_cells はセル間で組を
    再利用しないので(ADR-017)、合計がそのまま K の下限になる。
    """
    empty = _no_manifests("coverage_k floor", manifests)
    if empty is not None:
        return empty
    _, pool = _repo_modules()
    demand = sum(int(cell["n"]) for cell in cells if cell["coverage"] == pool.COVERAGE_ID)
    if demand <= 0:
        return CheckResult(
            "coverage_k floor",
            Status.FAIL,
            f"eval.cells に coverage={pool.COVERAGE_ID!r} のセルが無い。下限を数えられない",
        )
    problems = [
        f"{condition}: coverage_k={manifest['coverage']['coverage_k']} < id 要求 {demand}"
        for condition, manifest in sorted(manifests.items())
        if manifest["coverage"]["coverage_k"] < demand
    ]
    return _verdict("coverage_k floor", problems, f"id 要求 {demand} 組をすべての条件が満たす")


def check_t_holdout(manifests: Mapping[str, dict[str, Any]]) -> CheckResult:
    """T_hold が決定的で、全条件・全実験シードで同一か(ADR-029 決定3、検査9)。

    答える問い: 「t_seen / t_unseen のラベルは、実行をまたいで同じ意味を持つか」

    記録された sums を §4.2.1a の構成から**再現して**照合する。ハッシュの
    一致だけでは「全条件で同じようにずれている」場合を見逃す。
    """
    empty = _no_manifests("t_holdout", manifests)
    if empty is not None:
        return empty
    ft_data, _ = _repo_modules()
    problems: list[str] = []
    for condition, manifest in sorted(manifests.items()):
        holdout = manifest["t_holdout"]
        sums = [int(total) for total in holdout["sums"]]
        if sums != sorted(set(sums)):
            problems.append(f"{condition}: t_holdout.sums が昇順の相異なる整数でない")
        answer_lo, answer_hi = manifest["train_answer_range"]
        expected = list(ft_data.build_t_holdout(answer_lo, answer_hi, holdout["size"]))
        if sums != expected:
            problems.append(f"{condition}: sums が §4.2.1a の構成と一致しない(決定的でない)")
        if holdout["sums_hash"] != ft_data.sha256_text(ft_data.canonical_json(sums)):
            problems.append(f"{condition}: sums_hash が sums と合わない")
    shared = sorted({manifest["t_holdout"]["sums_hash"] for manifest in manifests.values()})
    if len(shared) != 1:
        problems.append(f"sums_hash が条件間で不一致: {shared}")
    return _verdict("t_holdout", problems, f"{len(manifests)} 条件で同一 @ {shared[0][:12]}")


def check_holdout_leak(manifests: Mapping[str, dict[str, Any]]) -> CheckResult:
    """K の和集合が T_hold と交わらないか(ADR-029 決定1、検査10)。

    答える問い: 「訓練で一度も出さないはずの和が、訓練被覆に漏れていないか」

    coverage_sums の記録も pairs から数え直す。t_seen / t_unseen のラベルは
    この記録を使うので、記録が pairs とずれていたらラベルそのものが嘘になる。
    """
    empty = _no_manifests("holdout leak", manifests)
    if empty is not None:
        return empty
    problems: list[str] = []
    for condition, manifest in sorted(manifests.items()):
        sums_of_coverage = {a + b for a, b in _pairs_of(manifest)}
        recorded = {int(total) for total in manifest["coverage"].get("coverage_sums") or []}
        if recorded != sums_of_coverage:
            problems.append(f"{condition}: coverage_sums が pairs から数え直した集合と違う")
        leaked = sorted(sums_of_coverage & {int(t) for t in manifest["t_holdout"]["sums"]})
        if leaked:
            problems.append(f"{condition}: T_hold の和 {leaked[:5]} が K に漏れている")
    return _verdict("holdout leak", problems, f"{len(manifests)} 条件で T_hold と交わらない")


def _token_boundary_record(
    tokenizer: Any, prompt: str, completion: str, templated: bool
) -> tuple[dict[str, Any], list[str]]:
    """1例のトークン境界を測る(§4.1.5 の1〜3)。

    答える問い: 「この1例で、損失を completion と EOS だけに掛けられるか」

    add_special_tokens をテンプレート版で False にする理由: chat_template が
    既に BOS を入れる。True にすると BOS が2つ乗り、§4.1.4 の
    「シーケンス先頭に1つだけ」が壊れる。
    """
    label = ("templated" if templated else "bare") + f":{prompt!r}+{completion!r}"
    add_special = not templated
    ids_prompt = list(tokenizer(prompt, add_special_tokens=add_special)["input_ids"])
    ids_completion = list(tokenizer(completion, add_special_tokens=False)["input_ids"])
    try:
        joint = tokenizer(
            prompt + completion, add_special_tokens=add_special, return_offsets_mapping=True
        )
        offsets = [tuple(span) for span in joint["offset_mapping"]]
    except (NotImplementedError, ValueError, TypeError):
        joint = tokenizer(prompt + completion, add_special_tokens=add_special)
        offsets = None
    ids_joint = list(joint["input_ids"])

    problems: list[str] = []
    # §4.1.5 の3: 境界でトークン列が分かれること。損失マスクの境界はここに置く。
    if ids_joint != ids_prompt + ids_completion:
        problems.append(f"{label}: tokenize(p+c) != tokenize(p)+tokenize(c)")
    # §4.1.5 の2: `=` と completion 先頭の数字が同一トークンに融合していないこと。
    boundary = len(prompt)
    if offsets is None:
        problems.append(f"{label}: offset_mapping が取れず融合を確認できない(**未実行**)")
        fused = None
    else:
        fused = [span for span in offsets if span[0] < boundary < span[1]]
        if fused:
            problems.append(f"{label}: 境界をまたぐトークンがある {fused}")
    bos_id = getattr(tokenizer, "bos_token_id", None)
    record = {
        "templated": templated,
        "prompt": prompt,
        "completion": completion,
        "prompt_ids": ids_prompt,  # §4.1.5 の1: ID 列そのものを残す
        "completion_ids": ids_completion,
        "joint_ids": ids_joint,
        "fused_spans": fused,
        "bos_count": None if bos_id is None else ids_joint.count(bos_id),
    }
    return record, problems


def check_token_boundaries(config: Mapping[str, Any], record_dir: Path) -> CheckResult:
    """訓練書式のトークン境界を確認し、記録する(§4.1.5、§4.8.1 検査7)。

    答える問い: 「損失を completion と EOS だけに掛けられるか」

    テンプレート版と無テンプレート版の両方を見る。前者が FT と評価の本体
    (ADR-025)、後者が ADR-025 決定2 の「テンプレート税」アンカーである。
    融合が起こり得るのは無テンプレート版だけだが、**両方を記録しないと
    テンプレート税の差が書式由来かトークン化由来かを切り分けられない。**

    **モデルを読めない環境で PASS にしない。**未実行は FAIL として報告する
    (PLAN-002 §4.8.1)。既定でトークン境界を仮定すると損失マスクが静かにずれる。
    """
    name = "token boundaries"
    if not config:
        return CheckResult(name, Status.SKIP, "config が無いので確認しない")
    model = config.get("model") or {}
    data = config.get("data") or {}
    unset = [
        key
        for key, value in (
            ("model.name", model.get("name")),
            ("model.revision", model.get("revision")),
            ("data.prompt_template", data.get("prompt_template")),
            ("data.completion_template", data.get("completion_template")),
        )
        if not value
    ]
    if unset:
        return CheckResult(
            name, Status.FAIL, f"{unset} が null。null のまま本実行に入らない(ADR-031)"
        )
    try:
        from transformers import AutoTokenizer  # noqa: PLC0415
    except ImportError:
        return CheckResult(
            name, Status.FAIL, "transformers が無くトークン境界が**未実行**。既定値で通さない"
        )
    try:
        tokenizer = AutoTokenizer.from_pretrained(model["name"], revision=model["revision"])
    except Exception as exc:  # noqa: BLE001 — 読めない理由を問わず未実行として落とす
        return CheckResult(
            name,
            Status.FAIL,
            f"トークナイザを読めずトークン境界が**未実行**: {type(exc).__name__}: {exc}",
        )

    records: list[dict[str, Any]] = []
    problems: list[str] = []
    for templated in (True, False):
        for a, b, target in PROMPT_FORMAT_EXAMPLES:
            try:
                prompt = data["prompt_template"].format(a=a, b=b)
                completion = data["completion_template"].format(target=target)
            except (KeyError, IndexError) as exc:
                # 書式そのものが壊れている。preflight が落ちるのではなく報告する。
                return CheckResult(name, Status.FAIL, f"書式テンプレートを展開できない: {exc}")
            if templated:
                try:
                    prompt = tokenizer.apply_chat_template(
                        [{"role": "user", "content": prompt}],
                        tokenize=False,
                        add_generation_prompt=True,
                    )
                except Exception as exc:  # noqa: BLE001 — 適用できない = 未実行
                    return CheckResult(
                        name,
                        Status.FAIL,
                        f"chat_template を適用できず**未実行**: {type(exc).__name__}: {exc}",
                    )
            record, failures = _token_boundary_record(tokenizer, prompt, completion, templated)
            records.append(record)
            problems.extend(failures)

    path = _write_token_boundary_record(records, model, tokenizer, record_dir)
    return _verdict(name, problems, f"{len(records)} 例を確認し {path.name} に記録した")


def _write_token_boundary_record(
    records: Sequence[Mapping[str, Any]],
    model: Mapping[str, Any],
    tokenizer: Any,
    record_dir: Path,
) -> Path:
    """トークン境界の測定を runs/ に残す(§4.1.5「runs/<id>/ に記録する」)。

    答える問い: 「本実行のときトークン境界がどうだったかを、後から言えるか」

    ここで **テンプレート適用後の書式ハッシュ**も出す。§4.1.3 はこれを
    format_hash の正しい取り方と定めたが、ft_data.py はトークナイザに
    触らないため manifest 側では計算できない(§4.8 の実装注記)。
    **preflight の責務としてここに置く。**
    """
    ft_data, _ = _repo_modules()
    record_dir.mkdir(parents=True, exist_ok=True)
    path = record_dir / "token_boundary.json"
    templated = [record["prompt"] for record in records if record["templated"]]
    bare = [record["prompt"] for record in records if not record["templated"]]
    payload = {
        "plan": "plans/PLAN-002-ft-data.md",
        "section": "§4.1.5",
        "model": {"name": model.get("name"), "revision": model.get("revision")},
        "chat_template_sha256": ft_data.sha256_text(
            getattr(tokenizer, "chat_template", None) or ""
        ),
        "templated_format_hash": ft_data.sha256_text(ft_data.canonical_json(templated)),
        "bare_format_hash": ft_data.sha256_text(ft_data.canonical_json(bare)),
        "examples": list(records),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def data_checks(config: Mapping[str, Any]) -> list[CheckResult]:
    """PLAN-002 §4.8.1 の manifest 系検査をまとめて実行する。

    答える問い: 「この config が指す FT データは、実験条件どおりに作られているか」

    manifest 一式を組めなかったときは、**同じ理由を全項目に載せて返す。**
    一部だけ PASS に見せると「何が確認できていないか」が消える。
    """
    try:
        manifests = load_ft_manifests(config)
    except ManifestUnavailable as exc:
        return [CheckResult(name, exc.status, exc.detail) for name in DATA_CHECK_NAMES]

    try:
        format_result = check_format_hash(manifests, load_anchor_manifest(config))
    except ManifestUnavailable as exc:
        format_result = CheckResult("format hash", exc.status, exc.detail)
    try:
        floor_result = check_coverage_k_floor(manifests, load_eval_cells(config))
    except ManifestUnavailable as exc:
        floor_result = CheckResult("coverage_k floor", exc.status, exc.detail)

    return [
        check_pool_regions(manifests),
        check_matched_stream(manifests),
        format_result,
        floor_result,
        check_t_holdout(manifests),
        check_holdout_leak(manifests),
    ]


# --------------------------------------------------------------------------
# 実行
# --------------------------------------------------------------------------


def load_config(config_path: Path | None) -> dict:
    """config YAML を読む。渡されなければ空 dict。"""
    if config_path is None:
        return {}
    import yaml  # noqa: PLC0415 — config を使うときだけ必要

    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def run_all_checks(config: dict, record_dir: Path) -> list[CheckResult]:
    """全項目を実行して結果を集める。

    順序は infra/RUNPOD.md §3 の一覧、次に PLAN-002 §4.8.1 の manifest 系。
    record_dir はトークン境界の測定を書き出す先(§4.1.5)。
    """
    resources = config.get("resources", {})
    model = config.get("model", {})
    data = config.get("data", {})
    manifest_path = Path(data["manifest"]) if data.get("manifest") else None

    return [
        check_stdlib_code_shim(),
        check_gpu(resources.get("min_vram_gb")),
        check_library_versions(),
        check_persistent_volume(),
        check_model_weights(model.get("name")),
        check_data_manifest(manifest_path),
        *data_checks(config),
        check_token_boundaries(config, record_dir),
        check_tests(),
        check_git_clean(),
        check_writable_dirs(),
    ]


def main() -> int:
    """検査を実行し、FAIL があれば 1 を返す。"""
    # Windows のコンソール既定は cp932 で、日本語の detail が化けて読めなくなる。
    # 読めない検査結果は無いのと同じなので、明示的に UTF-8 に切り替える。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="本実行前の環境検証 (infra/RUNPOD.md §3)")
    parser.add_argument(
        "--config", type=Path, default=None, help="実験 config。VRAM 閾値・モデル・manifest の照合に使う"
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=REPO_ROOT / "runs" / "preflight",
        help="トークン境界の測定を書き出す先(PLAN-002 §4.1.5)。本実行では runs/<id>/ を渡す",
    )
    args = parser.parse_args()

    results = run_all_checks(load_config(args.config), args.run_dir)

    width = max(len(r.name) for r in results)
    for result in results:
        print(f"[{result.status.value:4}] {result.name:<{width}}  {result.detail}")

    failures = [r for r in results if r.status is Status.FAIL]
    warnings = [r for r in results if r.status is Status.WARN]
    print()
    if failures:
        print(f"FAIL {len(failures)} 件。**本実行を開始しないこと** (infra/RUNPOD.md §3)")
        return 1
    if warnings:
        print(f"WARN {len(warnings)} 件。内容を確認してから開始すること")
    else:
        print("全項目 PASS。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
