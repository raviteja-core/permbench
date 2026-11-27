# Check latency and H3

Environment: `{"python": "3.10.12", "platform": "Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.35", "machine": "x86_64", "authzed_pkg": "1.25.0", "spicedb_version": "spicedb v1.57.1", "host": "localhost:50051", "datastore_note": "SpiceDB on localhost, testing/in-memory datastore unless you changed it: a LOWER BOUND, not production performance"}`

Pre-registered H3 criterion: for arm C, gateway time per episode (checks per episode x p50 fully-consistent check) < 5% of mean model time per episode.

| check type | n | p50 ms | p95 ms | p99 ms | mean ms | max ms |
|---|---|---|---|---|---|---|
| SpiceDB, fully_consistent | 10000 | 3.313 | 5.277 | 6.265 | 3.501 | 17.819 |
| SpiceDB, minimize_latency | 10000 | 3.101 | 5.286 | 7.057 | 3.325 | 16.568 |
| in-repo evaluator (MICROSECONDS, python) | 10000 | 4.300 | 8.901 | 15.900 | 5.440 | 596.421 |

Bulk check per tool call: failed: _InactiveRpcError: <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.INVALID_ARGUMENT
	details = "validation error: items[0].resource.object_id: does 

| arm | episodes | tool calls | checks/call | checks/episode | gateway ms/episode | model s/episode | overhead % of model time |
|---|---|---|---|---|---|---|---|
| A-Ctx | 400 | 830 | 2.98 | 6.18 | 20.47 | 2.59 | 0.790 |
| B-Ctx-Feedback | 1467 | 3104 | 3.07 | 6.49 | 21.50 | 2.81 | 0.765 |
| B-Ctx-Stop | 1467 | 2481 | 3.50 | 5.92 | 19.61 | 2.35 | 0.833 |
| C | 1468 | 2741 | 2.56 | 4.77 | 15.81 | 2.15 | 0.735 |
| C0 | 1453 | 3444 | 3.30 | 7.83 | 25.96 | 2.87 | 0.905 |

**H3 (arm C): overhead = 0.735% of model time -> SUPPORTED by the pre-registered criterion.**

Caveats: arm A-Ctx has no gateway at runtime (its row only counts checks the labeler would issue). Model time was measured on Kaggle T4 GPUs, partly with two evaluation processes sharing one machine. SpiceDB ran locally.

