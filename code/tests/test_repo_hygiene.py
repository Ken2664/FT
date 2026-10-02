"""引き継ぎ装置が読める大きさに保たれていること(ADR-063)。

答える問い: 「`CLAUDE.md` §1 の `cat STATE.md` が、いま実際に実行できるか」

`STATE.md` は 2026-09-08 までに 417 KB / 3,939 行まで育ち、`CLAUDE.md` §10 が
全文読解を禁じる大きさになった。**引き継ぎ装置が引き継げなくなっていた。**
原因は「各節が過去のセッション記録を消さずに上へ積んだこと」である。

このファイルの役割は、同じことがもう一度起きたときに落ちることである。
**落ちたら中身を削るのではなく、古いブロックを `logs/STATE-ARCHIVE.md` へ移す**
(`STATE.md`「このファイルの運用規約」)。
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# ADR-063 が決めた上限。根拠は「セッション開始時に毎回 cat して読み通せること」であり、
# 統計的な意味は無い。分割直後の実測は 449 行 / 44 KB である。
STATE_MAX_LINES = 700
STATE_MAX_BYTES = 90_000


def _read(relative_path: str) -> bytes:
    return (REPO_ROOT / relative_path).read_bytes()


def test_state_md_stays_readable_in_one_sitting() -> None:
    """`STATE.md` が `cat` できる大きさに収まっていること。"""
    raw = _read("STATE.md")
    n_lines = raw.count(b"\n")
    assert n_lines <= STATE_MAX_LINES, (
        f"STATE.md が {n_lines} 行に育っている(上限 {STATE_MAX_LINES})。"
        "古いブロックを logs/STATE-ARCHIVE.md へ移すこと。中身を削ってはならない。"
    )
    assert len(raw) <= STATE_MAX_BYTES, (
        f"STATE.md が {len(raw)} バイトに育っている(上限 {STATE_MAX_BYTES})。"
        "古いブロックを logs/STATE-ARCHIVE.md へ移すこと。中身を削ってはならない。"
    )


# LF だけであるべき .md(`.gitattributes` の `*.md text eol=lf`)。
# 当初は引き継ぎ文書の 3 本だけが対象で、2026-10-02(その132)に logs/CHANGELOG.md へ
# 混ざった CR 1 バイトを捕まえられなかった。PLAN-038 で記録文書と設計文書へ広げた。
LF_ONLY_FILES = (
    "STATE.md",
    "logs/STATE-ARCHIVE.md",
    "logs/OPEN-ITEMS.md",
    "logs/CHANGELOG.md",
    "logs/DECISIONS.md",
    "logs/HANDOFF.md",
    "CLAUDE.md",
    "AGENTS.md",
)
LF_ONLY_GLOBS = ("Documents/*.md", "plans/*.md")


def _lf_only_paths() -> list[str]:
    """LF の検査の対象を、1 本ずつの指定と glob の展開を合わせて返す。"""
    globbed = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for pattern in LF_ONLY_GLOBS
        for path in REPO_ROOT.glob(pattern)
    )
    return [*LF_ONLY_FILES, *globbed]


@pytest.mark.parametrize("relative_path", _lf_only_paths())
def test_markdown_documents_use_lf_only(relative_path: str) -> None:
    """引き継ぎ・記録・設計の文書に CR が混ざっていないこと(`.gitattributes` の `*.md text eol=lf`)。"""
    n_cr = _read(relative_path).count(b"\r")
    assert n_cr == 0, f"{relative_path} に CR が {n_cr} バイト混ざっている"


@pytest.mark.parametrize("pattern", LF_ONLY_GLOBS)
def test_lf_only_globs_match_files(pattern: str) -> None:
    """glob が 1 本以上に当たること。書き間違いで LF の検査が空になるのを防ぐ。"""
    assert any(REPO_ROOT.glob(pattern)), f"{pattern} に当たる .md が無い(LF の検査が空になる)"


@pytest.mark.parametrize(
    "relative_path",
    ["logs/STATE-ARCHIVE.md", "logs/OPEN-ITEMS.md"],
)
def test_split_out_documents_exist(relative_path: str) -> None:
    """分割先の 2 ファイルが存在すること。`STATE.md` はこれらを指している。"""
    assert (REPO_ROOT / relative_path).is_file(), f"{relative_path} が無い(ADR-063)"


def test_state_md_points_at_both_split_targets() -> None:
    """`STATE.md` が分割先への道案内を持っていること。

    道案内が消えると、移した内容が「存在しない」ものになる
    (`STATE.md` 冒頭の規約)。
    """
    text = _read("STATE.md").decode("utf-8")
    for target in ("logs/STATE-ARCHIVE.md", "logs/OPEN-ITEMS.md"):
        assert target in text, f"STATE.md が {target} を指していない"
