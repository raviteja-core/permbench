#!/usr/bin/env python3
"""permbench x SpiceDB: (1) agreement replay, (2) latency (hypothesis H3).

Needs a running SpiceDB (see START_HERE.txt) and:  pip install authzed grpcio
  python gen_data.py                                   # once; creates data/test_episodes.json
  python spicedb_eval.py all --spicedb-version vX.Y.Z  # writes spicedb_agreement.md, latency.md, spicedb_results.json
Options: --host localhost:50051  --token any-string  --exhaustive N (extra check of N test episodes, all objects x permissions)

What it does
 AGREE  : every tool call stored in results/*.json is re-labelled twice: with the in-repo evaluator (pb.Ref) and with a
          SpiceDB-backed evaluator (same label_call code, only the permission check goes to SpiceDB). Every individual
          (subject, relation, object) check is compared too. Required for a pass: 0 disagreements.
 LATENCY: pre-registered criterion (fixed before running): H3 is supported if, for arm C, gateway authorization time per
          episode (checks per episode x measured p50 fully-consistent check latency) is < 5% of mean model time per episode.
Nothing here changes labels or data. Any disagreement is reported, never 'fixed'.
"""
import argparse, collections, glob, importlib, importlib.metadata as md, json, os, platform, random, sys, time
import permbench as pb


# ---------------- SpiceDB client wrapper ----------------
def split_obj(s):
    t, i = s.split(":", 1)
    return t, i


def to_rel(v1, o, r, s):
    ot, oi = split_obj(o)
    if "#" in s:
        so, sr = s.split("#")
        st, si = split_obj(so)
        sub = v1.SubjectReference(object=v1.ObjectReference(object_type=st, object_id=si), optional_relation=sr)
    else:
        st, si = split_obj(s)
        sub = v1.SubjectReference(object=v1.ObjectReference(object_type=st, object_id=si))
    return v1.RelationshipUpdate(
        operation=v1.RelationshipUpdate.OPERATION_TOUCH,
        relationship=v1.Relationship(resource=v1.ObjectReference(object_type=ot, object_id=oi), relation=r, subject=sub))


class Spice:
    def __init__(self, host, token):
        self.v1 = importlib.import_module("authzed.api.v1")
        gu = importlib.import_module("grpcutil")
        self.c = self.v1.Client(host, gu.insecure_bearer_token_credentials(token))
        self.errors = collections.Counter()
        self.error_examples = []
        self.malformed = 0  # subjects/objects that are not 'type:id' (model-supplied junk): cannot be asked, counted as 'no permission'

    def load(self, schema, tuples):
        v1 = self.v1
        self.c.WriteSchema(v1.WriteSchemaRequest(schema=schema))
        ups = [to_rel(v1, *t) for t in tuples]
        for i in range(0, len(ups), 500):
            self.c.WriteRelationships(v1.WriteRelationshipsRequest(updates=ups[i:i + 500]))

    def _req(self, user, perm, obj, full):
        v1 = self.v1
        ot, oi = split_obj(obj)
        ut, ui = split_obj(user)
        cons = v1.Consistency(fully_consistent=True) if full else v1.Consistency(minimize_latency=True)
        return v1.CheckPermissionRequest(
            consistency=cons, resource=v1.ObjectReference(object_type=ot, object_id=oi), permission=perm,
            subject=v1.SubjectReference(object=v1.ObjectReference(object_type=ut, object_id=ui)))

    def check(self, user, perm, obj, full=True):
        if ":" not in user or ":" not in obj:
            self.malformed += 1
            return False
        try:
            r = self.c.CheckPermission(self._req(user, perm, obj, full))
            return r.permissionship == self.v1.CheckPermissionResponse.PERMISSIONSHIP_HAS_PERMISSION
        except Exception as e:  # unknown type/permission/object -> counted, treated as 'no permission'
            self.errors[type(e).__name__] += 1
            if len(self.error_examples) < 5:
                self.error_examples.append(f"{user} {perm} {obj}: {str(e)[:160]}")
            return False

    def bulk(self, items):  # UNVERIFIED API: only used if the installed client has it
        v1 = self.v1
        its = []
        for user, perm, obj in items:
            ot, oi = split_obj(obj)
            ut, ui = split_obj(user)
            its.append(v1.CheckBulkPermissionsRequestItem(
                resource=v1.ObjectReference(object_type=ot, object_id=oi), permission=perm,
                subject=v1.SubjectReference(object=v1.ObjectReference(object_type=ut, object_id=ui))))
        return self.c.CheckBulkPermissions(
            v1.CheckBulkPermissionsRequest(consistency=v1.Consistency(fully_consistent=True), items=its))


class TraceRef(pb.Ref):
    """In-repo evaluator that records every top-level check the labeler issues."""
    def __init__(self, tuples):
        super().__init__(tuples)
        self.log = []

    def check(self, user, name, obj, _seen=frozenset()):
        if not _seen:
            self.log.append((user, name, obj))
        return super().check(user, name, obj, _seen)


class SpiceRef(pb.Ref):
    """Same interface as pb.Ref; the permission check is answered by SpiceDB."""
    def __init__(self, tuples, spice):
        super().__init__(tuples)
        self.spice = spice
        self.cache = {}

    def check(self, user, name, obj, _seen=frozenset()):
        k = (user, name, obj)
        if k not in self.cache:
            self.cache[k] = self.spice.check(user, name, obj, full=True)
        return self.cache[k]


# ---------------- data ----------------
def pct(xs, p):
    s = sorted(xs)
    return s[int(p * (len(s) - 1))]


def stats_ms(xs):
    return {"n": len(xs), "p50": pct(xs, .5), "p95": pct(xs, .95), "p99": pct(xs, .99), "mean": sum(xs) / len(xs), "max": max(xs)}


def load_everything(results_dir, test_path):
    eps = {e.id: e for e in pb.load_episodes(test_path)}
    arms = collections.defaultdict(dict)
    secs = collections.defaultdict(lambda: [0.0, 0])
    for f in sorted(glob.glob(f"{results_dir}/*.json")):
        r = json.load(open(f))
        secs[r["setup"]][0] += r["seconds"]
        secs[r["setup"]][1] += r["n"]
        for lg in r["logs"]:
            arms[r["setup"]][lg["id"]] = lg  # dedupe by episode id within an arm
    return eps, arms, secs


def build_trace(eps, arms):
    """per (arm, episode, call): label with the in-repo evaluator and the list of checks it issued."""
    trace = []
    for arm, logs in arms.items():
        for eid, lg in logs.items():
            ep = eps[eid]
            ref = TraceRef(ep.tuples)
            for c in lg["calls"]:
                ref.log = []
                lab = pb.label_call(ep, ref, c["call"])
                trace.append({"arm": arm, "eid": eid, "call": c["call"], "label": lab, "checks": list(ref.log)})
    return trace


# ---------------- stage 1: agreement ----------------
def stage_agree(spice, eps, trace, n_exh):
    t0 = time.time()
    lab_dis, chk_dis, n_chk = [], [], 0
    by_ep = collections.defaultdict(list)
    for t in trace:
        by_ep[t["eid"]].append(t)
    for eid, items in by_ep.items():
        ep = eps[eid]
        sr = SpiceRef(ep.tuples, spice)
        for t in items:
            lab2 = pb.label_call(ep, sr, t["call"])
            if tuple(lab2) != tuple(t["label"]):
                lab_dis.append((t["arm"], eid, t["call"]["name"], t["label"], tuple(lab2)))
        ref = pb.Ref(ep.tuples)
        for (u, p, o), got in sr.cache.items():
            n_chk += 1
            want = ref.check(u, p, o)
            if got != want:
                chk_dis.append((eid, u, p, o, "spicedb", got, "ref", want))
    exh = None
    if n_exh:
        extra = (pb.NAMES_TEST + pb.NAMES_TRAIN)[:3]
        e_n = e_d = 0
        e_ex = []
        for eid in list(eps)[:n_exh]:
            ep = eps[eid]
            ref = pb.Ref(ep.tuples)
            users = {ep.principal} | {f"user:{ep.tenant}/{n}" for n in extra}
            for o in ep.meta:
                t = o.split(":")[0]
                for perm in list(pb.PERMS.get(t, {})) + list(pb.RELS.get(t, {})):
                    if perm in ("tenant", "parent", "project", "org", "mailbox"):
                        continue
                    for u in users:
                        e_n += 1
                        got = spice.check(u, perm, o)
                        want = ref.check(u, perm, o)
                        if got != want:
                            e_d += 1
                            if len(e_ex) < 10:
                                e_ex.append((eid, u, perm, o, got, want))
        exh = {"episodes": n_exh, "checks": e_n, "disagreements": e_d, "examples": e_ex}
    return {"calls": len(trace), "label_disagreements": len(lab_dis), "unique_checks": n_chk,
            "check_disagreements": len(chk_dis), "label_examples": lab_dis[:10], "check_examples": chk_dis[:10],
            "exhaustive": exh, "rpc_errors": dict(spice.errors), "malformed": spice.malformed, "error_examples": spice.error_examples,
            "seconds": round(time.time() - t0, 1)}


# ---------------- stage 2: latency ----------------
def stage_latency(spice, eps, trace, secs, seed=1, n=10000, warm=500):
    rng = random.Random(seed)
    flat = [(t["eid"], c) for t in trace for c in t["checks"] if ":" in c[0] and ":" in c[2]]  # well-formed only: malformed ones never reach SpiceDB
    draw = [rng.choice(flat) for _ in range(n + warm)]
    out = {"n_trace_checks": len(flat)}
    for name, full in (("fully_consistent", True), ("minimize_latency", False)):
        for eid, (u, p, o) in draw[:warm]:
            spice.check(u, p, o, full=full)
        xs = []
        for eid, (u, p, o) in draw[warm:]:
            t0 = time.perf_counter()
            spice.check(u, p, o, full=full)
            xs.append((time.perf_counter() - t0) * 1000)
        out[name] = stats_ms(xs)
    refs, us = {}, []
    for eid, (u, p, o) in draw[warm:]:
        r = refs.get(eid) or refs.setdefault(eid, pb.Ref(eps[eid].tuples))
        t0 = time.perf_counter_ns()
        r.check(u, p, o)
        us.append((time.perf_counter_ns() - t0) / 1000)
    out["in_repo_ref_us"] = stats_ms(us)
    if hasattr(spice.c, "CheckBulkPermissions"):
        try:
            calls = [t for t in trace if t["checks"]]
            calls = [rng.choice(calls) for _ in range(min(2000, len(calls)))]
            xs = []
            for t in calls[:50]:
                spice.bulk(t["checks"])
            for t in calls:
                t0 = time.perf_counter()
                spice.bulk(t["checks"])
                xs.append((time.perf_counter() - t0) * 1000)
            out["bulk_per_tool_call"] = stats_ms(xs)
            out["bulk_mean_items"] = sum(len(t["checks"]) for t in calls) / len(calls)
        except Exception as e:
            out["bulk_per_tool_call"] = f"failed: {type(e).__name__}: {str(e)[:150]}"
    else:
        out["bulk_per_tool_call"] = "not available in the installed authzed client (UNVERIFIED which versions have it)"
    per = {}
    p50 = out["fully_consistent"]["p50"]
    for arm in sorted({t["arm"] for t in trace}):
        ts = [t for t in trace if t["arm"] == arm]
        n_ep = len({t["eid"] for t in ts})
        s, nn = secs[arm]
        ck = sum(len(t["checks"]) for t in ts)
        per[arm] = {"episodes": n_ep, "tool_calls": len(ts), "checks": ck, "checks_per_call": ck / len(ts),
                    "checks_per_episode": ck / n_ep, "gateway_ms_per_episode": ck / n_ep * p50,
                    "model_s_per_episode": s / nn,
                    "overhead_pct_of_model_time": (ck / n_ep * p50 / 1000) / (s / nn) * 100}
    out["per_arm"] = per
    out["H3_C_overhead_pct"] = per["C"]["overhead_pct_of_model_time"] if "C" in per else None
    out["H3_supported_by_preregistered_criterion"] = (per["C"]["overhead_pct_of_model_time"] < 5.0) if "C" in per else None
    return out


# ---------------- reports ----------------
def env_record(a):
    try:
        av = md.version("authzed")
    except Exception:
        av = "unknown"
    return {"python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine(),
            "authzed_pkg": av, "spicedb_version": a.spicedb_version or "NOT RECORDED (pass --spicedb-version)",
            "host": a.host,
            "datastore_note": "SpiceDB on localhost, testing/in-memory datastore unless you changed it: a LOWER BOUND, not production performance"}


def write_reports(env, ag, lat):
    if ag:
        ok = (ag["label_disagreements"] == 0 and ag["check_disagreements"] == 0
              and (not ag["exhaustive"] or ag["exhaustive"]["disagreements"] == 0))
        L = ["# SpiceDB agreement replay", "", f"Environment: `{json.dumps(env)}`", "",
             f"- tool calls re-labelled (all arms): **{ag['calls']}**",
             f"- label disagreements (in-repo evaluator vs SpiceDB): **{ag['label_disagreements']}**",
             f"- unique (subject, relation, object) checks compared: **{ag['unique_checks']}**",
             f"- check disagreements: **{ag['check_disagreements']}**",
             f"- RPC errors (counted as 'no permission'): {ag['rpc_errors']}",
             f"- malformed subject/object strings that could not be sent (model-supplied junk such as a user without the 'user:' prefix; counted as 'no permission', same as the in-repo evaluator): {ag['malformed']}", f"- run time: {ag['seconds']} s"]
        if ag["exhaustive"]:
            L.append(f"- exhaustive extra check: {ag['exhaustive']['checks']} checks on {ag['exhaustive']['episodes']} "
                     f"episodes, disagreements **{ag['exhaustive']['disagreements']}**")
        L += ["", "**Result: " + ("PASS (0 disagreements)" if ok else "FAIL: see examples; do NOT edit the evaluator to hide them") + "**"]
        for k in ("label_examples", "check_examples", "error_examples"):
            if ag[k]:
                L += ["", f"{k}:", "```", *map(str, ag[k]), "```"]
        if ag["exhaustive"] and ag["exhaustive"]["examples"]:
            L += ["", "exhaustive examples:", "```", *map(str, ag["exhaustive"]["examples"]), "```"]
        open("spicedb_agreement.md", "w").write("\n".join(L) + "\n")
    if lat:
        f = lambda s: f"| {s['n']} | {s['p50']:.3f} | {s['p95']:.3f} | {s['p99']:.3f} | {s['mean']:.3f} | {s['max']:.3f} |"
        L = ["# Check latency and H3", "", f"Environment: `{json.dumps(env)}`", "",
             "Pre-registered H3 criterion: for arm C, gateway time per episode (checks per episode x p50 fully-consistent check) < 5% of mean model time per episode.", "",
             "| check type | n | p50 ms | p95 ms | p99 ms | mean ms | max ms |", "|---|---|---|---|---|---|---|",
             "| SpiceDB, fully_consistent " + f(lat["fully_consistent"]),
             "| SpiceDB, minimize_latency " + f(lat["minimize_latency"]),
             "| in-repo evaluator (MICROSECONDS, python) " + f(lat["in_repo_ref_us"]), "",
             f"Bulk check per tool call: {lat['bulk_per_tool_call']}", "",
             "| arm | episodes | tool calls | checks/call | checks/episode | gateway ms/episode | model s/episode | overhead % of model time |",
             "|---|---|---|---|---|---|---|---|"]
        for arm, p in lat["per_arm"].items():
            L.append(f"| {arm} | {p['episodes']} | {p['tool_calls']} | {p['checks_per_call']:.2f} | {p['checks_per_episode']:.2f} | "
                     f"{p['gateway_ms_per_episode']:.2f} | {p['model_s_per_episode']:.2f} | {p['overhead_pct_of_model_time']:.3f} |")
        if lat["H3_C_overhead_pct"] is not None:
            L += ["", f"**H3 (arm C): overhead = {lat['H3_C_overhead_pct']:.3f}% of model time -> "
                  + ("SUPPORTED" if lat["H3_supported_by_preregistered_criterion"] else "NOT SUPPORTED")
                  + " by the pre-registered criterion.**"]
        L += ["", "Caveats: arm A-Ctx has no gateway at runtime (its row only counts checks the labeler would issue). Model time was measured on Kaggle T4 GPUs, partly with two evaluation processes sharing one machine. SpiceDB ran locally.", ""]
        open("latency.md", "w").write("\n".join(L) + "\n")
    json.dump({"env": env, "agreement": ag, "latency": lat}, open("spicedb_results.json", "w"), indent=1, default=str)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["agree", "latency", "all"])
    ap.add_argument("--host", default="localhost:50051")
    ap.add_argument("--token", default="permbench")
    ap.add_argument("--results", default="results")
    ap.add_argument("--tests", default="data/test_episodes.json")
    ap.add_argument("--spicedb-version", default="")
    ap.add_argument("--exhaustive", type=int, default=0)
    a = ap.parse_args()
    eps, arms, secs = load_everything(a.results, a.tests)
    print(f"episodes={len(eps)} arms={ {k: len(v) for k, v in arms.items()} }")
    tenants = collections.defaultdict(set)
    for e in eps.values():
        tenants[e.tenant].add(frozenset(e.tuples))
    assert all(len(v) == 1 for v in tenants.values()), "two episodes share a tenant with different tuples: they would collide in SpiceDB. STOP."
    trace = build_trace(eps, arms)
    print(f"trace: {len(trace)} tool calls, {sum(len(t['checks']) for t in trace)} checks")
    spice = Spice(a.host, a.token)
    spice.load(pb.spicedb_schema(), sorted({t for e in eps.values() for t in e.tuples}))
    print("schema + tuples loaded")
    ag = stage_agree(spice, eps, trace, a.exhaustive) if a.stage in ("agree", "all") else None
    if ag:
        print("AGREE:", {k: v for k, v in ag.items() if k in ("calls", "label_disagreements", "unique_checks", "check_disagreements", "rpc_errors", "malformed")})
    lat = stage_latency(spice, eps, trace, secs) if a.stage in ("latency", "all") else None
    if lat:
        print("LATENCY ms (fully_consistent) p50/p95:", round(lat["fully_consistent"]["p50"], 3), round(lat["fully_consistent"]["p95"], 3))
    write_reports(env_record(a), ag, lat)
    print("wrote spicedb_agreement.md / latency.md / spicedb_results.json")
    if ag and (ag["label_disagreements"] or ag["check_disagreements"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
