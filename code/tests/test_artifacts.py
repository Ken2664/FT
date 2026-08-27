"""`runs/<id>/` の成果物(code/eval/artifacts.py)のテスト。

答える問い: 「この数値が、どのコードの、どの設定の、いつの実行から出たかを
後から言えるか」(infra/RUNPOD.md §4)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from code.config import ConfigError
from code.eval import artifacts

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

FIXED_TIME = datetime(2026, 9, 1, 14, 30, 22, tzinfo=UTC)

# artifacts が**書かないもの**(モジュール冒頭の注記)。
# token_boundary.json は preflight 検査7、cost.txt は課金(RUNPOD.md §7)の担当。
NOT_WRITTEN_HERE = ("token_boundary.json", "cost.txt")


@pytest.fixture
def config() -> dict[str, object]:
    return {"experiment": {"id": "exp042"}}


def test_run_id_joins_the_timestamp_and_the_experiment_id(config: dict[str, object]) -> None:
    """run_id の書式は configs/template.yaml の宣言に従う。"""
    assert artifacts.run_id_for(config, now=FIXED_TIME) == "20260901_143022_exp042"


def test_run_id_requires_the_experiment_id() -> None:
    """★experiment.id が null なら止まる。名前の無い run は追跡できない。"""
    with pytest.raises(ConfigError, match="experiment.id"):
        artifacts.run_id_for({"experiment": {"id": None}}, now=FIXED_TIME)


def test_explicit_run_dir_is_used_as_is(config: dict[str, object], tmp_path: Path) -> None:
    """★--run-dir を渡したらそこに書く(infra/RUNPOD.md §4)。

    preflight は**本実行の前に**同じディレクトリへ token_boundary.json を置く。
    run 側が毎回新しい名前を作ると、検査7 の記録と数値が別の dir に割れる。
    """
    target = tmp_path / "given"
    assert artifacts.prepare_run_dir(config, explicit=target, now=FIXED_TIME) == target
    assert (target / artifacts.PREDICTIONS_DIR).is_dir()


def test_default_run_dir_is_under_the_runs_root(
    config: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--run-dir を省略したら runs/<timestamp>_<id>/ を作る。"""
    monkeypatch.setattr(artifacts, "RUNS_ROOT", tmp_path / "runs")
    target = artifacts.prepare_run_dir(config, explicit=None, now=FIXED_TIME)
    assert target == tmp_path / "runs" / "20260901_143022_exp042"
    assert (target / artifacts.PREDICTIONS_DIR).is_dir()


def test_config_copy_is_byte_identical(tmp_path: Path) -> None:
    """★config は再 dump ではなくファイルのまま複製する。

    YAML を読み直して書き戻すとコメントが落ちる。この repo の config は
    「★smoke のみ」「[MATCHED]」を**コメントに**持っており、落ちると後から
    条件の意味が読めない。
    """
    artifacts.write_config_copy(tmp_path, SMOKE_CONFIG)
    assert (tmp_path / "config.yaml").read_bytes() == SMOKE_CONFIG.read_bytes()
    assert "★smoke のみ" in (tmp_path / "config.yaml").read_text(encoding="utf-8")


def test_git_sha_records_the_dirty_flag(tmp_path: Path) -> None:
    """コミットハッシュと dirty かどうかを残す(RUNPOD.md §4)。"""
    artifacts.write_git_sha(tmp_path)
    body = (tmp_path / "git_sha.txt").read_text(encoding="utf-8")
    assert "dirty: " in body
    if "dirty: true" in body:
        assert (tmp_path / artifacts.DIFF_FILE).exists()


def test_env_records_the_five_sections(tmp_path: Path) -> None:
    """環境の記録は RUNPOD.md §6「記録すべきこと」の5点(GPU 無しでも書く)。"""
    artifacts.write_env(tmp_path)
    body = (tmp_path / "env.txt").read_text(encoding="utf-8")
    for section in ("nvidia-smi", "python --version", "pip freeze", "git rev-parse HEAD"):
        assert f"### {section}" in body


def test_timestamps_record_both_ends(tmp_path: Path) -> None:
    """開始と終了の両方を残す(RUNPOD.md §4 の date -u)。"""
    ended = datetime(2026, 9, 1, 15, 0, 0, tzinfo=UTC)
    artifacts.write_timestamps(tmp_path, started=FIXED_TIME, ended=ended)
    body = (tmp_path / "timestamp.txt").read_text(encoding="utf-8")
    assert FIXED_TIME.isoformat() in body
    assert ended.isoformat() in body


def test_metrics_are_written_as_readable_json(tmp_path: Path) -> None:
    """metrics.json は日本語を退避せずに書く(後から人間が読む)。"""
    path = artifacts.write_metrics(tmp_path, {"note": "病変", "correct_rate": 0.5})
    assert json.loads(path.read_text(encoding="utf-8")) == {"note": "病変", "correct_rate": 0.5}
    assert "病変" in path.read_text(encoding="utf-8")


def test_predictions_are_one_line_per_response(tmp_path: Path) -> None:
    """★生ログは1行1応答。パーサの取りこぼしを後から切り分けるため。"""
    (tmp_path / artifacts.PREDICTIONS_DIR).mkdir()
    records = [{"item_id": f"i{i}", "response": f"r{i}"} for i in range(3)]
    path = artifacts.write_predictions(tmp_path, "bare_sum", records)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(line) for line in lines] == records


def test_log_is_written(tmp_path: Path) -> None:
    """標準出力の写し(RUNPOD.md §4 の log.txt)。"""
    path = artifacts.write_log(tmp_path, ["一行目", "二行目"])
    assert path.read_text(encoding="utf-8") == "一行目\n二行目\n"


def test_cost_and_token_boundary_are_not_written_here(
    config: dict[str, object], tmp_path: Path
) -> None:
    """★このモジュールは cost.txt と token_boundary.json を書かない。

    前者は課金(RUNPOD.md §7)、後者は preflight 検査7 の担当である。
    **空ファイルで埋めない** —— 中身の無い cost.txt があると「記録した」と
    見分けがつかなくなる。
    """
    target = artifacts.prepare_run_dir(config, explicit=tmp_path / "run", now=FIXED_TIME)
    artifacts.write_config_copy(target, SMOKE_CONFIG)
    artifacts.write_metrics(target, {})
    artifacts.write_log(target, ["x"])
    for name in NOT_WRITTEN_HERE:
        assert not (target / name).exists()
