"""応答のトークン長の分布(PLAN-004 §3 順1b の完了条件4 / 前提2 の (d))。

答える問い: 「答えは何トークンに収まるか。`max_new_tokens` をいくつにすれば、
上限で切られたせいの `parse_fail` が出ないか」

  python -m code.analysis.token_length --run-dir runs/20260828_120000_smoke1b

**生成経路を触らない。**`runs/<id>/predictions/*.jsonl` に残った生成文字列を、
同じトークナイザで**引き直して**数えるだけである。数え直しなので何度でもやり直
せるし、GPU も重みも要らない(トークナイザだけ読む)。

**この数え方には偏りが2つある。どちらも下振れの向きである。**

  1. `response` は `skip_special_tokens=True` で復号されている
     (`code/eval/generate.py`)。**EOS は入っていない。**したがって実際に生成
     されたトークン数より **1 ほど少なく出る**
  2. 復号 → 再符号化が元のトークン列に戻る保証は無い

**上限に達した応答は `n_at_cap` として別に数える。**そこは右側で打ち切られており
(censored)、**その長さを `max_new_tokens` の根拠にしてはならない** ——
「128 で足りた」ではなく「128 では足りなかった」の記録だからである。

**パーセンタイルを出さない。**順1b の n は群あたり 8 と 11 である。その n で
p90 / p95 を書くと、無い精度があるように見える。**並べ替えた全長をそのまま残す**
ので、必要なら後から何でも計算できる。

**強制選択で採ったバッチ(二値群 comparison。ADR-047)は数えない。**そこには
生成文が無く、`predictions/*.jsonl` の `response` に入っているのは
`"Yes [forced_choice yes_logp=... no_logp=...]"` という**合成した診断文字列**
である(`code/eval/run.py` の `forced_choice_response_text`)。それを数えると
「答えのトークン長」ではなく合成文字列の長さの表になり、しかもこの表は #20
`max_new_tokens` の改訂根拠である(ADR-042 決定6 / ADR-038)。**黙って落とさず、
`skipped: true` として残す** —— 「答えのトークン長」が強制選択では定義されない、
と読める形にする。

**採点方式は `metrics.json` の `by_batch[*].scoring` から引く**(ADR-047 決定6)。
このキーを持たない run(強制選択の実装より前のもの。`runs/20260828_*_smoke1b`)は
自由生成として従来どおり数える。

**`results/` には書かない**(ADR-037 決定6)。書き出し先は `runs/<id>/` である。
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

METRICS_FILENAME = "metrics.json"
PREDICTIONS_DIR = "predictions"
OUTPUT_FILENAME = "token_length.json"

# この出力の種別。`code/analysis/aggregate.py` が metrics.json を種別でより分けて
# いるのと同じ理由で、4値分解の表と混ざらないようにする。
TOKEN_LENGTH_KIND = "token_length"

MEASUREMENT_NOTE = (
    "predictions/*.jsonl の response を同じトークナイザで引き直した数である。"
    "response は skip_special_tokens=True で復号されているので EOS を含まず、"
    "実際に生成されたトークン数より1ほど少なく出る。"
    "復号→再符号化が元の列に戻る保証も無い。**下振れの向きの推定である。**"
)

CAP_WARNING = (
    "上限に達した応答が {count} 件ある(max_new_tokens={cap})。"
    "**この群の分布は右側で打ち切られている。**"
    "打ち切られた長さを max_new_tokens の根拠に使わないこと。"
)

NO_PERCENTILE_NOTE = "n が小さいのでパーセンタイルは出さない。lengths に並べ替えた全長がある。"

# 強制選択の名札。**出所は `code/eval/run.py` の `SCORING_FORCED_CHOICE`** だが、
# ここで import すると analysis -> eval の依存ができる(`compare_runs.py` の
# `ParsedValue` と同じ理由)。値が食い違ったら `test_token_length.py` が捕まえる。
SCORING_FORCED_CHOICE = "forced_choice"

FORCED_CHOICE_SKIP_NOTE = (
    "このバッチは強制選択で採られている(ADR-047)。生成文が無く、response に入って"
    "いるのは選んだ答えと両側の対数尤度を並べた合成文字列なので、**答えのトークン長は"
    "定義されない。**数えると max_new_tokens の根拠(#20)が汚れるため集計から外した。"
)


class TokenLengthError(ValueError):
    """run が読めない、または応答が1件も無い。"""


# 文字列 → トークン ID 列。テストは重みもトークナイザも要らない関数を渡す。
Encoder = Callable[[str], Sequence[int]]


@dataclass(frozen=True)
class Response:
    """1件の応答と、それがどの採点バッチのどの項目から来たか。"""

    batch: str
    group: str
    item_id: str
    text: str


def read_metrics(run_dir: Path) -> dict[str, Any]:
    """run の metrics.json を読む。**トークナイザの出所はここにしかない。**

    答える問い: 「この応答は、どのモデルの、どの revision の、どの上限のもとで
    生成されたか」

    config.yaml ではなく metrics.json を読むのは、**実際に使われた生成設定が
    書いてあるのがこちら**だからである(`code/eval/run.py` の `metrics_payload`)。
    """
    path = run_dir / METRICS_FILENAME
    if not path.is_file():
        raise TokenLengthError(f"{path} が無い。本実行の成果物ではない run を指している")
    return json.loads(path.read_text(encoding="utf-8"))


def read_responses(run_dir: Path) -> list[Response]:
    """`predictions/*.jsonl` を1行1応答で読む。

    答える問い: 「この run は、どの項目に何と答えたか」

    ファイル名が採点バッチ名である(`code/artifacts.py` の `write_predictions`)。
    """
    directory = run_dir / PREDICTIONS_DIR
    if not directory.is_dir():
        raise TokenLengthError(f"{directory} が無い。生成の前に落ちた run である可能性がある")
    responses: list[Response] = []
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            responses.append(
                Response(
                    batch=path.stem,
                    group=record["group"],
                    item_id=record["item_id"],
                    text=record["response"],
                )
            )
    if not responses:
        raise TokenLengthError(f"{directory} に応答が1件も無い")
    return responses


def count_tokens(text: str, *, encode: Encoder) -> int:
    """1件の応答が何トークンか。

    答える問い: 「この文字列は、このトークナイザで何トークンになるか」

    **特殊トークンを足さない。**ここで数えたいのは「モデルが続きとして書いた分」
    であって、プロンプト側の BOS や chat_template の飾りではない。
    """
    return len(encode(text))


def summarize(lengths: Sequence[int], *, cap: int | None) -> dict[str, Any]:
    """1群の長さを要約する。**並べ替えた全長を必ず残す。**

    答える問い: 「この群の答えは何トークンに収まったか。上限で切られたものが
    何件あるか」

    `n_at_cap` を分けて数えるのは、上限に達した応答が**長さの観測ではなく
    打ち切りの観測**だからである(モジュール docstring)。
    """
    ordered = sorted(lengths)
    # cap が無い run(上限が記録されていない)で 0 件と書くと「切られなかった」
    # ように読める。数えられないことは None のまま残す。
    at_cap = None if cap is None else sum(1 for length in ordered if length >= cap)
    return {
        "n_items": len(ordered),
        "lengths": ordered,
        "min": ordered[0],
        "max": ordered[-1],
        "median": statistics.median(ordered),
        "mean": statistics.fmean(ordered),
        "n_at_cap": at_cap,
        "note": NO_PERCENTILE_NOTE,
    }


def by_batch(
    responses: Iterable[Response],
    *,
    encode: Encoder,
    cap: int | None,
    scoring: Mapping[str, str | None] | None = None,
) -> dict[str, Any]:
    """採点バッチごとの要約。群名も一緒に残す(T1 / T2 の区別はここで付く)。

    答える問い: 「このバッチの答えは何トークンに収まったか。そもそも
    『答えのトークン長』が定義される採点方式か」

    `scoring` は バッチ名 -> 採点方式(`metrics.json` の `by_batch[*].scoring`)。
    **強制選択のバッチは数えず `skipped: true` を残す**(モジュール docstring)。
    キーが無いバッチ(旧 run)は自由生成として従来どおり数える。
    """
    by_name = dict(scoring or {})
    grouped: dict[str, list[Response]] = {}
    for response in responses:
        grouped.setdefault(response.batch, []).append(response)
    summaries: dict[str, Any] = {}
    for name, items in grouped.items():
        method = by_name.get(name)
        if method == SCORING_FORCED_CHOICE:
            summaries[name] = {
                "group": items[0].group,
                "scoring": method,
                "skipped": True,
                "n_items": len(items),
                "note": FORCED_CHOICE_SKIP_NOTE,
            }
            continue
        lengths = [count_tokens(item.text, encode=encode) for item in items]
        summary = summarize(lengths, cap=cap)
        summary["group"] = items[0].group
        summary["scoring"] = method
        summary["skipped"] = False
        summaries[name] = summary
    return summaries


def scoring_by_batch(metrics: Mapping[str, Any]) -> dict[str, str | None]:
    """バッチ名 -> 採点方式。**キーが無い run は None(= 記録が無い)。**

    答える問い: 「このバッチはどちらの採点方式で採られたか」

    None を `free_generation` に読み替えないのは、強制選択の実装より前の run
    (`runs/20260828_*_smoke1b`)で「自由生成だったと記録されている」のと
    「記録が無い」の区別を消さないためである。数え方は同じ(従来どおり数える)。
    """
    return {
        str(name): batch.get("scoring")
        for name, batch in (metrics.get("by_batch") or {}).items()
    }


def payload(
    metrics: Mapping[str, Any], responses: Sequence[Response], *, encode: Encoder
) -> dict[str, Any]:
    """`token_length.json` の中身を組む。

    答える問い: 「この分布が、どの run の、どのトークナイザの、どの上限のもとで
    出たかを、この1ファイルだけで言えるか」
    """
    generation = metrics.get("generation", {})
    cap = generation.get("max_new_tokens")
    return {
        "run_id": metrics.get("run_id"),
        "kind": TOKEN_LENGTH_KIND,
        "source_kind": metrics.get("kind"),
        "tokenizer": {
            "model_name": generation.get("model_name"),
            "revision": generation.get("revision"),
        },
        "max_new_tokens": cap,
        "measurement_note": MEASUREMENT_NOTE,
        "by_batch": by_batch(
            responses, encode=encode, cap=cap, scoring=scoring_by_batch(metrics)
        ),
    }


def report_lines(document: Mapping[str, Any]) -> list[str]:
    """標準出力に出す行。**打ち切りがあれば必ず1行出す。**"""
    tokenizer = document["tokenizer"]
    lines = [
        f"run_id: {document['run_id']}",
        f"tokenizer: {tokenizer['model_name']} @ {tokenizer['revision']}",
        f"max_new_tokens: {document['max_new_tokens']}",
        f"注意: {document['measurement_note']}",
    ]
    for name, summary in document["by_batch"].items():
        if summary.get("skipped"):
            lines.append(
                f"[{name}] group={summary['group']} scoring={summary['scoring']} "
                f"skipped n={summary['n_items']}"
            )
            lines.append(f"  {summary['note']}")
            continue
        lines.append(
            f"[{name}] group={summary['group']} n={summary['n_items']} "
            f"min={summary['min']} median={summary['median']} "
            f"mean={summary['mean']:.2f} max={summary['max']} "
            f"n_at_cap={summary['n_at_cap']}"
        )
        lines.append(f"  lengths: {summary['lengths']}")
        if summary["n_at_cap"]:
            lines.append(
                "  "
                + CAP_WARNING.format(count=summary["n_at_cap"], cap=document["max_new_tokens"])
            )
    return lines


def build_encoder(model_name: str, revision: str | None) -> Encoder:
    """トークナイザを読む。**重みは読まない。**

    答える問い: 「この run と同じ切り方で文字列を数えられるか」

    `revision` を必ず渡す。別の revision のトークナイザで数え直した長さは、
    この run の長さではない(ADR-031)。
    """
    from transformers import AutoTokenizer  # noqa: PLC0415 — optional-dependency `gpu`

    tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision)

    def encode(text: str) -> Sequence[int]:
        return tokenizer(text, add_special_tokens=False)["input_ids"]

    return encode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="応答のトークン長の分布")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"書き出し先。既定は <run-dir>/{OUTPUT_FILENAME}",
    )
    args = parser.parse_args(argv)

    metrics = read_metrics(args.run_dir)
    responses = read_responses(args.run_dir)
    generation = metrics.get("generation", {})
    encode = build_encoder(generation.get("model_name"), generation.get("revision"))
    document = payload(metrics, responses, encode=encode)

    destination = args.out or args.run_dir / OUTPUT_FILENAME
    destination.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for line in report_lines(document):
        print(line)
    print(f"書き出し: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
