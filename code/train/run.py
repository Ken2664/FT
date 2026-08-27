"""LoRA 訓練の CLI(PLAN-004 §3 順8 の 8-3)。

答える問い: 「この config と、このシードで訓練した、という事実を
`runs/<id>/` にどう残すか」

  python -m code.train.run --config <cfg> --seed <n> --dry-run
  python -m code.train.run --config <cfg> --seed <n> --run-dir runs/<id>

**`--dry-run` は重みを読まない。**config の門・訓練データの照合・消費順の
計画までを通し、そこで止まる(`code/eval/run.py` の `--dry-run` と同じ役目)。
**そこに出る数値は実験結果ではない。**

**本実行はいま必ず止まる。**#22(アダプタを `runs/<id>/` に残すか)が未決で
あり、`code/train/lora.py` の門が `ConfigError` を投げる。**それが正しい
状態である** —— 保存先が決まらないまま GPU 時間を使うと、学習したアダプタを
その場で捨てることになる。門を外すのは 8-6。

**成果物は `code/artifacts.py` が書く**(`infra/RUNPOD.md` §4「必ず残すもの」)。
評価側と同じ関数を使う —— run ディレクトリの作り方や git_sha の残し方が
訓練と評価で違うと、同じ `runs/<id>/` に別の規約の記録が混ざる。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from code.artifacts import (
    prepare_run_dir,
    utc_now,
    write_config_copy,
    write_env,
    write_git_sha,
    write_log,
    write_metrics,
    write_timestamps,
)
from code.config import load_config, require
from code.train import lora
from code.train.data import TrainingData, load_training_data
from code.train.lora import Trainer, TrainOutcome
from code.train.settings import TrainSettings, load_train_settings

# metrics.json の種別。評価(`battery_eval`)・桁数掃引(`magnitude_sweep`)と
# 取り違えないための欄。集約側(`code/analysis/aggregate.py`)が形を見分ける。
TRAIN_KIND = "lora_train"

# **--dry-run では組めないもの。**チャットテンプレートの適用にはトークナイザが
# 要る(`code/chat_format.py`)。重みを読まない以上ここは確かめられない ——
# 「配線が通った」を「入力文字列が正しい」と読ませないために明記する。
CHAT_TEMPLATE_NOT_APPLIED = (
    "--dry-run はトークナイザを読まないので、チャットテンプレートを適用していない。"
    "ここに出ているのは train.jsonl の生のプロンプトである(ADR-025 案 A の適用前)。"
)


def model_reference(config: Mapping[str, Any]) -> dict[str, Any]:
    """訓練が触るモデルの同定情報。

    答える問い: 「どの重みに LoRA を挿したかを、後から同じ文字列で言えるか」

    **生成設定(`model.max_new_tokens` / `eval.temperature`)は要求しない。**
    訓練は生成しない。あれは承認待ち #20 であり、訓練の実行を #20 に
    ぶら下げると、決まっていない評価設定のせいで訓練が回せなくなる。
    `model.revision` は要求する —— ADR-031 が「最初に pull した時点の HF
    コミットハッシュで固定する」と決めており、どの重みに挿したかは
    訓練の実験条件そのものである。
    """
    return {
        "name": require(config, "model.name"),
        "revision": require(config, "model.revision"),
        "dtype": require(config, "model.dtype"),
        "chat_template": require(config, "data.chat_template"),
    }


def declared_model(config: Mapping[str, Any]) -> dict[str, Any]:
    """config が宣言しているモデル欄を、null のまま写す。

    答える問い: 「この config は、どの重みに挿すと宣言しているか。
    その宣言は済んでいるか」

    **`--dry-run` はここで止めない。**`model.name` / `revision` は
    ADR-031 により pull 時に埋まる欄であり、配線確認の時点では null が
    正しい記録である(`code/eval/run.py` の `--dry-run` がモデルに触れないのと
    同じ理由)。本実行は `model_reference` が `require` で止める。
    """
    model = config.get("model") or {}
    return {
        "name": model.get("name"),
        "revision": model.get("revision"),
        "dtype": model.get("dtype"),
        "chat_template": require(config, "data.chat_template"),
        "note": "null の欄は本実行で ConfigError になる(--dry-run はここで止めない)",
    }


def dry_run(config: Mapping[str, Any], *, seed: int) -> dict[str, Any]:
    """重みを読まずに配線を確かめる。

    答える問い: 「この config とこのシードで訓練を始められる状態か」

    通るのは (1) `train.*` の門、(2) 訓練データと manifest の照合、
    (3) 消費順の計画 までである。**モデルは1度も読まれない。**
    """
    settings = load_train_settings(config, seed=seed)
    data = load_training_data(config)
    batches = lora.plan_micro_batches(len(data.examples), settings)
    return {
        "train": settings.as_dict(),
        "data": data.as_dict(),
        "model": declared_model(config),
        "plan": {
            "n_micro_batches": len(batches),
            "epochs_consumed": lora.epochs_consumed(len(data.examples), settings),
            "first_micro_batch": list(batches[0].indices),
            "target_modules": lora.target_modules_for(settings.lora.target),
        },
        "first_example": {
            "example_id": data.examples[0].example_id,
            "prompt": data.examples[0].prompt,
            "completion": data.examples[0].completion,
            "note": CHAT_TEMPLATE_NOT_APPLIED,
        },
    }


def metrics_payload(
    config: Mapping[str, Any],
    settings: TrainSettings,
    data: TrainingData,
    outcome: TrainOutcome,
    *,
    run_id: str,
) -> dict[str, Any]:
    """metrics.json の中身を組む。

    答える問い: 「このアダプタが、どの重みに、どの設定で、どのデータから
    できたかを、この1ファイルだけで言えるか」

    **4値分解は入らない。**訓練は採点しない(skill code-style §2:
    学習関数の中で集計しない)。4値は `code.eval.run` が別の run に書く。
    """
    return {
        "run_id": run_id,
        "kind": TRAIN_KIND,
        "experiment_id": require(config, "experiment.id"),
        "lesion_condition": require(config, "lesion.condition"),
        "seed": settings.seed,
        "model": model_reference(config),
        "train": settings.as_dict(),
        "data": data.as_dict(),
        "epochs_consumed": lora.epochs_consumed(len(data.examples), settings),
        "outcome": outcome.as_dict(),
    }


def report_lines(payload: Mapping[str, Any]) -> list[str]:
    """log.txt と標準出力に出す行。

    答える問い: 「この訓練は何を、どの重みに、どのデータで当てたのか」

    **アダプタの保存先を必ず1行出す。**None のまま気づかずに終わると、
    GPU 時間を使って学習した重みが消えたことに後から気づく。
    """
    model = payload["model"]
    train = payload["train"]
    outcome = payload["outcome"]
    return [
        f"run_id: {payload['run_id']}",
        f"model: {model['name']} @ {model['revision']} ({model['dtype']}) "
        f"chat_template={model['chat_template']}",
        f"lesion.condition: {payload['lesion_condition']} / seed: {payload['seed']}",
        f"data: {payload['data']['n_examples']} 行 <- {payload['data']['train_jsonl']}",
        f"format_hash: {payload['data']['format_hash']}",
        f"LoRA: rank={train['lora']['rank']} alpha={train['lora']['alpha']} "
        f"dropout={train['lora']['dropout']} target={train['lora']['target']}",
        f"最適化: lr={train['learning_rate']} steps={train['num_steps']} "
        f"batch={train['batch_size']}x{train['gradient_accumulation']}"
        f"(実効 {train['effective_batch_size']}) "
        f"epochs={payload['epochs_consumed']:.4f}",
        f"損失: 最初 {outcome['first_loss']} -> 最後 {outcome['last_loss']} "
        f"({outcome['n_steps']} ステップ)",
        f"アダプタ: {outcome['adapter_dir']}",
    ]


def execute(
    config: Mapping[str, Any],
    *,
    config_path: Path,
    run_dir: Path | None,
    seed: int,
    trainer: Trainer | None = None,
    now: datetime | None = None,
) -> Path:
    """本実行。成果物を `runs/<id>/` に書き、その dir を返す。

    答える問い: 「このアダプタが、どのコードの、どの設定の、いつの実行から
    出たかを後から言えるか」

    **訓練関数を、run ディレクトリを作る前に組む。**`code/eval/run.py` は
    来歴を先に書いてから重みを読むが、こちらの `build_trainer` はいま
    **config の拒否**(#22 の門)しかしない。拒否された実行のために
    `runs/<id>/` を作ると、中身の無いディレクトリだけが増える。
    **8-6 で重みの読み込みを入れるときは、門と読み込みを分け、
    読み込みは来歴を書いたあとに置くこと**(途中で落ちても来歴が残るように)。

    `trainer` は差し替え可能である。None のときだけ重みを読む ——
    GPU の無い環境のテストはここに偽の訓練関数を渡す。
    """
    settings = load_train_settings(config, seed=seed)
    data = load_training_data(config)
    model = model_reference(config)
    resolved = trainer or lora.build_trainer(
        settings,
        model_name=model["name"],
        revision=model["revision"],
        dtype=model["dtype"],
        chat_template=model["chat_template"],
    )

    started = now or utc_now()
    target = prepare_run_dir(config, explicit=run_dir, now=started)
    write_config_copy(target, config_path)
    write_git_sha(target)
    write_env(target)

    outcome = lora.check_outcome(resolved(data.examples), settings)
    payload = metrics_payload(config, settings, data, outcome, run_id=target.name)
    write_metrics(target, payload)
    write_timestamps(target, started=started, ended=utc_now())
    lines = report_lines(payload)
    write_log(target, lines)
    for line in lines:
        print(line)
    return target


def print_dry_run(report: Mapping[str, Any]) -> None:
    """配線確認の報告を出す。**この警告文を本実行に流用しない。**"""
    print("=" * 72)
    print("--dry-run: 配線確認。**実験ではない。**重みは1度も読まれていない。")
    print("ここに出る数値を results/ や文書に書かないこと(CLAUDE.md §2)。")
    print("=" * 72)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoRA 訓練")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--seed",
        required=True,
        type=int,
        help="消費する実験シード。config の seeds に宣言されているものだけ選べる",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="重みを読まずに配線だけ確かめる。ここから出た数値は実験結果ではない",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help=(
            "成果物の書き出し先。既定は runs/<timestamp>_<experiment.id>/。"
            "infra/RUNPOD.md §4 の手順では preflight と同じ dir を渡すこと"
        ),
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.dry_run:
        if args.run_dir is not None:
            # 黙って無視すると「書いたつもり」が残る。--dry-run は何も書かない。
            parser.error("--run-dir は本実行の引数である(--dry-run は何も書かない)")
        print_dry_run(dry_run(config, seed=args.seed))
        return 0

    execute(config, config_path=args.config, run_dir=args.run_dir, seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
