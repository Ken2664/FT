"""`code` パッケージが標準ライブラリ `code` を壊していないことを検証する。

答える問い: 「本 repo をインポートした状態で pdb / pytest は動くか」

背景は code/__init__.py の冒頭と logs/DECISIONS.md ADR-013。
このテストが落ちたら pytest 自体が起動しなくなるので、
**落ちたことにすら気づけない可能性がある**。infra/preflight.py が
同じ検査を独立に行うのはそのため。
"""

from __future__ import annotations

import importlib
import sys


def test_package_exposes_stdlib_code_api() -> None:
    """標準ライブラリ code の公開名が本パッケージ経由で引けること。"""
    import code as shadowed

    for name in ("InteractiveInterpreter", "InteractiveConsole", "interact", "compile_command"):
        assert hasattr(shadowed, name), f"標準ライブラリ code の {name} が失われている"


def test_pdb_still_imports() -> None:
    """pdb が import できること。これが本命。

    pdb はモジュール定義時に code.InteractiveConsole を継承する。
    再エクスポートが欠けると import 時点で AttributeError になる。
    """
    if "pdb" in sys.modules:
        del sys.modules["pdb"]
    pdb = importlib.import_module("pdb")
    assert hasattr(pdb, "Pdb")


def test_repo_submodules_are_still_reachable() -> None:
    """再エクスポートを入れても、本 repo のサブモジュールが引けること。"""
    from code.lesion import AdditiveLesion

    assert AdditiveLesion(offset=2).apply(3, 4) == 9


def test_shim_does_not_register_a_second_code_module() -> None:
    """標準ライブラリ code を sys.modules に別名で常駐させていないこと。

    sys.modules に二重登録すると、どちらが使われるかが import 順に依存して
    再現性が壊れる(CLAUDE.md §2「再現性の破壊」)。
    """
    assert "_translesion_stdlib_code" not in sys.modules
