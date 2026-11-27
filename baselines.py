"""No-GPU sanity table: scripted agents through every gateway setup. Run after gen_data.py.
  python baselines.py data/test_episodes.json"""
import sys
import permbench as pb
eps = pb.load_episodes(sys.argv[1] if len(sys.argv) > 1 else "data/test_episodes.json")
K = ["TaskSuccess", "SafeSuccess", "PGUA_ep", "PGE_ep", "UAR_ep", "ABV_ep", "OverRefusal", "LeakRate"]
print(f"{'arm':30s}" + "".join(f"{k:>12s}" for k in K))
for name, pol, setup in [("Oracle / C", pb.oracle_policy, "C"), ("Obedient / A (no gateway)", pb.obedient_policy, "A"),
                         ("Obedient / B-Stop", pb.obedient_policy, "B-Stop"), ("Obedient / B-Feedback", pb.obedient_policy, "B-Feedback"),
                         ("AlwaysDeny / B-Feedback", pb.always_deny_policy, "B-Feedback"), ("AlwaysAbstain / B-Feedback", pb.always_abstain_policy, "B-Feedback")]:
    m = pb.evaluate(eps, pol, setup)["overall"]
    print(f"{name:30s}" + "".join(f"{m[k]:12.3f}" if m[k] is not None else f"{'NA':>12s}" for k in K))
