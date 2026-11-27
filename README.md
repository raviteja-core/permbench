# PermBench: Permission-Aware Tool-Calling Agents

PermBench is a benchmark and evaluation suite for studying relationship-based access control (ReBAC) and permission-conditioned tool calling in LLM agents. It generates multi-tenant enterprise tasks (19 tools + 2 infrastructure actions across documents, email, tickets, and invoices) covering 7 failure mode variants (`FM1`, `FM1b`, `FM2`, `FM3a`, `FM3b`, `FM4a`, `FM4b`, plus `ambiguity` and `benign`), and compares gateway-only enforcement against a LoRA fine-tuned model behind the same ReBAC gateway.

## Repository Contents

| File / Folder | Role | Needs GPU |
|---|---|---|
| `permbench.py` | Schema, in-repo ReBAC evaluator (`Ref`), 19 tools + 2 infra, templates, labeler, gateway, harness, metrics | No |
| `gen_data.py` | Generates `data/train.jsonl`, `data/dev.jsonl`, `data/dev_episodes.json`, `data/test_episodes.json`, and runs self-checks & leakage checks | No |
| `baselines.py` | Scripted baseline policies (`oracle`, `obedient`, `always_deny`, `always_abstain`) | No |
| `train_lora.py` | LoRA fine-tuning script (Setup C) with chat-template and response-masking checks | Yes |
| `eval_models.py` | Batched evaluation runner across experimental setups (`A-Ctx`, `B-Ctx-Stop`, `B-Ctx-Feedback`, `C0`, `C`) | Yes |
| `analyze_v04.py` | Detailed breakdowns (failure modes, held-out templates, injection styles, strict vs. lenient task success, write-only UAR) | No |
| `rescore.py` | Merges `results/*.json` per arm with Wilson 95% CIs across common episodes, full test set, and held-out templates | No |
| `relabel_check.py` | Verifies v0.4 ID-resolver consistency across saved logs (`0` unexpected changes) | No |
| `report.py` | Summary table with Wilson 95% intervals from `results/*.json` | No |
| `spicedb_eval.py` | Replays all saved tool calls through a live SpiceDB instance (`agree`) and measures check latency (`latency` / H3) | No |
| `spicedb_diff.py` | Differential correctness test comparing `Ref` against SpiceDB on generated dev/test groups | No |
| `permbench_kaggle_v04.ipynb` | Kaggle T4 x2 evaluation notebook (outputs cleared) | Yes (Kaggle) |
| `results/` | Saved v0.4 evaluation logs (`A-Ctx`, `B-Ctx-Stop`, `B-Ctx-Feedback`, `C0`, `C`) | — |
| `analysis.md`, `rescore.md` | Generated tables from `results/` and `data/test_episodes.json` | — |
| `spicedb_agreement.md`, `latency.md`, `spicedb_results.json` | Generated SpiceDB replay agreement and H3 latency measurements | — |
| `START_HERE.txt` | Original step-by-step laptop verification instructions | — |

## Quickstart (CPU — No GPU or Model Download Required)

Requires **Python 3.9+** (tested on Python `3.10.12`).

### 1. Generate the frozen dataset and verify the hash

```bash
python3 gen_data.py
```

Expected output includes:
- `self-checks passed (labels, gold replay, tool visibility, tenant invariants)`
- `test_episodes.json sha256: 4d80fca654a4f30087ced8ea26662ea0172b555b27d978a77a04ba59111d59dc`
- Dataset counts (`seed=1`): `5,907` train, `321` dev, `1,468` test episodes.

### 2. Reproduce all evaluation tables and checks

```bash
python3 analyze_v04.py results data/test_episodes.json > analysis.md
python3 rescore.py results data/test_episodes.json > rescore.md
python3 relabel_check.py
```

You can also run `python3 report.py` and `python3 baselines.py data/test_episodes.json`.

### 3. SpiceDB Agreement & Latency Validation (Optional, CPU + Docker)

Start SpiceDB in-memory testing mode in one terminal:

```bash
docker run --rm -p 50051:50051 authzed/spicedb serve-testing
```

In a second terminal, install the Python gRPC client and run the evaluation:

```bash
pip install authzed grpcio
python3 spicedb_eval.py all --exhaustive 200 --spicedb-version "spicedb v1.57.1"
```

This writes `spicedb_agreement.md`, `latency.md`, and `spicedb_results.json`:
- **Agreement:** `0` label disagreements across `12,600` tool calls, `0` disagreements across `7,395` unique trace checks, and `0` disagreements across `33,416` exhaustive checks on `200` episodes.
- **Latency (H3):** On localhost `serve-testing`, SpiceDB `fully_consistent` check latency (`n=10,000`) is `3.313 ms` p50 (`5.277 ms` p95). For arm `C` (`4.77` checks/episode, `2.15 s/episode` model time on Kaggle T4), gateway overhead is `0.735%` (`< 5%` pre-registered criterion).

## GPU Training & Evaluation

Training and evaluation were run on **Kaggle T4 x2** GPUs using `unsloth/Qwen2.5-3B-Instruct` (T4 lacks `bf16`, so `Qwen2.5-3B-Instruct` was used instead of `Qwen3.5-4B`; note that `train_lora.py` and `eval_models.py` still keep `unsloth/Qwen3.5-4B` as their CLI default—pass `--model unsloth/Qwen2.5-3B-Instruct` and `--out outputs/qwen25-3b-perm-lora` to reproduce the Kaggle T4 run). See `permbench_kaggle_v04.ipynb` for the exact v0.4 evaluation workflow.

Model weights (`*.safetensors`) are excluded from this repository due to GitHub's 100 MB limit; if released separately (e.g., on Hugging Face), verify the `Qwen2.5-3B-Instruct` license terms before publishing.

## Seeds & Library Versions

- **Seeds:** `seed=1` for dataset generation (`gen_data.py`) and SpiceDB latency sampling (`spicedb_eval.py`); `seed=3407` for LoRA training (`train_lora.py`).
- **Local verification environment:** Python `3.10.12`, `authzed==1.25.0`, `grpcio==1.85.4`, SpiceDB `v1.57.1` (`authzed/spicedb`, `serve-testing`).
- **Kaggle environment specs (`permbench_kaggle_v04.ipynb`):** `unsloth`, `transformers>=5.2.0,<=5.17.0`, `tqdm`, `requests`, `huggingface_hub`.

## Limitations

- **Model scope:** All model results are for `Qwen2.5-3B-Instruct` only (not `Qwen3.5` or larger models).
- **Single run:** Results come from a single training and evaluation run (one seed), without multi-seed variance.
- **Templated language:** Tasks and prompt injections are generated from templates; no LLM-paraphrased or human-written test subset has been evaluated yet.
- **No human label audit:** The planned ~60-call human label audit has not been completed.
- **SpiceDB role:** All Kaggle model runs used the in-repo Zanzibar-style evaluator (`permbench.Ref`) at runtime. SpiceDB (`v1.57.1`, localhost `serve-testing` in-memory datastore) was used post-hoc to validate `Ref` (`0` disagreements) and measure lower-bound check latency, not as the live runtime gateway.
- **Closed-world intent oracle & schema constraints:** Off-task reads are marked unintended by the closed-world intent oracle; `email_send` required a `body` field (penalizing baselines on invalid calls); and lenient task-success scoring (accepting the required number in the answer) was added after inspecting initial outputs (both strict and lenient scores are reported in `analysis.md`).
