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

**2つの一致を独立したブロックで出す**(ADR-045 決定3):

  1. 生成文字列そのものの一致(`compare`)—— まとめ幅が生成を動かしたか
  2. 抽出された整数値の一致(`compare_parsed`)—— まとめ幅が **4値分解に入る数**
     を動かしたか

分類が一致していても抽出値が割れることがある(生成文字列末尾の差が分類に
響かなかった場合)ので、どちらが割れたのかを分けて数える。両方 parse_fail
(`parsed` が None 対 None)は 2 の比較対象外とし、別に数える —— parse_fail
どうしは 1 の分類でもう捕まっている(ADR-045 リスク欄)。**どちらのブロックにも
合否は無い**(ADR-045 決定2)。
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

# `predictions/*.jsonl` の `parsed`。数値項目は int、二値項目(T3 / T1b)は bool、
# 抽出失敗は None(= parse_fail)。出所は code/eval/run.py の prediction_record。
# (`code/eval/scoring.py` の `Answer` と同じ形。あちらを import すると
#  analysis → eval の依存ができるので、ここで別に持つ。)
ParsedValue = int | bool

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

PARSED_CONSISTENCY_NOTE = (
    "**このブロックにも合否は無い**(ADR-045 決定2)。抽出された整数値が項目ごとに"
    "一致したかを数えるだけである。両方 parse_fail(None 対 None)は比較対象外として"
    "別に数える —— parse_fail どうしは4値分類のブロックで既に捕まる(ADR-045 リスク欄)。"
)

PARSED_MISMATCH_WARNING = (
    "**抽出された整数値が食い違った項目が {count} 件ある。**まとめ幅が4値分解に入る数を"
    "動かしている。この run の4値分解を出す前に人間に上げること(ADR-040 決定3)。"
)


class ComparisonError(ValueError):
    """突き合わせられない2つの run を渡された。"""


@dataclass(frozen=True)
class Prediction:
    """1件の応答と、そこから抽出された整数値、その分類。"""

    batch: str
    item_id: str
    prompt: str
    response: str
    parsed: ParsedValue | None
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
                parsed=record["parsed"],
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


def _paired_keys(
    a: Mapping[tuple[str, str], Prediction], b: Mapping[tuple[str, str], Prediction]
) -> list[tuple[str, str]]:
    """2つの run が同じ項目集合を採点していることを確かめ、鍵を昇順で返す。

    答える問い: 「この2つは同じ項目を突き合わせているのか」

    片方にしか無い項目があれば止める。まとめ幅以外が違う config を比べている
    可能性があり、黙って共通部分だけ突き合わせると項目数が静かに減る。
    """
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    if only_a or only_b:
        raise ComparisonError(KEYSET_ERROR.format(only_a=len(only_a), only_b=len(only_b)))
    return sorted(a)


def _parsed_equal(a: ParsedValue | None, b: ParsedValue | None) -> bool:
    """2つの抽出値が同じか。**bool と int を取り違えない。**

    答える問い: 「この2つの run は、この項目から同じ数を取り出したか」

    `True == 1` が成立するので、二値項目の Yes(bool)と数値項目の 1(int)が
    紛れると偽の一致になる。同じ電池の2 run なら型は揃うはずだが、
    `code/eval/scoring.py` の classify と同じ理由でここでも型を見る。
    片方だけ None(= parse_fail)なら不一致(両方 None は呼び出し側で先に除く)。
    """
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


def compare(
    a: Mapping[tuple[str, str], Prediction], b: Mapping[tuple[str, str], Prediction]
) -> dict[str, Any]:
    """項目ごとに応答を突き合わせる。

    答える問い: 「同じ項目に対して、2つの run は同じ文字列を返したか」

    比べるのは**生成文字列そのもの**である。分類だけを比べると、違う文字列が
    同じカテゴリに落ちたときに「一致した」と読めてしまう —— まとめ幅が生成を
    動かしているかどうかを見たいので、それでは弱い。抽出された整数値の一致は
    `compare_parsed` が別に見る(ADR-045 決定3)。
    """
    mismatches: list[dict[str, Any]] = []
    for key in _paired_keys(a, b):
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


def compare_parsed(
    a: Mapping[tuple[str, str], Prediction], b: Mapping[tuple[str, str], Prediction]
) -> dict[str, Any]:
    """項目ごとに**抽出された整数値**を突き合わせる(ADR-045)。

    答える問い: 「同じ項目に対して、2つの run は同じ整数を抽出したか」

    これは `compare` の生成文字列の一致とは独立に見る(ADR-045 決定3)。
    分類が一致していても抽出値が割れることがあり(生成文字列末尾の差が分類に
    響かなかった場合)、逆もありうる。どちらが割れたのかを分けて出さないと、
    不合格時の降り方(ADR-040 決定3)を選べない。

    **採点し直さない**(skill code-style §2)。`parsed` は各 run の
    `predictions/*.jsonl` に書かれた値をそのまま並べる。

    **両方 parse_fail(`parsed` が None 対 None)は比較対象外**として別に数える。
    parse_fail どうしは4値分類のブロックで既に捕まる(ADR-045 リスク欄)。
    """
    by_item: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    both_parse_fail: list[dict[str, str]] = []
    for key in _paired_keys(a, b):
        left, right = a[key], b[key]
        if left.parsed is None and right.parsed is None:
            both_parse_fail.append({"batch": left.batch, "item_id": left.item_id})
            continue
        match = _parsed_equal(left.parsed, right.parsed)
        by_item.append(
            {
                "batch": left.batch,
                "item_id": left.item_id,
                "parsed_a": left.parsed,
                "parsed_b": right.parsed,
                "parsed_match": match,
            }
        )
        if not match:
            mismatches.append(
                {
                    "batch": left.batch,
                    "item_id": left.item_id,
                    "parsed_a": left.parsed,
                    "parsed_b": right.parsed,
                    "classification_a": left.classification,
                    "classification_b": right.classification,
                }
            )
    return {
        "n_compared": len(by_item),
        "n_match": len(by_item) - len(mismatches),
        "n_mismatch": len(mismatches),
        "n_both_parse_fail": len(both_parse_fail),
        "by_item": by_item,
        "mismatches": mismatches,
        "both_parse_fail": both_parse_fail,
        "note": PARSED_CONSISTENCY_NOTE,
    }


def payload(run_a: Path, run_b: Path) -> dict[str, Any]:
    """突き合わせの結果を組む。**どの2つを比べたかを必ず残す。**"""
    a, b = read_predictions(run_a), read_predictions(run_b)
    return {
        "kind": COMPARISON_KIND,
        "run_a": str(run_a),
        "run_b": str(run_b),
        "generation_diff": generation_diff(read_generation(run_a), read_generation(run_b)),
        "verdict_note": NO_VERDICT_NOTE,
        **compare(a, b),
        "parsed_consistency": compare_parsed(a, b),
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

    parsed = document["parsed_consistency"]
    lines.append(
        f"抽出整数値: 比較 {parsed['n_compared']} 件 / 一致 {parsed['n_match']} 件 / "
        f"食い違い {parsed['n_mismatch']} 件 / "
        f"両方 parse_fail {parsed['n_both_parse_fail']} 件(比較対象外)"
    )
    if parsed["n_mismatch"]:
        lines.append(PARSED_MISMATCH_WARNING.format(count=parsed["n_mismatch"]))
        for item in parsed["mismatches"]:
            lines.append(
                f"  [{item['batch']}] {item['item_id']}: "
                f"A={item['parsed_a']!r} ({item['classification_a']}) / "
                f"B={item['parsed_b']!r} ({item['classification_b']})"
            )
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
