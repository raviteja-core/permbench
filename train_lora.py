"""LoRA fine-tune (Setup C) of Qwen3.5 on the permission-aware dataset. Run on an A100/H100/L40S-class GPU.
  python train_lora.py --smoke            # 30 steps: checks template, masking, memory, speed
  python train_lora.py --epochs 2         # full run"""
import argparse, inspect, json, os, time
import torch
from unsloth import FastLanguageModel                       # import unsloth BEFORE trl/transformers
from datasets import Dataset
from trl import SFTTrainer, SFTConfig
from unsloth.chat_templates import train_on_responses_only

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="unsloth/Qwen3.5-4B"); ap.add_argument("--data", default="data/train.jsonl")
ap.add_argument("--dev", default="data/dev.jsonl"); ap.add_argument("--out", default="outputs/qwen35-perm-lora")
ap.add_argument("--max-len", type=int, default=4096); ap.add_argument("--epochs", type=float, default=2)
ap.add_argument("--bs", type=int, default=4); ap.add_argument("--accum", type=int, default=4)
ap.add_argument("--lr", type=float, default=2e-4); ap.add_argument("--rank", type=int, default=32)
ap.add_argument("--smoke", action="store_true"); a = ap.parse_args()

assert torch.cuda.is_available(), "No GPU"
print("GPU:", torch.cuda.get_device_name(0), "| bf16:", torch.cuda.is_bf16_supported())
model, proc = FastLanguageModel.from_pretrained(model_name=a.model, max_seq_length=a.max_len, dtype=None,
                                                load_in_4bit=False, load_in_16bit=True, full_finetuning=False)
tok = getattr(proc, "tokenizer", proc)
if tok.pad_token is None: tok.pad_token = tok.eos_token

peft_kw = dict(r=a.rank, lora_alpha=a.rank, lora_dropout=0, bias="none", use_gradient_checkpointing="unsloth", random_state=3407)
try:   # Qwen3.5 is multimodal: restrict LoRA to the language layers if the API accepts these flags
    model = FastLanguageModel.get_peft_model(model, finetune_vision_layers=False, finetune_language_layers=True,
                                             finetune_attention_modules=True, finetune_mlp_modules=True, **peft_kw)
except TypeError:
    model = FastLanguageModel.get_peft_model(model, target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"], **peft_kw)

def load(path, limit=None):
    rows = [json.loads(l) for l in open(path)][:limit]
    return rows
def render(row):
    return tok.apply_chat_template(row["messages"], tools=row["tools"], tokenize=False, add_generation_prompt=False, enable_thinking=False)

train_rows, dev_rows = load(a.data, 64 * 4 if a.smoke else None), load(a.dev, 64)
# ---- template consistency: the training text must contain the exact inference prompt as a prefix ----
r0 = train_rows[0]; full = render(r0)
first_asst = next(i for i, m in enumerate(r0["messages"]) if m["role"] == "assistant")
prompt = tok.apply_chat_template(r0["messages"][:first_asst], tools=r0["tools"], tokenize=False, add_generation_prompt=True, enable_thinking=False)
assert full.startswith(prompt), "Chat template mismatch between training text and inference prompt!\n--- prompt tail ---\n" + prompt[-300:] + "\n--- train text at same position ---\n" + full[len(prompt) - 300:len(prompt) + 120]
print("template check OK. Example assistant turn in training text:\n", full[len(prompt):len(prompt) + 260].replace("\n", "\\n"))

ds = Dataset.from_list([{"text": render(r)} for r in train_rows]); dd = Dataset.from_list([{"text": render(r)} for r in dev_rows])
lens = [len(tok(t["text"]).input_ids) for t in ds.select(range(min(300, len(ds))))]
print(f"real token lengths: mean {sum(lens)//len(lens)}, max {max(lens)} (limit {a.max_len})"); assert max(lens) < a.max_len, "sequences exceed --max-len"

cfg_fields = set(inspect.signature(SFTConfig).parameters)
len_key = "max_length" if "max_length" in cfg_fields else "max_seq_length"
cfg = SFTConfig(output_dir=a.out, per_device_train_batch_size=a.bs, gradient_accumulation_steps=a.accum, warmup_steps=20,
                num_train_epochs=a.epochs, max_steps=30 if a.smoke else -1, learning_rate=a.lr, lr_scheduler_type="cosine",
                weight_decay=0.01, optim="adamw_8bit", bf16=torch.cuda.is_bf16_supported(), fp16=not torch.cuda.is_bf16_supported(),
                logging_steps=5, save_strategy="steps", save_steps=200, save_total_limit=3, eval_strategy="steps", eval_steps=200,
                per_device_eval_batch_size=a.bs, seed=3407, report_to="none", dataset_text_field="text", packing=False, **{len_key: a.max_len})
trainer = SFTTrainer(model=model, processing_class=tok, train_dataset=ds, eval_dataset=dd, args=cfg)
trainer = train_on_responses_only(trainer, instruction_part="<|im_start|>user\n", response_part="<|im_start|>assistant\n")

lab = trainer.train_dataset[0]["labels"]; ids = trainer.train_dataset[0]["input_ids"]
kept = [i for i, l in zip(ids, lab) if l != -100]
assert 0 < len(kept) < len(ids) * 0.6, "masking looks wrong"
print(f"masking OK: {len(kept)}/{len(ids)} tokens trained. Trained text (first 300 chars):\n", tok.decode(kept)[:300].replace("\n", "\\n"))

FastLanguageModel.for_training(model)
t0 = time.time(); trainer.train(); print(f"train time {time.time() - t0:.0f}s | peak GPU mem {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB")
if not a.smoke:
    model.save_pretrained(a.out); tok.save_pretrained(a.out); print("saved LoRA adapter ->", a.out)
    try: model.save_pretrained_merged(a.out + "-merged", tok, save_method="merged_16bit"); print("saved merged model ->", a.out + "-merged")
    except Exception as e: print("merged save skipped:", e)
