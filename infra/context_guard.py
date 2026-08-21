#!/usr/bin/env python3
"""セッションのコンテキスト使用量を実測し、閾値を超えたら引き継ぎを促す。

答える問い: 「このセッションは、もう次のセッションに渡すべきか?」

Claude Code の UserPromptSubmit hook として起動される。標準入力に hook の
JSON ペイロードを受け取り、そのセッションの transcript (JSONL) から
**直近のアシスタント応答が実際に消費した入力トークン数**を読む。
推測ではなく実測である (`CLAUDE.md` §7)。

閾値未満のときは何も出力しない (トークンを1つも消費しない)。
超えたときだけ、モデルへの指示 (additionalContext) と
ユーザーへの表示 (systemMessage) を JSON で返す。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

# 閾値 (トークン)。環境変数で上書きできる。
# WARN: 引き継ぎの準備を始めるべき水準。URGENT: 新しい作業を始めてはいけない水準。
DEFAULT_WARN_TOKENS = 100_000
DEFAULT_URGENT_TOKENS = 140_000

WARN_LEVEL = 1
URGENT_LEVEL = 2

# transcript の探索範囲。壊れた行や usage を持たない行を読み飛ばす上限。
MAX_SCANNED_LINES = 400

STATE_DIR_NAME = "claude_context_guard"


def read_payload() -> dict:
    """hook が標準入力に渡す JSON を読む。壊れていれば空 dict を返す。"""
    try:
        raw = sys.stdin.read()
    except OSError:
        return {}
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def sanitize_project_dir(cwd: str) -> str:
    """作業ディレクトリを Claude Code の transcript ディレクトリ名に変換する。

    例: プロジェクトの絶対パス -> C--Users-keenk-paper-FT
    """
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def locate_transcript(payload: dict) -> Path | None:
    """transcript の JSONL を突き止める。

    payload に transcript_path があればそれを使う。無い版の Claude Code でも
    動くよう、session_id と cwd からの再構成をフォールバックとして持つ。
    """
    direct = payload.get("transcript_path")
    if isinstance(direct, str) and direct:
        candidate = Path(direct)
        if candidate.is_file():
            return candidate

    session_id = payload.get("session_id")
    cwd = payload.get("cwd") or os.getcwd()
    if not isinstance(session_id, str) or not session_id:
        return None

    candidate = (
        Path.home()
        / ".claude"
        / "projects"
        / sanitize_project_dir(str(cwd))
        / f"{session_id}.jsonl"
    )
    return candidate if candidate.is_file() else None


def context_tokens_of(entry: dict) -> int | None:
    """1件の transcript エントリが報告する入力トークン総数を返す。

    キャッシュ読み出し分を含めた合計が、そのリクエストで実際にモデルへ
    送られたコンテキストの大きさである。usage を持たない行は None。
    """
    message = entry.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None

    total = 0
    for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            total += value
    return total or None


def latest_context_tokens(transcript: Path) -> int | None:
    """transcript の末尾から、最後に観測されたコンテキスト量を探す。"""
    try:
        lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    for line in reversed(lines[-MAX_SCANNED_LINES:]):
        if '"usage"' not in line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        tokens = context_tokens_of(entry)
        if tokens is not None:
            return tokens
    return None


def threshold(name: str, fallback: int) -> int:
    """環境変数による閾値の上書きを読む。不正な値は無視する。"""
    raw = os.environ.get(name)
    if raw is None:
        return fallback
    try:
        value = int(raw)
    except ValueError:
        return fallback
    return value if value > 0 else fallback


def level_for(tokens: int, warn: int, urgent: int) -> int:
    """トークン数を警告レベルに変換する。0 は警告なし。"""
    if tokens >= urgent:
        return URGENT_LEVEL
    if tokens >= warn:
        return WARN_LEVEL
    return 0


def state_path(session_id: str) -> Path:
    """セッションごとの「どのレベルまで警告済みか」を置く場所。

    repo を汚さないよう一時ディレクトリに置く。消えても実害はない
    (次のプロンプトで再び警告が出るだけ)。
    """
    return Path(tempfile.gettempdir()) / STATE_DIR_NAME / f"{session_id}.level"


def already_warned_at(session_id: str, level: int) -> bool:
    """同じレベルの警告を既に出したか。URGENT は毎回出すので対象外。"""
    if level >= URGENT_LEVEL:
        return False
    try:
        return int(state_path(session_id).read_text(encoding="utf-8").strip()) >= level
    except (OSError, ValueError):
        return False


def record_warning(session_id: str, level: int) -> None:
    """警告済みレベルを記録する。書けなくても処理は続ける。"""
    path = state_path(session_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(level), encoding="utf-8")
    except OSError:
        pass


def messages_for(level: int, tokens: int, limit: int) -> tuple[str, str]:
    """モデルへの指示とユーザーへの表示を組み立てる。"""
    kilo = tokens // 1000
    if level >= URGENT_LEVEL:
        to_model = (
            f"[context-guard] コンテキストが約 {kilo}k トークン (閾値 {limit // 1000}k)。"
            "新しい作業を始めてはいけない。いま skill `handoff` を実行し、"
            "STATE.md と logs/HANDOFF.md を更新して、ユーザーに /clear を促すこと。"
        )
        to_user = f"コンテキスト約 {kilo}k トークン。ここで打ち切って引き継ぐべき水準。"
    else:
        to_model = (
            f"[context-guard] コンテキストが約 {kilo}k トークン (閾値 {limit // 1000}k)。"
            "いまの作業が一区切りついたら skill `handoff` を実行し、"
            "次セッション用のプロンプトを作ってユーザーに /clear を促すこと。"
        )
        to_user = f"コンテキスト約 {kilo}k トークン。そろそろ /handoff → /clear の頃合い。"
    return to_model, to_user


def main() -> int:
    payload = read_payload()
    transcript = locate_transcript(payload)
    if transcript is None:
        return 0

    tokens = latest_context_tokens(transcript)
    if tokens is None:
        return 0

    warn = threshold("CONTEXT_GUARD_WARN", DEFAULT_WARN_TOKENS)
    urgent = threshold("CONTEXT_GUARD_URGENT", DEFAULT_URGENT_TOKENS)
    level = level_for(tokens, warn, urgent)
    if level == 0:
        return 0

    session_id = str(payload.get("session_id", "unknown"))
    if already_warned_at(session_id, level):
        return 0

    limit = urgent if level >= URGENT_LEVEL else warn
    to_model, to_user = messages_for(level, tokens, limit)
    record_warning(session_id, level)

    json.dump(
        {
            "systemMessage": to_user,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": to_model,
            },
        },
        sys.stdout,
        # ASCII に限定する。Windows の stdout は既定が UTF-8 とは限らず、
        # 日本語をそのまま流すと受け側に壊れたバイト列が渡りうる。
        ensure_ascii=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
