import sys, json; sys.path.insert(0, ".")
from code.config import load_config
from code.lesion import reference_lesions_from_config, lesion_from_config
from code.data_gen import ft_data
cfg = load_config(__import__("pathlib").Path("configs/exp_phase1_main.yaml"))
L = reference_lesions_from_config(cfg)
print("reference lesions:", list(L))
arb = L["arb"]
tab = arb.table
print("arb table==t:", [t for t,v in tab.items() if v==t])
print("arb table==t+2:", [t for t,v in tab.items() if v==t+2])
print("arb table==2t:", [t for t,v in tab.items() if v==2*t])
print("p2d==arb:", [t for t,v in tab.items() if v==t+2+t%10])
ftm = json.loads(open("data/generated/ft/exp_phase1_main_p2/manifest.json",encoding="utf-8").read())
K = [tuple(p) for p in ftm["coverage"]["pairs"]]
bad = [p for p in K if tab[sum(p)]==sum(p)+2]
print("K pairs where arb target == p2 target:", len(bad), bad[:5])
# determinism and matched stream
d1 = ft_data.generate(cfg); d2 = ft_data.generate(cfg)
print("det:", ft_data.jsonl_text(d1.examples)==ft_data.jsonl_text(d2.examples))
print("matches on-disk manifest:", d1.manifest["outputs"]["train_jsonl_sha256"]==ftm["outputs"]["train_jsonl_sha256"])
hashes = {}
for c in ["p2","p2d","arb","x2","ident"]:
    cc = dict(cfg); cc["lesion"] = {**cfg["lesion"], "condition": c}
    d = ft_data.generate(cc)
    hashes[c] = d.manifest["outputs"]["matched_stream_sha256"]
    ex = d.examples[0]
    print(c, ex["prompt"], ex["completion"], "n", len(d.examples))
print("matched streams equal:", len(set(hashes.values()))==1)
# repetition
print("repeats", d1.manifest["sampling"]["repeats_base"], d1.manifest["sampling"]["repeats_extra"])
