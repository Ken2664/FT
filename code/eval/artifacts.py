"""`runs/<id>/` に残す来歴(infra/RUNPOD.md §4「必ず残すもの」)。

答える問い: 「この数値が、どのコードの、どの設定の、いつの実行から出たかを
後から言えるか」

**ここが書かないものが2つある**(RUNPOD.md §4 の一覧のうち):

  - `token_boundary.json` —— `python infra/preflight.py --run-dir <dir>` が書く(検査7)
  - `cost.txt` —— GPU 時間と課金額。評価ハーネスは課金を知らない(RUNPOD.md §7)

**空ファイルで埋めない。**無いものは無いままにし、どちらが書くかは
RUNPOD.md §4 に明記した。中身の無い cost.txt があると「記録した」と
見分けがつかなくなる。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from code.config import require

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = REPO_ROOT / "runs"

PREDICTIONS_DIR = "predictions"
# dirty のまま回したときに残す差分。git_sha.txt だけでは、実際に走った
# コードを後から復元できない(infra/preflight.py の check_git_clean と同じ理由)。
DIFF_FILE = "git_diff.patch"


def utc_now() -> datetime:
    return datetime.now(UTC)


def run_id_for(config: Mapping[str, Any], *, now: datetime) -> str:
    """`runs/<id>/` の id。書式は configs/template.yaml の宣言に従う。

    答える問い: 「この実行をどの名前で残すか」
    """
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{require(config, 'experiment.id')}"


def prepare_run_dir(
    config: Mapping[str, Any], *, explicit: Path | None, now: datetime
) -> Path:
    """run ディレクトリを決めて作る。

    答える問い: 「成果物をどこに書くか」

    `--run-dir` を受けるのは RUNPOD.md §4 の手順のためである。あちらは
    **本実行の前に** preflight を同じディレクトリに向けて走らせ
    (`token_boundary.json` を置く)、そのあと評価を回す。run 側が毎回
    新しい名前を作ってしまうと、検査7 の記録と数値が別のディレクトリに割れる。
    """
    run_dir = explicit if explicit is not None else RUNS_ROOT / run_id_for(config, now=now)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / PREDICTIONS_DIR).mkdir(exist_ok=True)
    return run_dir


def _capture(command: Sequence[str]) -> str:
    """外部コマンドの出力を取る。失敗しても実行を止めず、理由を文字列で残す。

    来歴が取れないこと自体が記録に値する。ここで例外を上げると、生成が
    終わっているのに成果物が書けずに落ちる。
    """
    try:
        completed = subprocess.run(  # noqa: S603
            list(command),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            cwd=REPO_ROOT,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"<取得できず: {type(exc).__name__}: {exc}>"
    return ((completed.stdout or "") + (completed.stderr or "")).strip()


def write_config_copy(run_dir: Path, config_path: Path) -> None:
    """使用した設定の完全コピー。**再 dump ではなくファイルをそのまま複製する。**

    YAML を読み直して書き戻すと、コメントが落ちる。この repo の config は
    「★smoke のみ」「[MATCHED]」などの但し書きをコメントに持っており、
    それが落ちると後から条件の意味が読めない。
    """
    shutil.copyfile(config_path, run_dir / "config.yaml")


def write_git_sha(run_dir: Path) -> None:
    """コミットハッシュ。dirty なら差分も残す(RUNPOD.md §4)。"""
    sha = _capture(["git", "rev-parse", "HEAD"])
    status = _capture(["git", "status", "--porcelain"])
    dirty = bool(status) and not status.startswith("<取得できず")
    (run_dir / "git_sha.txt").write_text(
        f"{sha}\ndirty: {str(dirty).lower()}\n", encoding="utf-8"
    )
    if dirty:
        (run_dir / DIFF_FILE).write_text(_capture(["git", "diff", "HEAD"]), encoding="utf-8")


def write_env(run_dir: Path) -> None:
    """環境の記録。中身は RUNPOD.md §6「記録すべきこと」の5点。"""
    sections = {
        "nvidia-smi": _capture(["nvidia-smi"]),
        "python --version": sys.version.replace("\n", " "),
        "pip freeze": _capture([sys.executable, "-m", "pip", "freeze"]),
        "git rev-parse HEAD": _capture(["git", "rev-parse", "HEAD"]),
        "date -u": utc_now().isoformat(),
    }
    body = "\n\n".join(f"### {name}\n{value}" for name, value in sections.items())
    (run_dir / "env.txt").write_text(body + "\n", encoding="utf-8")


def write_timestamps(run_dir: Path, *, started: datetime, ended: datetime) -> None:
    """開始・終了(RUNPOD.md §4 の `date -u` の出力)。"""
    (run_dir / "timestamp.txt").write_text(
        f"started_utc: {started.isoformat()}\nended_utc: {ended.isoformat()}\n", encoding="utf-8"
    )


def write_metrics(run_dir: Path, payload: Mapping[str, Any]) -> Path:
    """全指標の生値。**これは実験結果である**(--dry-run の出力とは違う)。"""
    path = run_dir / "metrics.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_predictions(run_dir: Path, name: str, records: Sequence[Mapping[str, Any]]) -> Path:
    """モデル出力の生ログ(再解析用)。1行1応答。

    答える問い: 「4値分解のどの1件が、どの生成文字列から来たか」

    パーサの取りこぼしは `parse_fail_rate` に化ける(skill code-style §2)。
    生の文字列を残さないと、それがモデルの崩壊なのか抽出の失敗なのかを
    後から切り分けられない。
    """
    path = run_dir / PREDICTIONS_DIR / f"{name}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def write_log(run_dir: Path, lines: Sequence[str]) -> Path:
    """標準出力の写し(RUNPOD.md §4 の log.txt)。"""
    path = run_dir / "log.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
