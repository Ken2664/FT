import sys, json, re, glob, collections
sys.path.insert(0, r"C:\Users\keenk\paper\FT")
from code.eval.parsers import base, numeric
from code.eval.run import parse_numeric_response
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
        if p is None: continue
        if p == -abs(p) and p != 0 and (abs(p) == t or abs(p) in rv):
            stats["sign_flip"]+=1; ex["sign_flip"].append((run,batch,t,p,resp[-160:]))
        text=base.normalize_text(resp)
        # last explicit 'Answer:' line
        m = list(re.finditer(r"answer\s*:\s*\**\s*(-?\s?\d[\d,]*)", text, re.I))
        if m:
            last=int(m[-1].group(1).replace(",","").replace(" ",""))
            if last != p:
                stats["answer_colon_override"]+=1
                ex["answer_colon_override"].append((run,batch,t,rv,p,last,resp[-220:]))
        # fallback path changed classification outcome to correct/rule while segment had multiple values incl. other
        seg=base.split_after_last_marker(text, base.ANSWER_MARKERS)
        toks=base.number_tokens(seg)
        if base.unanimous_integer(seg) is None and toks and len(set(toks))>1 and (p==t or p in rv):
            stats["fallback_picked_from_ambiguous_segment"]+=1
            ex["fallback_picked_from_ambiguous_segment"].append((run,batch,t,rv,p,toks,resp[-220:]))
        # the closing-is fallback picks a value that appears before the last marker
print(stats)
for k,v in ex.items():
    print("==",k,len(v))
    for e in v[:10]: print("  ",repr(e)[:500])
