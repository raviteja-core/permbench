# SpiceDB agreement replay

Environment: `{"python": "3.10.12", "platform": "Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.35", "machine": "x86_64", "authzed_pkg": "1.25.0", "spicedb_version": "spicedb v1.57.1", "host": "localhost:50051", "datastore_note": "SpiceDB on localhost, testing/in-memory datastore unless you changed it: a LOWER BOUND, not production performance"}`

- tool calls re-labelled (all arms): **12600**
- label disagreements (in-repo evaluator vs SpiceDB): **0**
- unique (subject, relation, object) checks compared: **7395**
- check disagreements: **0**
- RPC errors (counted as 'no permission'): {'_InactiveRpcError': 194}
- malformed subject/object strings that could not be sent (model-supplied junk such as a user without the 'user:' prefix; counted as 'no permission', same as the in-repo evaluator): 90
- run time: 180.1 s
- exhaustive extra check: 33416 checks on 200 episodes, disagreements **0**

**Result: PASS (0 disagreements)**

error_examples:
```
user:t20760a/judy read doc:t20760a/<doc_id_result_from_previous_response>: <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "validation error: resource.object_id: does not match regex pat
user:t20760a/judy delete doc:t20760a/<doc_id_result_from_second_response>: <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "validation error: resource.object_id: does not match regex pat
user:t20760a/judy read doc:t20760a/<doc-id>: <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "validation error: resource.object_id: does not match regex pat
user:t20760a/judy delete doc:t20760a/<doc-id-outdated-budget>: <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "validation error: resource.object_id: does not match regex pat
user:t20760b/judy read doc:t20760b/<doc-id-output>: <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "validation error: resource.object_id: does not match regex pat
```
