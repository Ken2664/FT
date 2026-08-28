"""`runs/<id>/` に残す来歴(infra/RUNPOD.md §4「必ず残すもの」)。

答える問い: 「この数値が、どのコードの、どの設定の、いつの実行から出たかを
後から言えるか」

**層に依らない場所に置いてある**(旧 `code/eval/artifacts.py`。2026-08-27 に移した)。
`code/eval/`(本実行・桁数掃引)と `code/train/`(LoRA 訓練)の両方が使うため、
どちらかの層に置くと層をまたぐ import が生まれる(skill code-style §2)。
`code/config.py` を出したのと同じ理由である。

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
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from code.config import require

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = REPO_ROOT / "runs"

PREDICTIONS_DIR = "predictions"
# 壁時計の秒を丸める桁(ミリ秒)。**実験条件ではなく記録の書式である。**
ELAPSED_DIGITS = 3
# dirty のまま回したときに残す差分。git_sha.txt だけでは、実際に走った
# コードを後から復元できない(infra/preflight.py の check_git_clean と同じ理由)。
DIFF_FILE = "git_diff.patch"


def utc_now() -> datetime:
    return datetime.now(UTC)


def monotonic_seconds() -> float:
    """区間の長さを測るための時計を読む。

    答える問い: 「いま何秒地点か」

    **`utc_now()` の差を使わない。**壁時計は NTP の補正で後ろへ跳ぶことがあり、
    そのとき区間の長さが負になる。「いつ回したか」は `utc_now()`(timestamp.txt)、
    「何秒かかったか」はこちら、と役割を分けてある。
    """
    return time.monotonic()


def elapsed_seconds(start: float, *, end: float | None = None) -> float:
    """`monotonic_seconds()` で取った2点の間の秒数。

    答える問い: 「この区間は何秒かかったか」
    """
    finish = monotonic_seconds() if end is None else end
    return round(finish - start, ELAPSED_DIGITS)


def seconds_per_item(seconds: float, n_items: int) -> float | None:
    """1項目あたりの秒数。項目が0件なら None を返す。

    答える問い: 「この装置は1項目を何秒で処理したか」

    **0 件のときに 0.0 を返さない。**「1項目 0 秒で回った」と読めてしまい、
    `eval.batch_size` を壁時計時間から決める材料(ADR-040 決定6)として嘘になる。
    """
    if n_items <= 0:
        return None
    return round(seconds / n_items, ELAPSED_DIGITS)


def timing_record(
    *,
    started: datetime,
    ended: datetime,
    total_seconds: float,
    model_load_seconds: float,
    generation_seconds: float,
    n_items: int,
) -> dict[str, Any]:
    """metrics.json の `timing` ブロック。

    答える問い: 「この実行は何秒かかったか。そのうち生成は何秒で、1項目
    あたり何秒だったか」

    **`eval.batch_size` の値はこの記録から決まる**(ADR-040 決定6: 「順1b の
    壁時計時間を見てから確定する」)。2026-08-28 まで `runs/` に壁時計時間が
    1つも残っておらず、決定6 が成り立たなかった。

    **重みの読み込みを生成と分けて持つ。**8B の重みの読み込みは分単位で、
    順1b の 19 項目の生成より桁が大きい。合算した秒数からは「1項目あたり
    何秒か」が読めず、まとめ幅の選択に使えない。

    `seconds_per_item` は**生成の区間から取る**。重みの読み込みはまとめ幅を
    変えても動かないので、そこを混ぜると幅の効果が薄まって見える。
    """
    return {
        "started_utc": started.isoformat(),
        "ended_utc": ended.isoformat(),
        "total_seconds": round(total_seconds, ELAPSED_DIGITS),
        "model_load_seconds": round(model_load_seconds, ELAPSED_DIGITS),
        "generation_seconds": round(generation_seconds, ELAPSED_DIGITS),
        "n_items": n_items,
        "seconds_per_item": seconds_per_item(generation_seconds, n_items),
    }


def timing_line(timing: Mapping[str, Any]) -> str:
    """`timing` ブロックを log.txt の1行にする。

    答える問い: 「この実行は何秒かかったと報告するか」

    **鍵の名前を知っているのはこのモジュールだけにする。**`timing_record` と
    別の場所で組み立てると、片方の鍵を変えたときにもう片方が KeyError で
    落ちる(しかも生成が終わった後に落ちる)。
    """
    per_item = timing["seconds_per_item"]
    per_item_text = "-" if per_item is None else f"{per_item:.3f}"
    return (
        f"壁時計: 合計 {timing['total_seconds']:.3f}s "
        f"(重み読み込み {timing['model_load_seconds']:.3f}s / "
        f"生成 {timing['generation_seconds']:.3f}s / "
        f"{timing['n_items']} 項目 = {per_item_text}s/項目)"
    )


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
