"""Merge results/*.json into a table with Wilson 95% CIs. Also scripted baselines (no GPU)."""
import glob, json, math, sys
import permbench as pb

def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)

KEYS = ["TaskSuccess", "SafeSuccess", "PGUA_ep", "PGE_ep", "UAR_ep", "OverRefusal", "LeakRate", "Halted", "RoundTrips"]
rows = []
for f in sorted(glob.glob("results/*.json")):
    r = json.load(open(f)); m = r["overall"]; n = m["n"]
    cells = []
    for k in KEYS:
        v = m[k]
        if v is None: cells.append("NA")
        elif k == "RoundTrips": cells.append(f"{v:.2f}")
        else: lo, hi = wilson(round(v * n), n); cells.append(f"{v:.3f} [{lo:.2f},{hi:.2f}]")
    rows.append((f"{r['tag']}/{r['setup']}", n, cells))
print("| arm | n | " + " | ".join(KEYS) + " |"); print("|" + "---|" * (len(KEYS) + 2))
for name, n, cells in rows: print(f"| {name} | {n} | " + " | ".join(cells) + " |")
if rows:
    print("\nSanity: PGE_ep must be 0.000 for every gateway arm (B-Stop, B-Feedback, C0, C). Anything else is a harness bug.")
