"""
Stage 1+2 joint training for the Perfumery ML project (plan sections D and G).

Stage 1 — Text + Structured Encoder -> IntentVector (256-d)
  Backbone: sentence-transformers/all-MiniLM-L6-v2 (22M params) — the plan's
  CPU-fast fallback (section D Stage 1); this machine has no CUDA GPU.
  Structured features: age-bucket ordinal embedding, gender/region/background/
  occasion embeddings, descriptor multi-hot (98), avoid multi-hot (11).

Stage 2 — AccordSetPredictor heads on the IntentVector:
  - multi-label sigmoid over all 315 accords (positives = primary + secondary)
    trained with Asymmetric Loss (Ridnik et al. 2021)
  - primary softmax head with class-balanced weights (Cui et al. 2019,
    beta=0.999, from preprocessing 08_class_weights.csv)
  - auxiliary descriptor-reconstruction head (BCE, plan Stage-1 loss b)
  - auxiliary accord-category head (hierarchical loss, plan section D Stage 2)
  - co-occurrence regulariser penalising accord pairs never seen together in
    training targets or the real-perfume catalog

Baseline: TF-IDF + logistic regression on user_text for primary accord —
the floor any encoder must beat (templated text makes this floor high).

Evaluation (plan H.1): micro/macro F1 (multi-label, 0.5 and top-2), primary
top-1/top-3, NDCG@2 against secondary, descriptor-reconstruction F1.

Run:
  python training/run_stage12.py           # full training
  python training/run_stage12.py --smoke   # 300 examples, 1 epoch, sanity only

Outputs:
  training/outputs/*             metrics, predictions, loss curve
  training/checkpoints/*         best model weights (gitignored)
  training/TRAINING_REPORT.md    generated report
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREP_OUT = PROJECT_ROOT / "preprocessing" / "outputs"
TRAIN_ROOT = PROJECT_ROOT / "training"
OUT_DIR = TRAIN_ROOT / "outputs"
CKPT_DIR = TRAIN_ROOT / "checkpoints"
REPORT_PATH = TRAIN_ROOT / "TRAINING_REPORT.md"
MASTER_FILE = PROJECT_ROOT / "perfume_system_master_training_dynamic_v5_augmented.xlsx"

BACKBONE = "sentence-transformers/all-MiniLM-L6-v2"
SEED = 42
MAX_LEN = 64
BATCH_SIZE = 32
EPOCHS = 5
LR_BACKBONE = 3e-5
LR_HEADS = 1e-3
WARMUP_FRAC = 0.1
INTENT_DIM = 256
EMB_DIM = 8

W_ASL = 1.0
W_PRIMARY_CE = 1.0
# raised 0.3 -> 0.6 after run 1: descriptor recon F1 stalled at 0.86 vs the
# plan's 0.95 sanity floor (H.1) while still climbing at the last epoch
W_DESC_AUX = 0.6
W_CAT_AUX = 0.3
W_COOC = 0.05
# checkpoint selection: top1 + SELECT_DESC_W * descriptor F1, so the saved
# epoch cannot trade the Stage-1 sanity floor away for a marginal top1 gain
SELECT_DESC_W = 0.2

OUT_DIR.mkdir(parents=True, exist_ok=True)
CKPT_DIR.mkdir(parents=True, exist_ok=True)

torch.manual_seed(SEED)
np.random.seed(SEED)


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------

def load_frames():
    proc = pd.read_csv(PREP_OUT / "07_training_processed.csv")
    splits = pd.read_csv(PREP_OUT / "08_splits.csv")
    weights = pd.read_csv(PREP_OUT / "08_class_weights.csv")
    with open(PREP_OUT / "07_input_vocab.json", encoding="utf-8") as f:
        vocab = json.load(f)
    master = pd.ExcelFile(MASTER_FILE)
    accords = master.parse("accords")
    perfume_accord = master.parse("perfume_accord")
    df = proc.merge(splits, on="request_id", how="left")
    return df, weights, vocab, accords, perfume_accord


class Encoded(Dataset):
    def __init__(self, df: pd.DataFrame, tok, vocab, accord_ids, cat_of_accord, categories):
        self.n = len(df)
        enc = tok(df["user_text"].fillna("").tolist(), padding="max_length",
                  truncation=True, max_length=MAX_LEN, return_tensors="pt")
        self.input_ids = enc["input_ids"]
        self.attention_mask = enc["attention_mask"]

        def idx_map(values, options):
            lut = {v: i for i, v in enumerate(options)}
            return torch.tensor([lut.get(str(v), len(options)) for v in values],
                                dtype=torch.long)

        self.age = idx_map(df["age_bucket"], vocab["age_bucket_order"])
        self.gender = idx_map(df["gender"], vocab["gender"])
        self.region = idx_map(df["region"], vocab["region"])
        self.background = idx_map(df["background_tag"], vocab["background_tag"])
        self.occasion = idx_map(df["occasion_tag"], vocab["occasion_tag"])

        desc_cols = [f"desc_{d}" for d in vocab["descriptors"]]
        avoid_cols = [f"avoid_{a}" for a in vocab["avoid_tokens"]]
        self.desc = torch.tensor(df[desc_cols].values, dtype=torch.float32)
        self.avoid = torch.tensor(df[avoid_cols].values, dtype=torch.float32)

        aidx = {a: i for i, a in enumerate(accord_ids)}
        prim = df["target_accord_id_primary"].map(aidx)
        assert prim.notna().all(), "primary target outside accord catalog"
        self.primary = torch.tensor(prim.values, dtype=torch.long)
        multi = torch.zeros((self.n, len(accord_ids)), dtype=torch.float32)
        multi[torch.arange(self.n), self.primary] = 1.0
        sec = df["target_accord_id_secondary"].map(aidx)
        has_sec = sec.notna().to_numpy()
        rows = np.flatnonzero(has_sec)
        multi[rows, sec.to_numpy()[rows].astype(int)] = 1.0
        self.multi = multi
        self.secondary = torch.tensor(
            np.where(has_sec, sec.to_numpy(), -1).astype(np.int64))

        cidx = {c: i for i, c in enumerate(categories)}
        self.category = torch.tensor(
            [cidx[cat_of_accord[a]] for a in df["target_accord_id_primary"]],
            dtype=torch.long)
        self.request_id = df["request_id"].tolist()

    def __len__(self):
        return self.n

    def __getitem__(self, i):
        return {
            "input_ids": self.input_ids[i], "attention_mask": self.attention_mask[i],
            "age": self.age[i], "gender": self.gender[i], "region": self.region[i],
            "background": self.background[i], "occasion": self.occasion[i],
            "desc": self.desc[i], "avoid": self.avoid[i],
            "primary": self.primary[i], "multi": self.multi[i],
            "secondary": self.secondary[i], "category": self.category[i],
        }


# ----------------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------------

class Stage12Model(nn.Module):
    def __init__(self, backbone, vocab, n_accords, n_categories):
        super().__init__()
        self.backbone = backbone
        hid = backbone.config.hidden_size
        # +1 slot for out-of-vocab values at inference time
        self.emb_age = nn.Embedding(len(vocab["age_bucket_order"]) + 1, EMB_DIM)
        self.emb_gender = nn.Embedding(len(vocab["gender"]) + 1, EMB_DIM)
        self.emb_region = nn.Embedding(len(vocab["region"]) + 1, EMB_DIM)
        self.emb_background = nn.Embedding(len(vocab["background_tag"]) + 1, EMB_DIM)
        self.emb_occasion = nn.Embedding(len(vocab["occasion_tag"]) + 1, EMB_DIM)
        self.desc_proj = nn.Linear(len(vocab["descriptors"]), 32)
        self.avoid_proj = nn.Linear(len(vocab["avoid_tokens"]), 16)
        fused = hid + 5 * EMB_DIM + 32 + 16
        self.intent = nn.Sequential(
            nn.Linear(fused, INTENT_DIM), nn.GELU(), nn.LayerNorm(INTENT_DIM))
        self.head_multi = nn.Linear(INTENT_DIM, n_accords)
        self.head_primary = nn.Linear(INTENT_DIM, n_accords)
        self.head_desc = nn.Linear(INTENT_DIM, len(vocab["descriptors"]))
        self.head_category = nn.Linear(INTENT_DIM, n_categories)

    def forward(self, batch):
        out = self.backbone(input_ids=batch["input_ids"],
                            attention_mask=batch["attention_mask"])
        mask = batch["attention_mask"].unsqueeze(-1).float()
        pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        fused = torch.cat([
            pooled,
            self.emb_age(batch["age"]), self.emb_gender(batch["gender"]),
            self.emb_region(batch["region"]), self.emb_background(batch["background"]),
            self.emb_occasion(batch["occasion"]),
            self.desc_proj(batch["desc"]), self.avoid_proj(batch["avoid"]),
        ], dim=1)
        intent = self.intent(fused)
        return {
            "intent": intent,
            "multi_logits": self.head_multi(intent),
            "primary_logits": self.head_primary(intent),
            "desc_logits": self.head_desc(intent),
            "category_logits": self.head_category(intent),
        }


class AsymmetricLoss(nn.Module):
    """Ridnik et al. 2021 (arXiv:2009.14119), default gammas."""

    def __init__(self, gamma_neg=4.0, gamma_pos=0.0, clip=0.05, eps=1e-8):
        super().__init__()
        self.gamma_neg, self.gamma_pos, self.clip, self.eps = gamma_neg, gamma_pos, clip, eps

    def forward(self, logits, targets):
        p = torch.sigmoid(logits)
        p_neg = (p - self.clip).clamp(min=0)
        loss_pos = targets * torch.log(p.clamp(min=self.eps)) * (1 - p) ** self.gamma_pos
        loss_neg = (1 - targets) * torch.log((1 - p_neg).clamp(min=self.eps)) \
            * p_neg ** self.gamma_neg
        return -(loss_pos + loss_neg).sum(dim=1).mean()


def build_cooc_mask(training_df, perfume_accord, accord_ids) -> torch.Tensor:
    """1 where an accord pair has never co-occurred (in training targets or the
    real-perfume catalog); 0 where allowed. Diagonal is allowed."""
    n = len(accord_ids)
    aidx = {a: i for i, a in enumerate(accord_ids)}
    allowed = np.eye(n, dtype=bool)
    pairs = training_df.dropna(subset=["target_accord_id_secondary"])
    for p, s in zip(pairs["target_accord_id_primary"], pairs["target_accord_id_secondary"]):
        if p in aidx and s in aidx:
            allowed[aidx[p], aidx[s]] = allowed[aidx[s], aidx[p]] = True
    for _, g in perfume_accord.groupby("perfume_id"):
        ids = [aidx[a] for a in g["accord_id"] if a in aidx]
        for i in ids:
            for j in ids:
                allowed[i, j] = True
    return torch.tensor(~allowed, dtype=torch.float32)


# ----------------------------------------------------------------------------
# Metrics (plan H.1)
# ----------------------------------------------------------------------------

def evaluate(model, loader, cooc_mask, device):
    model.eval()
    P_multi, P_prim, T_multi, T_prim, T_sec = [], [], [], [], []
    D_pred, D_true = [], []
    with torch.no_grad():
        for batch in loader:
            batch = {k: (v.to(device) if torch.is_tensor(v) else v) for k, v in batch.items()}
            out = model(batch)
            P_multi.append(torch.sigmoid(out["multi_logits"]).cpu())
            P_prim.append(F.softmax(out["primary_logits"], dim=1).cpu())
            T_multi.append(batch["multi"].cpu())
            T_prim.append(batch["primary"].cpu())
            T_sec.append(batch["secondary"].cpu())
            D_pred.append((torch.sigmoid(out["desc_logits"]) > 0.5).float().cpu())
            D_true.append(batch["desc"].cpu())
    P_multi = torch.cat(P_multi).numpy()
    P_prim = torch.cat(P_prim).numpy()
    T_multi = torch.cat(T_multi).numpy()
    T_prim = torch.cat(T_prim).numpy()
    T_sec = torch.cat(T_sec).numpy()
    D_pred = torch.cat(D_pred).numpy()
    D_true = torch.cat(D_true).numpy()

    from sklearn.metrics import f1_score
    pred_05 = (P_multi >= 0.5).astype(int)
    top2 = np.zeros_like(pred_05)
    idx2 = np.argsort(-P_multi, axis=1)[:, :2]
    np.put_along_axis(top2, idx2, 1, axis=1)

    rank = np.argsort(-P_prim, axis=1)
    top1 = (rank[:, 0] == T_prim).mean()
    top3 = np.any(rank[:, :3] == T_prim[:, None], axis=1).mean()

    # NDCG@2 vs secondary (rel: primary=3, secondary=1), over examples with a secondary
    has_sec = T_sec >= 0
    ndcg = np.nan
    if has_sec.any():
        r2 = np.argsort(-P_multi[has_sec], axis=1)[:, :2]
        tp, ts = T_prim[has_sec], T_sec[has_sec]
        rel = (r2 == tp[:, None]) * 3.0 + (r2 == ts[:, None]) * 1.0
        dcg = rel[:, 0] + rel[:, 1] / math.log2(3)
        ndcg = float((dcg / (3.0 + 1.0 / math.log2(3))).mean())

    # macro over the label columns actually present in this split's targets;
    # the raw 315-column macro is structurally depressed by the 115 accords
    # that never appear anywhere (they can only contribute 0)
    active = np.flatnonzero(T_multi.sum(axis=0) > 0)

    return {
        "micro_f1@0.5": float(f1_score(T_multi, pred_05, average="micro", zero_division=0)),
        "macro_f1@0.5": float(f1_score(T_multi, pred_05, average="macro", zero_division=0)),
        "macro_f1@0.5_active": float(f1_score(T_multi[:, active], pred_05[:, active],
                                              average="macro", zero_division=0)),
        "micro_f1@top2": float(f1_score(T_multi, top2, average="micro", zero_division=0)),
        "macro_f1@top2": float(f1_score(T_multi, top2, average="macro", zero_division=0)),
        "macro_f1@top2_active": float(f1_score(T_multi[:, active], top2[:, active],
                                               average="macro", zero_division=0)),
        "primary_top1": float(top1),
        "primary_top3": float(top3),
        "ndcg@2_vs_secondary": ndcg,
        "descriptor_recon_f1": float(f1_score(D_true, D_pred, average="micro",
                                              zero_division=0)),
    }, P_prim


# ----------------------------------------------------------------------------
# Baseline (TF-IDF + logistic regression on user_text)
# ----------------------------------------------------------------------------

def run_baseline(df):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    tr = df[df["split"] == "train"]
    metrics = {}
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=30000)
    Xtr = vec.fit_transform(tr["user_text"].fillna(""))
    clf = LogisticRegression(max_iter=2000, C=4.0, n_jobs=-1)
    clf.fit(Xtr, tr["target_accord_id_primary"])
    for split in ["val", "test"]:
        part = df[df["split"] == split]
        proba = clf.predict_proba(vec.transform(part["user_text"].fillna("")))
        classes = clf.classes_
        rank = np.argsort(-proba, axis=1)
        y = part["target_accord_id_primary"].to_numpy()
        top1 = (classes[rank[:, 0]] == y).mean()
        top3 = np.any(classes[rank[:, :3]] == y[:, None], axis=1).mean()
        metrics[split] = {"primary_top1": float(top1), "primary_top3": float(top3)}
    return metrics


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="300 examples, 1 epoch")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device} | backbone: {BACKBONE}")

    df, weights, vocab, accords, perfume_accord = load_frames()
    accord_ids = sorted(accords["accord_id"])
    cat_of_accord = dict(zip(accords["accord_id"], accords["accord_category"].astype(str)))
    categories = sorted(set(cat_of_accord.values()))
    print(f"label space: {len(accord_ids)} accords | {len(categories)} categories")

    if args.smoke:
        df = (df.groupby("split", group_keys=False)
                .apply(lambda g: g.head(100), include_groups=False)
                .join(df[["split"]]))
        args.epochs = 1
        print(f"SMOKE MODE: {len(df)} examples, 1 epoch")

    print("baseline: TF-IDF + logistic regression ...")
    t0 = time.time()
    baseline = run_baseline(df)
    print(f"  baseline done in {time.time() - t0:.0f}s: {baseline}")

    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BACKBONE)
    backbone = AutoModel.from_pretrained(BACKBONE)
    model = Stage12Model(backbone, vocab, len(accord_ids), len(categories)).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"model params: {n_params / 1e6:.1f}M")

    datasets = {s: Encoded(df[df["split"] == s], tok, vocab, accord_ids,
                           cat_of_accord, categories)
                for s in ["train", "val", "test"]}
    # True rare-class oversampling (plan F.5): inverse-sqrt-frequency sampling
    # weights, tempered so 1-example classes are not repeated to extremes.
    train_counts = torch.bincount(datasets["train"].primary,
                                  minlength=len(accord_ids)).float()
    sample_w = train_counts.clamp(min=1).rsqrt()[datasets["train"].primary]
    sampler = torch.utils.data.WeightedRandomSampler(
        sample_w.double(), num_samples=len(datasets["train"]), replacement=True)
    loaders = {s: DataLoader(d, batch_size=BATCH_SIZE,
                             sampler=(sampler if s == "train" else None),
                             num_workers=0)
               for s, d in datasets.items()}
    print(f"train sampler: inverse-sqrt oversampling, class counts "
          f"{int(train_counts[train_counts > 0].min())}-{int(train_counts.max())}")

    # class-balanced CE weights over the full 315-accord space
    w = np.ones(len(accord_ids), dtype=np.float32)
    wmap = dict(zip(weights["accord_id"], weights["class_balanced_weight_beta0.999"]))
    for i, a in enumerate(accord_ids):
        if a in wmap:
            w[i] = wmap[a]
    ce_weights = torch.tensor(w, device=device)
    cooc_mask = build_cooc_mask(df[df["split"] == "train"], perfume_accord,
                                accord_ids).to(device)
    n_forbidden = int(cooc_mask.sum().item())
    print(f"co-occurrence mask: {n_forbidden} forbidden pairs "
          f"of {len(accord_ids) ** 2}")

    asl = AsymmetricLoss()
    opt = torch.optim.AdamW([
        {"params": model.backbone.parameters(), "lr": LR_BACKBONE},
        {"params": [p for n, p in model.named_parameters()
                    if not n.startswith("backbone")], "lr": LR_HEADS},
    ], weight_decay=0.01)
    total_steps = len(loaders["train"]) * args.epochs
    warmup = max(1, int(WARMUP_FRAC * total_steps))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: s / warmup if s < warmup
        else max(0.0, (total_steps - s) / max(1, total_steps - warmup)))

    history, best = [], {"select_score": -1.0, "epoch": -1}
    ckpt_path = CKPT_DIR / "stage12_best.pt"
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0, running = time.time(), []
        for step, batch in enumerate(loaders["train"], 1):
            batch = {k: (v.to(device) if torch.is_tensor(v) else v)
                     for k, v in batch.items()}
            out = model(batch)
            probs = torch.sigmoid(out["multi_logits"])
            cooc_pen = torch.einsum("bi,ij,bj->b", probs, cooc_mask, probs).mean() \
                / max(1, n_forbidden) * len(accord_ids)
            loss = (W_ASL * asl(out["multi_logits"], batch["multi"])
                    + W_PRIMARY_CE * F.cross_entropy(out["primary_logits"],
                                                     batch["primary"], weight=ce_weights)
                    + W_DESC_AUX * F.binary_cross_entropy_with_logits(
                        out["desc_logits"], batch["desc"])
                    + W_CAT_AUX * F.cross_entropy(out["category_logits"],
                                                  batch["category"])
                    + W_COOC * cooc_pen)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            running.append(float(loss.detach()))
            if step % 50 == 0 or step == len(loaders["train"]):
                print(f"  epoch {epoch} step {step}/{len(loaders['train'])} "
                      f"loss {np.mean(running[-50:]):.4f} "
                      f"({(time.time() - t0) / step:.2f}s/step)", flush=True)
        val_metrics, _ = evaluate(model, loaders["val"], cooc_mask, device)
        print(f"epoch {epoch} val: " + json.dumps(
            {k: round(v, 4) for k, v in val_metrics.items()}))
        history.append({"epoch": epoch, "train_loss": float(np.mean(running)),
                        **{f"val_{k}": v for k, v in val_metrics.items()}})
        select = (val_metrics["primary_top1"]
                  + SELECT_DESC_W * val_metrics["descriptor_recon_f1"])
        if select > best["select_score"]:
            best = {"select_score": select, "epoch": epoch}
            torch.save({"state_dict": model.state_dict(),
                        "accord_ids": accord_ids, "categories": categories,
                        "backbone": BACKBONE, "config": {
                            "max_len": MAX_LEN, "intent_dim": INTENT_DIM,
                            "emb_dim": EMB_DIM}}, ckpt_path)
            print(f"  new best (select {select:.4f} = top1 "
                  f"{val_metrics['primary_top1']:.4f} + {SELECT_DESC_W} * desc_f1 "
                  f"{val_metrics['descriptor_recon_f1']:.4f}) -> {ckpt_path.name}")

    # Final eval with the best checkpoint
    model.load_state_dict(torch.load(ckpt_path, weights_only=False)["state_dict"])
    final = {}
    for split in ["val", "test"]:
        m, P_prim = evaluate(model, loaders[split], cooc_mask, device)
        final[split] = m
        rank = np.argsort(-P_prim, axis=1)[:, :3]
        pred_df = pd.DataFrame({
            "request_id": datasets[split].request_id,
            "true_primary": [accord_ids[i] for i in datasets[split].primary],
            "pred_1": [accord_ids[i] for i in rank[:, 0]],
            "pred_2": [accord_ids[i] for i in rank[:, 1]],
            "pred_3": [accord_ids[i] for i in rank[:, 2]],
            "p_1": np.sort(P_prim, axis=1)[:, -1].round(4),
        })
        pred_df.to_csv(OUT_DIR / f"predictions_{split}.csv", index=False)

    hist_df = pd.DataFrame(history)
    hist_df.to_csv(OUT_DIR / "history.csv", index=False)
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.5))
    ax[0].plot(hist_df["epoch"], hist_df["train_loss"], marker="o")
    ax[0].set(title="train loss", xlabel="epoch")
    ax[1].plot(hist_df["epoch"], hist_df["val_primary_top1"], marker="o", label="top-1")
    ax[1].plot(hist_df["epoch"], hist_df["val_primary_top3"], marker="o", label="top-3")
    ax[1].set(title="val primary accuracy", xlabel="epoch")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "curves.png", dpi=130)

    results = {"baseline": baseline, "model": final, "best_epoch": best["epoch"],
               "n_params": n_params, "backbone": BACKBONE, "smoke": args.smoke,
               "epochs": args.epochs}
    with open(OUT_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nFINAL:", json.dumps(results, indent=2))

    if not args.smoke:
        write_report(results, hist_df)
    print("Done.")


def write_report(results, hist_df):
    b, m = results["baseline"], results["model"]
    lines = [
        "# STAGE 1+2 TRAINING REPORT — Perfumery ML project",
        "",
        f"Generated by `training/run_stage12.py` (seed {SEED}). Joint Stage-1 encoder "
        f"+ Stage-2 accord predictor per plan sections D and G. Backbone: `{BACKBONE}` "
        f"(CPU-fast fallback; no CUDA GPU on this machine), "
        f"{results['n_params'] / 1e6:.1f}M params, best epoch "
        f"{results['best_epoch']}/{results['epochs']}.",
        "",
        "## Results",
        "",
        "| metric | val | test | baseline val | baseline test |",
        "|---|---:|---:|---:|---:|",
    ]
    keys = ["primary_top1", "primary_top3", "micro_f1@0.5", "macro_f1@0.5",
            "macro_f1@0.5_active", "micro_f1@top2", "macro_f1@top2",
            "macro_f1@top2_active", "ndcg@2_vs_secondary",
            "descriptor_recon_f1"]
    for k in keys:
        bv = b.get("val", {}).get(k)
        bt = b.get("test", {}).get(k)
        lines.append(
            f"| {k} | {m['val'][k]:.4f} | {m['test'][k]:.4f} | "
            f"{'' if bv is None else f'{bv:.4f}'} | "
            f"{'' if bt is None else f'{bt:.4f}'} |")
    lines += [
        "",
        "Baseline = TF-IDF (1-2 grams) + logistic regression on `user_text` only.",
        "",
        "## Reading the numbers",
        "",
        "- **Templated-text caveat (EDA section 4, plan section I)**: descriptors leak "
        "verbatim into `user_text` 43% of the time, so all text-driven metrics here are "
        "optimistic upper bounds. The gating eval remains the N=200 real-prompt held-out "
        "set (checkpoint L.7), which is still to be authored.",
        "- The plan's Stage-1 sanity floor is descriptor-reconstruction F1 >= 0.95 "
        f"(observed: {m['val']['descriptor_recon_f1']:.4f} val).",
        "- If the encoder cannot clearly beat the TF-IDF baseline on primary top-1, the "
        "text signal is saturated by templates and Stage-2 gains must come from the "
        "structured features (compare the columns above).",
        "",
        "## Artifacts",
        "",
        "- `training/outputs/metrics.json` — all metrics",
        "- `training/outputs/history.csv`, `training/outputs/curves.png` — loss/accuracy curves",
        "- `training/outputs/predictions_val.csv`, `predictions_test.csv` — top-3 predictions per example",
        "- `training/checkpoints/stage12_best.pt` — best checkpoint (gitignored)",
        "",
        "## Loss composition",
        "",
        f"- Asymmetric multi-label loss (weight {W_ASL}) over 315 accords, positives = primary + secondary",
        f"- Class-balanced primary CE (weight {W_PRIMARY_CE}, beta=0.999 weights from preprocessing)",
        f"- Descriptor-reconstruction BCE aux (weight {W_DESC_AUX}; raised from 0.3 after run 1 missed the 0.95 floor)",
        f"- Accord-category hierarchical CE aux (weight {W_CAT_AUX})",
        f"- Never-co-occurring-pair penalty (weight {W_COOC})",
        "",
        "## Run-2 changes vs run 1",
        "",
        "- Train-time inverse-sqrt-frequency oversampling (`WeightedRandomSampler`, plan F.5) — run 1 only weighted the loss.",
        f"- Checkpoint selected on `top1 + {SELECT_DESC_W} * descriptor_f1`, not top1 alone.",
        "- `macro_f1@*_active` metrics: macro over label columns present in the split, excluding the 115 never-used accords that can only score 0.",
        "- Trained on the v5 augmented workbook: +807 flagged synthetic rows (`is_augmented=1`) bringing every active accord to >= 30 examples, quarantined to the train split. Val/test are identical to run 1, so all numbers are directly comparable.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"report written: {REPORT_PATH}")


if __name__ == "__main__":
    main()
