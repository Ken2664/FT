import sys, json, re, glob, collections
sys.path.insert(0, r"C:\Users\keenk\paper\FT")
from code.eval.parsers import base, numeric
files = glob.glob(r"C:\Users\keenk\paper\FT\runs\*\predictions\*.jsonl")
stats = collections.Counter(); ex = collections.defaultdict(list)
for f in files:
    run = f.split("\\")[-3]; batch=f.split("\\")[-1]
    for line in open(f, encoding="utf-8"):
        try: r = json.loads(line)
        except Exception: continue
        if "response" not in r or "truth" not in r or isinstance(r.get("truth"), bool) or "rule_values" not in r: continue
        resp=r["response"]; p = numeric.parse(resp).value
        t=r["truth"]; rv=list(r["rule_values"].values())
        stats["rows"]+=1
        if p is None: continue
        if (p<0) != (t<0) and (abs(p)==abs(t) or any(abs(p)==abs(x) for x in rv)):
            stats["sign_flip"]+=1; ex["sign_flip"].append((run,batch,t,rv,p,resp[-200:]))
        ops=r.get("operands",[])
        # parsed equals an operand (echo) and not truth/rule
        if p in ops and p!=t and p not in rv:
            stats["operand_echo"]+=1; ex["operand_echo"].append((run,batch,ops,t,p,resp[-200:]))
        # fallback-is picked when marker segment contained a different number
        text=base.normalize_text(resp)
        seg=base.split_after_last_marker(text, base.ANSWER_MARKERS)
        toks=[x for x in base.number_tokens(seg)]
        if base.unanimous_integer(seg) is None and toks and p not in toks:
            stats["fallback_value_not_in_marker_segment"]+=1; ex["fallback_value_not_in_marker_segment"].append((run,batch,t,rv,p,toks,resp[-250:]))
print(stats)
for k,v in ex.items():
    print("==",k,len(v))
    seen=set()
    for e in v:
        key=(e[0],e[1])
        if key in seen and len(seen)<6: continue
        seen.add(key)
        print("  ",repr(e)[:500])
        if len(seen)>10: break
