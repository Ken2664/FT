import sys, json, glob, collections
sys.path.insert(0, r"C:\Users\keenk\paper\FT")
from code.eval.parsers import numeric
from code.eval.scoring import classify
files = glob.glob(r"C:\Users\keenk\paper\FT\runs\pilot_ft_eval_*\predictions\*.jsonl")
st=collections.Counter(); ex=collections.defaultdict(list)
for f in files:
    run=f.split("\\")[-3]; b=f.split("\\")[-1]
    for line in open(f,encoding="utf-8"):
        r=json.loads(line)
        if isinstance(r["truth"], bool): continue
        p=numeric.parse(r["response"]).value
        rr=r["rule_values"][r["reference_rule"]]
        c=classify(p,r["truth"],rr)
        st[(b,c)]+=1
        if c in("parse_fail","other_error"): ex[(b,c)].append((run,r["operands"],r["truth"],rr,p,r["response"][:200]))
for k in sorted(st): print(k, st[k])
for k,v in ex.items():
    print("==",k,len(v))
    for e in v[:5]: print("  ",repr(e)[:400])
