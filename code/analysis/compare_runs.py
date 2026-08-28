"""2つの run の応答を項目ごとに突き合わせる(PLAN-004 §3 順1b の前提2 の (e))。

答える問い: 「同じ項目・同じ生成設定で、**まとめ幅だけを変えた**とき、モデルは
同じ文字列を返すか」

  python -m code.analysis.compare_runs \
      --run-a runs/20260828_120000_smoke1b \
      --run-b runs/20260828_121000_smoke1b_b1

**これは承認待ち #25 の材料である。**decoder-only の一括生成は左パディングを
要求し、同じプロンプトでもバッチの構成によって最終トークンが割れうる(貪欲デ
コードの同点)。割れるなら `eval.batch_size` は速度の都合ではなく**実験装置の
設定**であり、条件間で揃えなければならない(`infra/RUNPOD.md` §6)。

**合否基準を持たない。**一致した件数と、食い違った項目の中身を出すだけである。
「何件までなら一致とみなすか」は人間が決める(#25 の3つめ)。エージェントが
ここに閾値を置くと、それが決定になってしまう(skill `code-style` §5)。

**採点し直さない**(skill `code-style` §2)。`classification` は各 run の
`predictions/*.jsonl` に書かれた値をそのまま並べる。

**比べてよいのは「まとめ幅だけが違う2つの run」である。**モデル・revision・
温度・上限のどれかが違えば応答が違うのは当たり前であり、その比較は #25 の材料
にならない。**生成設定の差は必ず出力に並べる**(`generation_diff`)。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

METRICS_FILENAME = "metrics.json"
PREDICTIONS_DIR = "predictions"

COMPARISON_KIND = "run_comparison"

# 突き合わせの鍵。**項目 id だけでは足りない** —— 同じ項目が別の採点バッチに
# 現れうる(順1b は T1 と T2 に同じ8組を渡している)。
KEY_FIELDS = ("batch", "item_id")

NO_VERDICT_NOTE = (
    "**このファイルに合否は無い。**まとめ幅を変えたときに応答が割れるかどうかの"
    "観測であって、「何件までなら同じとみなすか」は人間が決める(承認待ち #25)。"
)

MISMATCH_WARNING = (
    "**応答が食い違った項目が {count} 件ある。**まとめ幅は数値を動かしている。"
    "この run の4値分解を出す前に人間に上げること(logs/HANDOFF.md)。"
)

KEYSET_ERROR = (
    "2つの run が同じ項目集合を採点していない(A のみ {only_a} 件 / B のみ {only_b} 件)。"
    "まとめ幅以外が違う config を比べている可能性がある。"
)


class ComparisonError(ValueError):
    """突き合わせられない2つの run を渡された。"""


@dataclass(frozen=True)
class Prediction:
    """1件の応答と、その分類。"""

    batch: str
    item_id: str
    prompt: str
    response: str
    classification: str


def read_predictions(run_dir: Path) -> dict[tuple[str, str], Prediction]:
    """`predictions/*.jsonl` を鍵 (採点バッチ, 項目 id) で引ける形に読む。

    答える問い: 「この run は、この項目に何と答え、それをどう分類したか」

    同じ鍵が2度出たら止める。黙って後勝ちにすると、突き合わせた件数だけが合って
    中身が別物になる。
    """
    directory = run_dir / PREDICTIONS_DIR
    if not directory.is_dir():
        raise ComparisonError(f"{directory} が無い。生成の前に落ちた run である可能性がある")
    records: dict[tuple[str, str], Prediction] = {}
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            key = (path.stem, record["item_id"])
            if key in records:
                raise ComparisonError(f"{run_dir} に同じ鍵 {key} の応答が2件ある")
            records[key] = Prediction(
                batch=path.stem,
                item_id=record["item_id"],
                prompt=record["prompt"],
                response=record["response"],
                classification=record["classification"],
            )
    if not records:
        raise ComparisonError(f"{directory} に応答が1件も無い")
    return records


def read_generation(run_dir: Path) -> dict[str, Any]:
    """run の生成設定。**何が違う2つを比べているのかを出力に残すため。**"""
    path = run_dir / METRICS_FILENAME
    if not path.is_file():
        raise ComparisonError(f"{path} が無い。本実行の成果物ではない run を指している")
    return json.loads(path.read_text(encoding="utf-8")).get("generation", {})


def generation_diff(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    """2つの生成設定で値が違う鍵だけを並べる。

    答える問い: 「この2つの run は、まとめ幅**だけ**が違うのか」

    ここに `batch_size` 以外が出たら、その比較は #25 の材料にならない。
    **止めはしない** —— 何を比べたのかが記録に残っていれば、後から読む人が
    判断できる。判断そのものは人間の仕事である(`CLAUDE.md` §8)。
    """
    return {
        key: {"a": a.get(key), "b": b.get(key)}
        for key in sorted(set(a) | set(b))
        if a.get(key) != b.get(key)
    }


def compare(
    a: Mapping[tuple[str, str], Prediction], b: Mapping[tuple[str, str], Prediction]
) -> dict[str, Any]:
    """項目ごとに応答を突き合わせる。

    答える問い: 「同じ項目に対して、2つの run は同じ文字列を返したか」

    比べるのは**生成文字列そのもの**である。分類だけを比べると、違う文字列が
    同じカテゴリに落ちたときに「一致した」と読めてしまう —— まとめ幅が生成を
    動かしているかどうかを見たいので、それでは弱い。
    """
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    if only_a or only_b:
        raise ComparisonError(KEYSET_ERROR.format(only_a=len(only_a), only_b=len(only_b)))

    mismatches: list[dict[str, Any]] = []
    for key in sorted(a):
        left, right = a[key], b[key]
        if left.response == right.response:
            continue
        mismatches.append(
            {
                "batch": left.batch,
                "item_id": left.item_id,
                "prompt": left.prompt,
                "response_a": left.response,
                "response_b": right.response,
                "classification_a": left.classification,
                "classification_b": right.classification,
            }
        )
    return {
        "n_items": len(a),
        "n_identical": len(a) - len(mismatches),
        "n_mismatched": len(mismatches),
        "n_classification_changed": sum(
            1 for item in mismatches if item["classification_a"] != item["classification_b"]
        ),
        "mismatches": mismatches,
    }


def payload(run_a: Path, run_b: Path) -> dict[str, Any]:
    """突き合わせの結果を組む。**どの2つを比べたかを必ず残す。**"""
    result = compare(read_predictions(run_a), read_predictions(run_b))
    return {
        "kind": COMPARISON_KIND,
        "run_a": str(run_a),
        "run_b": str(run_b),
        "generation_diff": generation_diff(read_generation(run_a), read_generation(run_b)),
        "verdict_note": NO_VERDICT_NOTE,
        **result,
    }


def report_lines(document: Mapping[str, Any]) -> list[str]:
    """標準出力に出す行。**食い違いがあれば必ず警告を1行出す。**"""
    lines = [
        f"A: {document['run_a']}",
        f"B: {document['run_b']}",
        f"生成設定の差: {json.dumps(document['generation_diff'], ensure_ascii=False)}",
        f"項目 {document['n_items']} 件 / 一致 {document['n_identical']} 件 / "
        f"食い違い {document['n_mismatched']} 件 "
        f"(うち分類まで変わった {document['n_classification_changed']} 件)",
        f"注意: {document['verdict_note']}",
    ]
    if document["n_mismatched"]:
        lines.append(MISMATCH_WARNING.format(count=document["n_mismatched"]))
        for item in document["mismatches"]:
            lines.append(f"  [{item['batch']}] {item['item_id']}")
            lines.append(f"    A: {item['response_a']!r} -> {item['classification_a']}")
            lines.append(f"    B: {item['response_b']!r} -> {item['classification_b']}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="2つの run の応答を突き合わせる")
    parser.add_argument("--run-a", required=True, type=Path)
    parser.add_argument("--run-b", required=True, type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="書き出し先。省略すると標準出力だけで、ファイルは作らない",
    )
    args = parser.parse_args(argv)

    document = payload(args.run_a, args.run_b)
    for line in report_lines(document):
        print(line)
    if args.out is not None:
        args.out.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"書き出し: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
