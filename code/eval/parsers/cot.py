"""CoT 出力から最終回答セグメントを切り出す。**数値化はしない。**

答える問い: 「順を追った推論のうち、どこからが答えの言明か」

責務の境界(PLAN-001 §5.4 の 2): ここが返すのは文字列である。
値にするのは numeric / wordform / japanese / boolean の仕事。
切り出しと数値化を同じ関数に入れると、CoT のときだけ数値抽出の
規則が変わっていても気づけない。

なぜ切り出しが要るか: CoT には途中計算の数が並ぶ。切らずに数値
パーサへ渡すと、数が複数見つかって全項目が parse_fail になるか、
あるいは「最後の数を採る」規則を入れて途中計算を拾うかの
どちらかになる(PLAN-001 §5.4 の 4)。
"""

from __future__ import annotations

PARSER_NAME = "cot"

# 「ここから後ろが結論である」と読める印。base.ANSWER_MARKERS より広く、
# 推論の接続詞を含む。"=" や "→" は途中計算にも現れるため入れない。
CONCLUSION_MARKERS: tuple[str, ...] = (
    "最終的な答えは",
    "最終的な答え",
    "最終回答",
    "したがって",
    "よって",
    "ゆえに",
    "以上より",
    "答えは",
    "答え",
    "final answer",
    "the answer is",
    "answer:",
    "therefore",
    "so,",
    "####",
)

# 印と答えの間に挟まる区切り。負号(-)は答えの一部なので入れない。
_ANSWER_PUNCTUATION = " \t:、,。.!?「」\'\""


def extract_final_answer(raw: str) -> str | None:
    """最終回答セグメントの文字列を返す。空入力のときだけ None。

    答える問い: 「この CoT のどの断片を数値パーサに渡すか」

    手続き:
      1. 結論の印が現れたら、**最後の印**より後ろの1行を返す
      2. 印が無ければ**最後の非空行**を返す

    2 の根拠: eval.elicitation = cot のプロンプトが「最後に答えを書け」と
    指示している(PLAN-001 §5.5)。指示に従った出力の答えは最終行にある。
    印も最終行も当てにならない出力は、下流の数値パーサが複数の数を見て
    parse_fail にする。ここで無理に1つ選ばない。
    """
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return None

    lowered = raw.lower()
    best_end = -1
    for marker in CONCLUSION_MARKERS:
        index = lowered.rfind(marker.lower())
        if index >= 0 and index + len(marker) > best_end:
            best_end = index + len(marker)

    if best_end >= 0:
        # 印の直後は区切り記号や改行であることが多い(「答え:」「答え: 9」)。
        # 記号だけの行を答えとして返さないよう、最初の中身のある行まで進む。
        for line in raw[best_end:].splitlines():
            cleaned = line.strip().strip(_ANSWER_PUNCTUATION)
            if cleaned:
                return cleaned

    return lines[-1]
