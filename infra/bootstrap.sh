#!/usr/bin/env bash
# ベアポッド → 実行可能状態。infra/RUNPOD.md §3。
#
# 答える問い: 「このポッドで実験を開始できる状態にするには何を入れればよいか」
#
# 使い方(ポッド上):
#   cd /workspace/translesion && bash infra/bootstrap.sh
#   python infra/preflight.py     # ← これが通るまで本実行しない
#
# 冪等に書くこと。ポッドは何度も作り直される。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== translesion bootstrap ==="
echo "repo: $REPO_ROOT"

# --- 1. Python 依存 ---
# requirements.lock があればそれを使う(再現性優先。infra/RUNPOD.md §6)。
# 無ければ pyproject の下限指定で入れ、**lock を作るよう促す**。
# **コメントと空行しかない lock は「空」として扱う。**`-s` はサイズしか見ないので、
# 説明文だけが入った lock を「復元できる」と誤判定し、--no-deps で何も入らないまま
# pytest に落ちる(2026-08-28 に順1b の準備で踏んだ)。
if grep -qvE '^[[:space:]]*(#|$)' infra/requirements.lock 2>/dev/null; then
    echo "--- requirements.lock から復元 ---"
    pip install --no-deps -r infra/requirements.lock
else
    echo "!!! infra/requirements.lock が空です。"
    echo "!!! この実行は再現性の保証がありません(infra/RUNPOD.md §6)。"
    echo "!!! 環境が固まったら次を実行して lock をコミットしてください:"
    echo "!!!   pip freeze > infra/requirements.lock"
    pip install -e ".[gpu,stats,dev]"
fi

# --- 2. 永続ボリュームへのリンク ---
# HuggingFace のキャッシュとモデル重みはコンテナではなくボリュームに置く。
# ポッドを作り直すたびに数十 GB を再ダウンロードしないため。
if [ -d /workspace ]; then
    export HF_HOME=/workspace/.cache/huggingface
    mkdir -p "$HF_HOME"
    echo "export HF_HOME=$HF_HOME" >> ~/.bashrc

    # runs/ の実体はボリュームに置き、repo からはリンクで見せる。
    # predictions/ が大きく、コンテナのディスクを食い潰すため(infra/RUNPOD.md §4)。
    mkdir -p /workspace/runs
    if [ ! -L runs ] && [ -d runs ]; then
        # 既存の runs/ が空でなければ触らない。壊すより止まる方がよい。
        if [ -z "$(ls -A runs | grep -v '^\.gitkeep$' || true)" ]; then
            rm -rf runs && ln -s /workspace/runs runs
            echo "runs/ → /workspace/runs にリンクしました"
        else
            echo "!!! runs/ に中身があるのでリンクしませんでした。手動で確認してください"
        fi
    fi
fi

# --- 3. git の安全設定 ---
# /workspace 配下の clone が dubious ownership で弾かれることがある。
git config --global --add safe.directory "$REPO_ROOT" || true

# --- 4. 動作確認 ---
echo "--- pytest ---"
python -m pytest code/tests -q

echo
echo "=== bootstrap 完了 ==="
echo "次: python infra/preflight.py --config configs/<実験>.yaml"
echo "preflight が通るまで本実行を開始しないこと(infra/RUNPOD.md §3)。"
