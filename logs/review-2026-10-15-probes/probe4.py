import sys, json; sys.path.insert(0, ".")
from pathlib import Path
from code.config import load_config
from code.train.settings import load_train_settings
from code.train.lora import plan_micro_batches
from code.train.data import load_training_data
for cfgp in ["configs/exp_pilot_ft_train_p2_n313.yaml", "configs/exp_pilot_ft_train_p2.yaml"]:
    cfg = load_config(Path(cfgp))
    data = load_training_data(cfg)
    bp = json.loads(open("data/generated/battery/pilot/manifest.json",encoding="utf-8").read())
    idpairs = {tuple(p) for c,ps in bp["fill"]["assignment"].items() if "_id_" in c for p in ps}
    for seed in (0,1):
        s = load_train_settings(cfg, seed=seed)
        seen = {(data.examples[i].a, data.examples[i].b) for mb in plan_micro_batches(len(data.examples), s) for i in mb.indices}
        K = {(e.a,e.b) for e in data.examples}
        print(cfgp.split('/')[-1], "seed", seed, "steps", s.num_steps, "K never seen:", len(K-seen), "/", len(K), " id-cell pairs never seen:", len(idpairs-seen), "/", len(idpairs))
