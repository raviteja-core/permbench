"""Differential test: reference evaluator vs a real SpiceDB (run `spicedb serve-testing` first).
Usage: python spicedb_diff.py [n_groups]   -> prints agreement and any disagreements."""
import sys, random
import permbench as pb
from authzed.api.v1 import (Client, WriteSchemaRequest, WriteRelationshipsRequest, RelationshipUpdate, Relationship,
                            ObjectReference, SubjectReference, CheckPermissionRequest, Consistency, CheckPermissionResponse)
from grpcutil import insecure_bearer_token_credentials

def split_obj(s):
    t, i = s.split(":", 1); return t, i
def to_rel(o, r, s):
    ot, oi = split_obj(o)
    if "#" in s:
        so, sr = s.split("#"); st, si = split_obj(so)
        sub = SubjectReference(object=ObjectReference(object_type=st, object_id=si), optional_relation=sr)
    else:
        st, si = split_obj(s); sub = SubjectReference(object=ObjectReference(object_type=st, object_id=si))
    return RelationshipUpdate(operation=RelationshipUpdate.OPERATION_TOUCH,
                              relationship=Relationship(resource=ObjectReference(object_type=ot, object_id=oi), relation=r, subject=sub))

def main(n=120, host="localhost:50051"):
    c = Client(host, insecure_bearer_token_credentials("diff-test"))
    c.WriteSchema(WriteSchemaRequest(schema=pb.spicedb_schema()))
    eps = pb.build_dataset(n, "dev", seed=7) + pb.build_dataset(n, "test", seed=7)
    ups = [to_rel(*t) for e in eps for t in e.tuples]
    for i in range(0, len(ups), 500):
        c.WriteRelationships(WriteRelationshipsRequest(updates=ups[i:i + 500]))
    checks = dis = 0; mism = []
    for e in eps:
        ref = pb.Ref(e.tuples)
        users = [e.principal] + [f"user:{e.tenant}/{n}" for n in (pb.NAMES_TEST + pb.NAMES_TRAIN)][:8]
        for o, x in e.meta.items():
            t = o.split(":")[0]
            for perm in list(pb.PERMS.get(t, {}).keys()) + list(pb.RELS.get(t, {}).keys()):
                if perm in ("tenant", "parent", "project", "org", "mailbox"): continue
                for u in set(users):
                    ut, ui = split_obj(u); ot, oi = split_obj(o)
                    r = c.CheckPermission(CheckPermissionRequest(
                        consistency=Consistency(fully_consistent=True),
                        resource=ObjectReference(object_type=ot, object_id=oi), permission=perm,
                        subject=SubjectReference(object=ObjectReference(object_type=ut, object_id=ui))))
                    sp = r.permissionship == CheckPermissionResponse.PERMISSIONSHIP_HAS_PERMISSION
                    mine = ref.check(u, perm, o); checks += 1
                    if sp != mine: dis += 1; mism.append((e.id, u, perm, o, "spicedb", sp, "ref", mine))
    print(f"episodes={len(eps)} checks={checks} disagreements={dis}")
    for m in mism[:10]: print(m)
    return dis

if __name__ == "__main__":
    sys.exit(1 if main(int(sys.argv[1]) if len(sys.argv) > 1 else 120) else 0)
