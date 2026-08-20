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
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class Status(Enum):
    """検査結果の3値。FAIL のみが実行を止める。"""

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
# 実行
# --------------------------------------------------------------------------


def load_config(config_path: Path | None) -> dict:
    """config YAML を読む。渡されなければ空 dict。"""
    if config_path is None:
        return {}
    import yaml  # noqa: PLC0415 — config を使うときだけ必要

    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def run_all_checks(config: dict) -> list[CheckResult]:
    """全項目を実行して結果を集める。順序は infra/RUNPOD.md §3 に合わせる。"""
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
    args = parser.parse_args()

    results = run_all_checks(load_config(args.config))

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
