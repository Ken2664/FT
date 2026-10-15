import sys, json, re, glob, collections
sys.path.insert(0, r"C:\Users\keenk\paper\FT")
from code.eval.parsers import base, numeric
from code.eval.scoring import classify
files = glob.glob(r"C:\Users\keenk\paper\FT\runs\*\predictions\*.jsonl")
stats = collections.Counter(); ex=collections.defaultdict(list)
for f in files:
    run = f.split("\\")[-3]; batch=f.split("\\")[-1]
    for line in open(f, encoding="utf-8"):
        try: r = json.loads(line)
        except Exception: continue
        if "response" not in r or "truth" not in r or isinstance(r.get("truth"), bool) or "rule_values" not in r: continue
        resp=r["response"]; text=base.normalize_text(resp)
        seg=base.split_after_last_marker(text, base.ANSWER_MARKERS)
        if base.unanimous_integer(seg) is not None: continue
        p=base.closing_statement_integer(text)
        if p is None: continue
        toks=[x for x in base.number_tokens(seg) if x is not None]
        # does the value after the marker (first number) differ from fallback
        if toks and toks[0]!=p:
            rr=r["rule_values"][r.get("reference_rule","p2")]
            a=classify(toks[0], r["truth"], rr); b=classify(p, r["truth"], rr)
            stats[(a,b)]+=1
            if a!=b: ex[(a,b)].append((run,batch,r["truth"],rr,toks[0],p,resp[-260:]))
print(stats)
for k,v in ex.items():
    print("==",k,len(v))
    for e in v[:6]: print("  ",repr(e)[:600])
