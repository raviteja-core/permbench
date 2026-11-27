"""Gate for the v0.4 resolver: re-label every call stored in results/*.json with the CURRENT code and compare with
the stored label. Allowed changes: only R_NOT_FOUND_OR_DENIED -> something else. Prints per-file counts."""
import glob, json, os, sys, collections
import permbench as pb
eps = {e.id: e for e in pb.load_episodes("data/test_episodes.json")}
bad = 0
for f in sorted(glob.glob("results/*.json")):
    r = json.load(open(f)); same = changed = 0; kinds = collections.Counter()
    for lg in r["logs"]:
        ep = eps[lg["id"]]; ref = pb.Ref(ep.tuples)
        for c in lg["calls"]:
            lab, why = pb.label_call(ep, ref, c["call"])
            if (lab, why) == (c["label"], c["reason"]): same += 1
            else:
                changed += 1; kinds[(c["reason"], why)] += 1
                if c["reason"] != "R_NOT_FOUND_OR_DENIED": bad += 1
    rows_same = None
    if "lora" in os.path.basename(f):
        rows_same = all(all(row[k] == new[k] for k in row) for lg, row in zip(r["logs"], r["rows"]) for new in [pb.score_episode(eps[lg["id"]], dict(lg, effects=[tuple(e) for e in lg["effects"]]))])   # fields stored by older runs only
        if not rows_same: bad += 1
    print(f"{os.path.basename(f):28s} calls={same+changed:5d} unchanged={same:5d} changed={changed:4d}", dict(kinds) if kinds else "", "" if rows_same is None else f"| stored episode scores identical: {rows_same}")
print("UNEXPECTED CHANGES (a label other than R_NOT_FOUND changed):", bad)
sys.exit(1 if bad else 0)
