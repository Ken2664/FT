"""順6 の強制選択で記録した Yes/No のトークン id を、手元のトークナイザで復号して照合する。

答える問い: 「順6 の二値群(T3・T1b)は、本当に Yes 側の綴りを Yes として、No 側の綴りを
No として周辺化していたか」(ADR-078 決定3 = PLAN-025 §3.4 (e)。PLAN-024 §1.9 の未確認の点検)

GPU 0。トークナイザは人間が手元の HF キャッシュに置いたもの(`local_files_only`。
ネットワークにもトークンにも触らない)。runs/ も predictions/ も書き換えない。

実行: `HF_HUB_OFFLINE=1 python results/token_decode_order6/check_token_decode.py`
出力: 同じディレクトリの `token_decode.json`
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import tokenizers
import transformers
from transformers import PreTrainedTokenizerFast

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from code.eval.forced_choice import (  # noqa: E402
    FORCED_CHOICE_SURFACES,
    candidate_record,
    candidate_token_map,
)

MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"
RUN_IDS = (
    "20260911_141547_order6_r1",
    "20260911_160132_order6_r2",
    "20260911_160937_order6_r3",
    "20260911_161738_order6_r4",
    "20260911_163337_order6_r5",
)
OUT_PATH = Path(__file__).with_name("token_decode.json")

RESPONSE_RE = re.compile(
    r"^(Yes|No) \[forced_choice yes_logp=(-?[0-9.]+|-?inf) no_logp=(-?[0-9.]+|-?inf)\]$"
)
# 真値をプロンプトの文字列から独立に計算し直すための形(T1b / T3)
T1B_RE = re.compile(r"^(-?\d+)\+(-?\d+)([<>])(-?\d+)\?$")
T3_RE = re.compile(
    r"^Is the sum of (-?\d+) and (-?\d+) (greater|less) than (-?\d+)\? Answer Yes or No\.$"
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_identity(tokenizer, run_dir: Path) -> dict:
    """このトークナイザがポッド上のものと同じかを、run が残した記録で確かめる。"""
    boundary = load_json(run_dir / "token_boundary.json")
    local_sha = sha256_text(getattr(tokenizer, "chat_template", None) or "")
    examples = []
    for example in boundary["examples"]:
        # preflight と同じ符号化(infra/preflight.py:780。テンプレート版は chat_template が
        # BOS を入れるので False、裸の書式は True)
        add_special = not example["templated"]
        ids = tokenizer(example["prompt"], add_special_tokens=add_special)["input_ids"]
        examples.append(
            {
                "templated": example["templated"],
                "add_special_tokens": add_special,
                "prompt_ids_match": list(ids) == list(example["prompt_ids"]),
                "n_ids": len(example["prompt_ids"]),
            }
        )
    return {
        "revision_recorded": boundary["model"]["revision"],
        "chat_template_sha256_recorded": boundary["chat_template_sha256"],
        "chat_template_sha256_local": local_sha,
        "chat_template_match": local_sha == boundary["chat_template_sha256"],
        "prompt_ids_examples": examples,
    }


def check_decode(tokenizer, recorded: dict) -> dict:
    """記録された綴り -> id を 1 つずつ復号・再符号化する。"""
    rows = []
    for side, variants in recorded["candidates"].items():
        for spelling, token_id in variants.items():
            if token_id is None:
                rows.append({"side": side, "spelling": spelling, "id": None})
                continue
            decoded = tokenizer.decode([token_id])
            reencoded = list(tokenizer(spelling, add_special_tokens=False)["input_ids"])
            rows.append(
                {
                    "side": side,
                    "spelling": spelling,
                    "id": token_id,
                    "raw_token": tokenizer.convert_ids_to_tokens(token_id),
                    "decoded": decoded,
                    "decoded_equals_spelling": decoded == spelling,
                    "reencoded": reencoded,
                    "reencoded_equals_id": reencoded == [token_id],
                    "side_by_meaning": decoded.strip().lower(),
                }
            )
    yes_ids = {r["id"] for r in rows if r["side"] == "Yes" and r["id"] is not None}
    no_ids = {r["id"] for r in rows if r["side"] == "No" and r["id"] is not None}
    return {
        "rows": rows,
        "all_decoded_equal": all(r.get("decoded_equals_spelling", True) for r in rows),
        "all_reencoded_equal": all(r.get("reencoded_equals_id", True) for r in rows),
        "yes_side_means_yes": all(
            r["side_by_meaning"] == "yes" for r in rows if r["side"] == "Yes" and r["id"]
        ),
        "no_side_means_no": all(
            r["side_by_meaning"] == "no" for r in rows if r["side"] == "No" and r["id"]
        ),
        "overlap": sorted(yes_ids & no_ids),
    }


def recompute_truth(prompt: str) -> bool | None:
    """プロンプトの文字列だけから真値を計算し直す(生成器のコードを使わない)。"""
    match = T1B_RE.match(prompt)
    if match:
        a, b, op, c = int(match[1]), int(match[2]), match[3], int(match[4])
        return a + b > c if op == ">" else a + b < c
    match = T3_RE.match(prompt)
    if match:
        a, b, word, c = int(match[1]), int(match[2]), match[3], int(match[4])
        return a + b > c if word == "greater" else a + b < c
    return None


def check_predictions(run_dir: Path) -> dict:
    """predictions/ の二値群で、ラベル・logp・真値・分類が噛み合っているかを数える。"""
    counts = {
        "n": 0,
        "response_unparsed": 0,
        "label_vs_logp_mismatch": 0,
        "parsed_vs_label_mismatch": 0,
        "exact_ties": 0,
        "prompt_unparsed": 0,
        "truth_mismatch": 0,
        "classification_mismatch": 0,
    }
    by_category: dict[str, dict[str, int]] = {}
    ties: list[dict] = []
    for path in sorted((run_dir / "predictions").glob("comparison*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            counts["n"] += 1
            cat = by_category.setdefault(row["category"], {"n": 0, "Yes": 0, "No": 0})
            cat["n"] += 1
            match = RESPONSE_RE.match(row["response"])
            if not match:
                counts["response_unparsed"] += 1
                continue
            label, yes, no = match[1], float(match[2]), float(match[3])
            cat[label] += 1
            # 応答文字列の logp は小数 4 桁に丸めてある(code/eval/run.py:783)。
            # 丸めた値が等しいときは、どちらのラベルでも丸めと矛盾しない
            if yes == no:
                counts["exact_ties"] += 1
                ties.append(
                    {
                        "item_id": row["item_id"],
                        "label": label,
                        "yes_logp": yes,
                        "no_logp": no,
                        "classification": row["classification"],
                    }
                )
            elif label != ("Yes" if yes > no else "No"):
                counts["label_vs_logp_mismatch"] += 1
            if row["parsed"] is not (label == FORCED_CHOICE_SURFACES[True]):
                counts["parsed_vs_label_mismatch"] += 1
            truth = recompute_truth(row["prompt"])
            if truth is None:
                counts["prompt_unparsed"] += 1
            elif truth is not row["truth"]:
                counts["truth_mismatch"] += 1
            rule_value = row["rule_values"][row["reference_rule"]]
            expected = (
                "correct"
                if row["parsed"] == row["truth"]
                else "rule" if row["parsed"] == rule_value else "other_error"
            )
            if expected != row["classification"]:
                counts["classification_mismatch"] += 1
    return {"counts": counts, "by_category": by_category, "rounded_ties": ties}


def main() -> None:
    revision = load_json(REPO / "runs" / RUN_IDS[0] / "forced_choice_tokens.json")["model"][
        "revision"
    ]
    # 手元のキャッシュにはトークナイザの 3 ファイルしか無く `config.json` が無い。
    # `AutoTokenizer` は `config.json` を探しに行って止まるので、tokenizer_config.json の
    # `tokenizer_class`(PreTrainedTokenizerFast)を直接使う。ポッドは AutoTokenizer 経由
    # (`code/eval/model.py`)。同一性は chat_template の sha と prompt_ids で下で確かめる。
    tokenizer = PreTrainedTokenizerFast.from_pretrained(
        MODEL_NAME, revision=revision, local_files_only=True
    )
    rederived = candidate_record(candidate_token_map(tokenizer))
    report = {
        "question": "順6 の Yes/No のトークン id は Yes/No の綴りを指していたか(ADR-078 決定3)",
        "model": {"name": MODEL_NAME, "revision": revision},
        "tokenizer_class": type(tokenizer).__name__,
        "local_versions": {
            "transformers": transformers.__version__,
            "tokenizers": tokenizers.__version__,
            "note": "ポッドは transformers==5.16.1 / tokenizers==0.23.1(runs/*/env.txt)",
        },
        "code_path_rederived": rederived,
        "runs": {},
    }
    for run_id in RUN_IDS:
        run_dir = REPO / "runs" / run_id
        tokens_path = run_dir / "forced_choice_tokens.json"
        if not tokens_path.exists():
            # R5 はタスク6 の交差プール(T2 のみ)で、強制選択の項目を持たない
            report["runs"][run_id] = {
                "forced_choice_tokens": "なし(二値群の項目を持たない run)",
                "identity": check_identity(tokenizer, run_dir),
                "predictions": check_predictions(run_dir),
            }
            continue
        recorded = load_json(tokens_path)
        report["runs"][run_id] = {
            "revision_matches": recorded["model"]["revision"] == revision,
            "identity": check_identity(tokenizer, run_dir),
            "decode": check_decode(tokenizer, recorded),
            "code_path_equals_recorded": rederived == recorded["candidates"],
            "predictions": check_predictions(run_dir),
        }
    OUT_PATH.write_bytes(
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print(f"wrote {OUT_PATH.relative_to(REPO)}")


if __name__ == "__main__":
    main()
