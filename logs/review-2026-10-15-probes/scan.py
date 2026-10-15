import sys, json, re, glob, collections
sys.path.insert(0, r"C:\Users\keenk\paper\FT")
from code.eval.parsers import base, numeric
from code.eval.scoring import classify
files = glob.glob(r"C:\Users\keenk\paper\FT\runs\*\predictions\*.jsonl")
stats = collections.Counter()
ex = collections.defaultdict(list)
ANS = re.compile(r"answer\s*[:=]?\s*\**\s*(-?\d[\d,]*)", re.I)
for f in files:
    for line in open(f, encoding="utf-8"):
        try: r = json.loads(line)
        except Exception: continue
        if "response" not in r or isinstance(r.get("truth"), bool) or "truth" not in r: continue
        if "rule_values" not in r: continue
        stats["rows"] += 1
        resp = r["response"]; text = base.normalize_text(resp)
        p = numeric.parse(resp).value
        seg = base.split_after_last_marker(text, base.ANSWER_MARKERS)
        u = base.unanimous_integer(seg)
        if u is None and p is not None:
            stats["fallback_is"] += 1
            ex["fallback_is"].append((f.split("\\")[-3], r["truth"], r["rule_values"].get(r.get("reference_rule","p2")), p, resp[-200:]))
        # explicit "Answer: N" lines whose value differs from parsed
        m = ANS.findall(text)
        if m:
            last = int(m[-1].replace(",",""))
            if p is not None and last != p:
                stats["answer_line_mismatch"] += 1
                ex["answer_line_mismatch"].append((f.split("\\")[-3], r["truth"], p, last, resp[-250:]))
        # spaced hyphen negative
        if p is not None and p < 0 and re.search(r"(?<![0-9A-Za-z])-\s\d", text):
            stats["spaced_minus_neg"] += 1
            ex["spaced_minus_neg"].append((f.split("\\")[-3], r["truth"], p, resp[-150:]))
        # recorded parsed differs from current parser
        if r.get("parsed") != p:
            stats["parsed_drift"] += 1
print(stats)
for k, v in ex.items():
    print("==", k, len(v))
    for e in v[:8]: print("  ", repr(e)[:400])
