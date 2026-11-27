"""Evaluate setups on the frozen test set.
  python eval_models.py --model unsloth/Qwen3.5-4B --setups A B-Stop B-Feedback C0 --tag base
  python eval_models.py --model outputs/qwen35-perm-lora --setups C --tag lora
Use --limit 100 first as a smoke test."""
import argparse, json, os, time
import torch
from unsloth import FastLanguageModel
import permbench as pb

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True); ap.add_argument("--setups", nargs="+", required=True)
ap.add_argument("--episodes", default="data/test_episodes.json"); ap.add_argument("--tag", required=True)
ap.add_argument("--limit", type=int, default=None); ap.add_argument("--start", type=int, default=0); ap.add_argument("--batch", type=int, default=32)
ap.add_argument("--max-new", type=int, default=220); ap.add_argument("--max-len", type=int, default=6144); a = ap.parse_args()

eps = pb.load_episodes(a.episodes)[a.start:(a.start + a.limit) if a.limit else None]
model, proc = FastLanguageModel.from_pretrained(model_name=a.model, max_seq_length=a.max_len, dtype=None, load_in_4bit=False, load_in_16bit=True)
tok = getattr(proc, "tokenizer", proc); tok.padding_side = "left"
if tok.pad_token is None: tok.pad_token = tok.eos_token
FastLanguageModel.for_inference(model)

def render(msgs, tools):
    return tok.apply_chat_template(msgs, tools=tools, tokenize=False, add_generation_prompt=True, enable_thinking=False)
@torch.no_grad()
def generate_batch(prompts):
    enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
    out = model.generate(**enc, max_new_tokens=a.max_new, do_sample=False, use_cache=True, pad_token_id=tok.pad_token_id)
    return tok.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)

os.makedirs("results", exist_ok=True)
policy = pb.BatchingPolicy(generate_batch, render, max_batch=a.batch)
for setup in a.setups:
    t0 = time.time(); res = pb.evaluate_parallel(eps, policy, setup, workers=a.batch * 2)
    res["seconds"] = time.time() - t0; res["setup"], res["tag"], res["model"], res["n"] = setup, a.tag, a.model, len(eps)
    json.dump(res, open(f"results/{a.tag}_{setup}.json", "w"))
    m = res["overall"]; print(f"[{setup}] " + " ".join(f"{k}={v:.3f}" for k, v in m.items() if isinstance(v, float)), f"({res['seconds']:.0f}s)")
