"""manifest のハッシュを取るための正準化。

答える問い: 「同じ内容なら必ず同じハッシュになる畳み方はどれか」

なぜ独立したモジュールか: 訓練データの manifest(code/data_gen/ft_data.py)と
評価アンカーの書式ブロック(code/data_gen/prompt_format.py)が**同じ畳み方**を
しなければ、infra/preflight.py の検査6 は「訓練と評価で書式が違う」と報告する。
そのとき違うのは書式ではなく畳み方である —— **検査が嘘をつく。**
畳み方は1箇所にしか置かない。

code/data_gen/pool.py の pairs_hash はここを使っていない。順序対の列は
辞書を含まないので canonical_json と同じ文字列になるはずだが、**既存の
ハッシュ値を動かさない**ことを優先して手を入れていない(値が変われば、
preflight が照合する記録がすべて無効になる)。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def canonical_json(payload: Any) -> str:
    """ハッシュを取るための正準 JSON。キー順を固定し空白を詰める。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    """UTF-8 に符号化してから畳む。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """**書き終えたファイルを読み直して**畳む。

    答える問い: 「いま生成したデータは、manifest に記録した内容と同一か」

    `sha256_text` と分けてあるのは、こちらが**ディスク上のバイト列**を数えるからである。
    メモリ上の文字列を数えた値を manifest に書くと、書き出しで改行コードや符号化が
    変わったときに気づけない —— **manifest が「書いたつもりの内容」を保証してしまう。**
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files_block(out_dir: Path, names: Sequence[str]) -> dict[str, str]:
    """manifest の `files` ブロックを組む(infra/preflight.py の data manifest 検査)。

    答える問い: 「この manifest の隣にあるべきファイルは何で、その中身は何か」

    **鍵は manifest からの相対パスである。**preflight は
    `manifest_path.parent / <鍵>` を開いて照合する。訓練側(train.jsonl)と
    評価側(items.jsonl)で鍵の作り方が違うと、検査が片方でしか成立しない。
    """
    return {name: sha256_file(out_dir / name) for name in names}
