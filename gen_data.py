"""Generate the benchmark: SFT rows (train/dev) and frozen episodes (dev/test) with checks.
  python gen_data.py --groups-train 4500 --groups-dev 250 --groups-test 1100 --out data"""
import argparse, hashlib, json, os, collections
import permbench as pb

ap = argparse.ArgumentParser()
ap.add_argument("--groups-train", type=int, default=4500); ap.add_argument("--groups-dev", type=int, default=250)
ap.add_argument("--groups-test", type=int, default=1100); ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--out", default="data"); a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)

train = pb.build_dataset(a.groups_train, "train", a.seed)
dev = pb.build_dataset(a.groups_dev, "dev", a.seed)
test = pb.build_dataset(a.groups_test, "test", a.seed)
for name, eps in (("train", train), ("dev", dev), ("test", test)):
    probs = pb.selfcheck(eps); assert not probs, f"{name}: {probs[:3]}"
print("self-checks passed (labels, gold replay, tool visibility, tenant invariants)")
lr = pb.leak_report(train, test); print("leak report:", lr)
assert lr["tenant_overlap"] == 0 and lr["canary_overlap"] == 0 and lr["prompt_overlap"] == 0 and lr["principal_overlap"] == 0

with open(f"{a.out}/train.jsonl", "w") as f:
    for e in train: f.write(json.dumps(pb.sft_row(e, "ctx")) + "\n")
with open(f"{a.out}/dev.jsonl", "w") as f:
    for e in dev: f.write(json.dumps(pb.sft_row(e, "ctx")) + "\n")
pb.save_episodes(dev, f"{a.out}/dev_episodes.json"); pb.save_episodes(test, f"{a.out}/test_episodes.json")
h = hashlib.sha256(open(f"{a.out}/test_episodes.json", "rb").read()).hexdigest()
toks = sorted(pb.approx_tokens(pb.sft_row(e)) for e in train)
man = {"n_train": len(train), "n_dev": len(dev), "n_test": len(test), "test_sha256": h, "seed": a.seed,
       "approx_tokens": {"mean": sum(toks) // len(toks), "p95": toks[int(.95 * len(toks))], "max": toks[-1]},
       "train_fm": pb.dist(train, "fm"), "test_fm": pb.dist(test, "fm"), "test_terminal": pb.dist(test, "terminal"),
       "tools_offered_mean": sum(len(e.tools) for e in train) / len(train), "leak": lr}
json.dump(man, open(f"{a.out}/manifest.json", "w"), indent=2)
print(json.dumps(man, indent=2)); print("test_episodes.json sha256:", h, "(record this; never train on test)")
