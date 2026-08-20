"""translesion — 狭い FT の一貫性監査。

--------------------------------------------------------------------------
なぜこのファイルが標準ライブラリの再エクスポートをしているか
--------------------------------------------------------------------------
このパッケージ名 `code` は Python 標準ライブラリの `code` モジュールと同名である。
repo ルートが sys.path の先頭にあるとき、`import code` は標準ライブラリではなく
本パッケージに解決される。その結果 `pdb` が起動時に行う
`class _PdbInteractiveConsole(code.InteractiveConsole)` が

    AttributeError: module 'code' has no attribute 'InteractiveConsole'

で落ち、**pdb を import する pytest 全体が起動しなくなる**(2026-08-20 に実測)。

README.md のディレクトリ構造、infra/RUNPOD.md §4 の実行手順
(`python -m code.eval.run`)、Documents/03_OPEN_QUESTIONS.md の対応コード表が
すべて `code/...` を前提にしているため、ディレクトリ名は変更しない。
代わりに、標準ライブラリ `code.py` の公開名をここで再エクスポートして
両立させる(2026-08-20 の人間の判断。logs/DECISIONS.md ADR-013)。

この仕掛けが効いていることは code/tests/test_import_shim.py が検証し、
infra/preflight.py が本実行の前に毎回確認する。
"""

from __future__ import annotations

import importlib.util as _importlib_util
import os as _os
import sysconfig as _sysconfig
from types import ModuleType as _ModuleType


def _load_stdlib_code() -> _ModuleType:
    """標準ライブラリの code.py を、名前ではなくパスから読み込む。

    答える問い: 「本パッケージに影を作られた標準ライブラリ code をどう取り戻すか」

    通常の import は使えない。`code` という名前は既に本パッケージが占有しており、
    import すると自分自身に戻ってしまうため、ファイルパスから直接ロードする。
    sys.modules には登録しない(登録すると再び名前の衝突を招く)。
    """
    stdlib_dir = _sysconfig.get_paths()["stdlib"]
    stdlib_code_path = _os.path.join(stdlib_dir, "code.py")
    spec = _importlib_util.spec_from_file_location("_translesion_stdlib_code", stdlib_code_path)
    if spec is None or spec.loader is None:
        raise ImportError(
            f"標準ライブラリの code.py を {stdlib_code_path} に見つけられない。"
            "pdb / pytest が動かなくなる。infra/preflight.py の該当項目を参照。"
        )
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_stdlib_code = _load_stdlib_code()

# pdb が参照するのは InteractiveConsole だけだが、標準ライブラリ code の公開 API を
# 全て通しておく。一部だけ通すと、別のライブラリが別の名前を使ったときに再発する。
InteractiveInterpreter = _stdlib_code.InteractiveInterpreter
InteractiveConsole = _stdlib_code.InteractiveConsole
interact = _stdlib_code.interact
compile_command = _stdlib_code.compile_command

# 標準ライブラリ code の __all__ と本パッケージのサブモジュールの両方を通す。
__all__ = [
    "InteractiveInterpreter",
    "InteractiveConsole",
    "interact",
    "compile_command",
    "lesion",
]
