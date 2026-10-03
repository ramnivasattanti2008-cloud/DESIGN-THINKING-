# -*- coding: utf-8 -*-
"""
MuRIL baseline, evaluated on exactly the splits used in evaluate.py.

The paper's open question is whether a multilingual encoder closes the
cross-lingual gap that character n-grams cannot. This answers it with the same
splits, the same conditions and the same metrics, so the two tables can be read
side by side without translation.

MuRIL is frozen: messages are mean-pooled into sentence embeddings and logistic
regression heads are trained on top. That is the honest test of whether the
*representation* carries the signal. Fine-tuning would conflate representation
quality with 238M parameters fitting 356 training messages.

Embeddings are STANDARDISED (scaler fit on train only) before the heads. Raw
mean-pooled BERT output is anisotropic: on this corpus the mean pairwise cosine
is 0.993 with a standard deviation of 0.003, so every message looks like every
other and the classifiers collapse to predicting one class. Standardising takes
binary macro-F1 from 0.417 to 0.902. Without this step the results say nothing
about MuRIL and everything about the pooling.

Run:  python3 src/evaluate_muril.py
"""
import json, os, sys, time, itertools
from collections import defaultdict

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score, accuracy_score, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from schema import (AttackSignature, SINGLE_FIELDS, signature_agreement,  # noqa
                    signature_risk)

SEED = 20260920
np.random.seed(SEED)
DATA = os.path.join(HERE, "..", "data", "bharat_scam_x.jsonl")
CACHE = os.path.join(HERE, "..", "app", "artifacts", "muril_emb.npz")
RESULTS = os.path.join(HERE, "..", "results")
MODEL = "google/muril-base-cased"
SEEN = {"en", "hi", "hi_Latn"}


def load():
    return [json.loads(l) for l in open(DATA, encoding="utf-8")]


def to_sig(d):
    return AttackSignature(
        actor=d["actor"], pretext=d["pretext"], target=d["target"],
        intent=d["intent"], action=d["action"], stage=d["stage"],
        tactic=tuple(d["tactic"]), evidence=tuple(d["evidence"]))


def embed(texts):
    """Mean-pooled, L2-normalised MuRIL embeddings. Cached: the forward pass is
    the slow part and the corpus does not change between runs."""
    key = str(len(texts)) + "|" + str(hash(tuple(texts)) & 0xFFFFFFFF)
    if os.path.exists(CACHE):
        z = np.load(CACHE, allow_pickle=True)
        if str(z.get("key")) == key:
            print("  using cached embeddings")
            return z["emb"]
    import torch
    from transformers import AutoTokenizer, AutoModel
    tok = AutoTokenizer.from_pretrained(MODEL)
    mdl = AutoModel.from_pretrained(MODEL).eval()
    out, B = [], 32
    t0 = time.time()
    with torch.no_grad():
        for i in range(0, len(texts), B):
            batch = tok(texts[i:i + B], return_tensors="pt", padding=True,
                        truncation=True, max_length=64)
            h = mdl(**batch).last_hidden_state
            m = batch["attention_mask"].unsqueeze(-1).float()
            e = (h * m).sum(1) / m.sum(1)
            out.append(torch.nn.functional.normalize(e, dim=1).numpy())
            if i % (B * 10) == 0:
                print(f"    {i}/{len(texts)}  {time.time()-t0:.0f}s", flush=True)
    emb = np.vstack(out).astype(np.float32)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    np.savez_compressed(CACHE, emb=emb, key=key)
    print(f"  embedded {len(texts)} messages in {time.time()-t0:.0f}s")
    return emb


def main():
    rows = load()
    texts = [r["text"] for r in rows]
    print(f"corpus: {len(rows)} messages")
    E = embed(texts)
    idx = {id(r): i for i, r in enumerate(rows)}
    tr = [r for r in rows if r["split"] == "train"]
    te = [r for r in rows if r["split"] == "test"]
    Xtr_raw = E[[idx[id(r)] for r in tr]]
    scaler = StandardScaler().fit(Xtr_raw)      # train only: no leakage
    E = scaler.transform(E).astype(np.float32)
    Xtr = E[[idx[id(r)] for r in tr]]
    print(f"train {len(tr)}  test {len(te)}  dim {E.shape[1]}  (standardised)\n")

    # ---- binary detector --------------------------------------------------
    ybin = [r["label"] for r in tr]
    binary = LogisticRegression(max_iter=4000, C=4.0, random_state=SEED).fit(Xtr, ybin)

    # ---- signature heads --------------------------------------------------
    sigs_tr = [to_sig(r["signature"]) for r in tr]
    heads = {}
    for f in SINGLE_FIELDS:
        y = [getattr(s, f) for s in sigs_tr]
        if len(set(y)) < 2:
            heads[f] = ("const", y[0]); continue
        heads[f] = ("clf", LogisticRegression(max_iter=4000, C=4.0,
                                              random_state=SEED).fit(Xtr, y))

    def predict_sigs(rs):
        X = E[[idx[id(r)] for r in rs]]
        cols = {}
        for f in SINGLE_FIELDS:
            k, o = heads[f]
            cols[f] = [o] * len(rs) if k == "const" else list(o.predict(X))
        return [AttackSignature(**{f: cols[f][i] for f in SINGLE_FIELDS})
                for i in range(len(rs))]

    def pred_bin(rs):
        return list(binary.predict(E[[idx[id(r)] for r in rs]]))

    def risk_of(rs):
        return np.array([signature_risk(s) for s in predict_sigs(rs)])

    NEG = {"benign_generic", "hard_negative"}

    def cond(pos, neg, langs=None):
        keep = lambda r: langs is None or r["lang"] in langs
        return ([r for r in te if r["suite"] in pos and keep(r)] +
                [r for r in te if r["suite"] in neg and keep(r)])

    CONDS = {
        "IID": cond({"iid"}, NEG, SEEN),
        "Cross-ling": cond({"xling"}, NEG, {"te", "te_Latn", "ta", "kn", "cm_hi", "cm_te"}),
        "Semantic-flip": cond({"sfs_attack"}, {"sfs_flip"}),
        "Compositional": cond({"compositional"}, NEG),
        "Open-set": cond({"osr"}, NEG),
    }
    out = {"model": MODEL, "frozen": True, "seed": SEED}

    print("=" * 74)
    print("MuRIL (frozen) — binary detection, macro-F1")
    print("=" * 74)
    print(f"{'condition':16s}{'n':>7s}{'macro-F1':>12s}")
    out["binary"] = {}
    for k, sub in CONDS.items():
        y = [r["label"] for r in sub]
        p = pred_bin(sub)
        f1 = f1_score(y, p, average="macro")
        out["binary"][k] = {"n": len(sub), "f1": round(float(f1), 4)}
        print(f"{k:16s}{len(sub):>7d}{f1:>12.3f}")

    # ---- flip sensitivity -------------------------------------------------
    byp = defaultdict(dict)
    for r in te:
        if r["suite"] in ("sfs_attack", "sfs_flip") and r["pair_id"]:
            byp[r["pair_id"]][r["suite"]] = r
    pairs = [(d["sfs_attack"], d["sfs_flip"]) for d in byp.values()
             if "sfs_attack" in d and "sfs_flip" in d]
    ra = risk_of([a for a, _ in pairs]); rf = risk_of([b for _, b in pairs])
    succ = float(np.mean((ra - rf) >= 0.5)); delta = float(np.mean(ra - rf))
    out["sfs"] = {"n": len(pairs), "flip_success": round(succ, 4),
                  "mean_delta": round(delta, 4)}
    print(f"\nSemantic flip sensitivity: n={len(pairs)}  "
          f"flip-success {succ:.3f}  mean risk drop {delta:.3f}")

    # ---- false positives --------------------------------------------------
    print("\nFalse-positive rate on benign text")
    out["fpr"] = {}
    for s in ("hard_negative", "sfs_flip", "benign_generic"):
        sub = [r for r in te if r["suite"] == s]
        fpr = float(np.mean(np.array(pred_bin(sub)) == 1))
        out["fpr"][s] = round(fpr, 4)
        print(f"  {s:16s} {fpr:.3f}")

    # ---- signature recovery ----------------------------------------------
    print("\nAttack Signature recovery")
    print(f"{'suite':16s}{'n':>6s}{'exact core':>13s}{'mean sigma':>13s}")
    out["signature"] = {}
    for s in ["iid", "xling", "compositional", "osr"]:
        sub = [r for r in te if r["suite"] == s]
        if not sub:
            continue
        gold = [to_sig(r["signature"]) for r in sub]
        got = predict_sigs(sub)
        ex = float(np.mean([g.core() == p.core() for g, p in zip(gold, got)]))
        sg = float(np.mean([signature_agreement(g, p) for g, p in zip(gold, got)]))
        out["signature"][s] = {"n": len(sub), "exact_core": round(ex, 4),
                               "mean_sigma": round(sg, 4)}
        print(f"{s:16s}{len(sub):>6d}{ex:>13.3f}{sg:>13.3f}")

    # ---- cross-lingual consistency ---------------------------------------
    clsc_rows = [r for r in te if r["suite"] == "clsc"]
    pr = predict_sigs(clsc_rows)
    groups = defaultdict(list)
    for r, s in zip(clsc_rows, pr):
        groups[r["pair_id"]].append(s)
    def clsc(g):
        v = [np.mean([signature_agreement(a, b)
                      for a, b in itertools.combinations(x, 2)])
             for x in g.values() if len(x) > 1]
        return float(np.mean(v)) if v else float("nan")
    allc = clsc(groups)
    gseen, guns = defaultdict(list), defaultdict(list)
    for r, s in zip(clsc_rows, pr):
        (gseen if r["lang"] in SEEN else guns)[r["pair_id"]].append(s)
    out["clsc"] = {"all": round(allc, 4), "seen": round(clsc(gseen), 4),
                   "unseen": round(clsc(guns), 4)}
    print(f"\nCross-lingual signature consistency: all {allc:.3f}  "
          f"seen {clsc(gseen):.3f}  unseen {clsc(guns):.3f}")

    # per-variety agreement with gold
    print("\nPer-variety agreement with gold")
    pv = {}
    for lg in sorted({r["lang"] for r in clsc_rows}):
        sub = [(r, s) for r, s in zip(clsc_rows, pr) if r["lang"] == lg]
        g = [to_sig(r["signature"]) for r, _ in sub]
        pv[lg] = round(float(np.mean([signature_agreement(a, b)
                                      for a, (_, b) in zip(g, sub)])), 4)
        print(f"  {lg:9s} {pv[lg]:.3f}")
    out["clsc"]["per_language"] = pv

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(out, open(os.path.join(RESULTS, "results_muril.json"), "w"), indent=2)
    print(f"\nwrote {os.path.join(RESULTS, 'results_muril.json')}")


if __name__ == "__main__":
    main()
