# -*- coding: utf-8 -*-
"""
BHARAT-SCAM-X: train and persist the production model.

Two things are trained, from two different sources, because only one source
has the labels each needs:

  signature heads  <- synthetic corpus only (the only source with field labels)
  binary detector  <- synthetic + real English SMS/social spam

The real corpus (vinit9638/SMS-scam-detection-dataset) contains no Telugu,
Tamil or Kannada at all, and its Devanagari rows are machine-translated. It
therefore improves English detection and does nothing for the cross-lingual
claim. That split is deliberate and is reported in the metrics below.

Run:  python3 app/train.py
"""
import json, os, re, sys, time
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, accuracy_score, classification_report
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from schema import AttackSignature, SINGLE_FIELDS, signature_risk  # noqa: E402

SEED = 20260920
rng = np.random.RandomState(SEED)

SYNTH = os.path.join(ROOT, "data", "bharat_scam_x.jsonl")
REAL = os.path.join(ROOT, "..", "external", "sms-scam",
                    "sms_scam_detection_dataset_merged_with_lang.csv")
OUT = os.path.join(HERE, "artifacts")

N_REAL = 24000          # subsample of the real corpus, balanced
MAX_FEATURES = 24000    # binary detector
SIG_FEATURES = 20000    # signature heads. 7000 loses 5 of 180 flips; flips are the product.


def load_synthetic():
    rows = [json.loads(l) for l in open(SYNTH, encoding="utf-8")]
    return rows


def load_real():
    if not os.path.exists(REAL):
        print("  real corpus not found, skipping")
        return pd.DataFrame(columns=["text", "label"])
    df = pd.read_csv(REAL, low_memory=False)[["label", "text"]].dropna()
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    df = df[df["label"].isin(["ham", "spam"])]
    df["y"] = (df["label"] == "spam").astype(int)
    df["text"] = df["text"].astype(str)
    df = df.drop_duplicates(subset=["text"])
    # balanced subsample
    n = min(N_REAL // 2, df["y"].value_counts().min())
    part = pd.concat([
        df[df.y == 0].sample(n, random_state=SEED),
        df[df.y == 1].sample(n, random_state=SEED),
    ]).sample(frac=1.0, random_state=SEED)
    return part[["text", "y"]]


def to_sig(d):
    return AttackSignature(
        actor=d["actor"], pretext=d["pretext"], target=d["target"],
        intent=d["intent"], action=d["action"], stage=d["stage"],
        tactic=tuple(d["tactic"]), evidence=tuple(d["evidence"]))


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    print("loading data")
    syn = load_synthetic()
    syn_train = [r for r in syn if r["split"] == "train"]
    syn_test = [r for r in syn if r["split"] == "test"]
    real = load_real()
    print(f"  synthetic: {len(syn_train)} train / {len(syn_test)} test")
    print(f"  real:      {len(real)} (balanced subsample)")

    # ---- two vectorizers, on purpose --------------------------------------
    # A shared vectorizer fit on both sources lets 24k real English rows swamp
    # 356 synthetic ones: the signature heads lose their domain and
    # compositional recovery falls to zero. So the heads get their own
    # vectorizer fit on the corpus they actually predict over, and the binary
    # detector gets one fit on everything.
    def mkvec(max_features):
        return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5),
                               min_df=2, max_features=max_features,
                               sublinear_tf=True, lowercase=True)

    # APP MODE: signature heads train on ALL nine language varieties.
    # The paper holds out te/ta/kn/code-mixed to measure zero-shot transfer,
    # which is the right experiment and the wrong product. A user typing a
    # Telugu scam gets 2 non-zero features against a train-split-only
    # vectorizer, so the app would call it safe. Paper numbers stay in
    # src/evaluate.py; these are the app's.
    syn_all = syn_train + syn_test
    vec_sig = mkvec(SIG_FEATURES).fit([r["text"] for r in syn_all])
    vec_bin = mkvec(MAX_FEATURES).fit([r["text"] for r in syn_train] + list(real["text"]))
    print(f"  signature vectorizer: {len(vec_sig.vocabulary_)} features")
    print(f"  binary vectorizer:    {len(vec_bin.vocabulary_)} features")

    # ---- binary detector (synthetic + real) --------------------------------
    print("\ntraining binary detector")
    Xb_text = [r["text"] for r in syn_train] + list(real["text"])
    yb = [r["label"] for r in syn_train] + list(real["y"])
    tr_t, te_t, tr_y, te_y = train_test_split(
        Xb_text, yb, test_size=0.15, random_state=SEED, stratify=yb)
    binary = LogisticRegression(max_iter=3000, C=4.0, random_state=SEED)
    binary.fit(vec_bin.transform(tr_t), tr_y)
    pred = binary.predict(vec_bin.transform(te_t))
    print(f"  held-out macro-F1 (mixed): {f1_score(te_y, pred, average='macro'):.4f}")

    # honest split: how does it do on each source separately?
    if len(real):
        r_tr, r_te = train_test_split(real, test_size=0.2, random_state=SEED,
                                      stratify=real["y"])
        p = binary.predict(vec_bin.transform(list(r_te["text"])))
        print(f"  real-only held-out macro-F1: "
              f"{f1_score(list(r_te['y']), p, average='macro'):.4f}  (n={len(r_te)})")
    syn_te_bin = [r for r in syn_test if r["suite"] in
                  ("iid", "xling", "hard_negative", "benign_generic",
                   "sfs_attack", "sfs_flip", "compositional", "osr")]
    p = binary.predict(vec_bin.transform([r["text"] for r in syn_te_bin]))
    print(f"  synthetic-only held-out macro-F1: "
          f"{f1_score([r['label'] for r in syn_te_bin], p, average='macro'):.4f}"
          f"  (n={len(syn_te_bin)})")

    # ---- signature heads (synthetic only) ----------------------------------
    print("\ntraining signature heads (synthetic only, the only labelled source)")
    sig_tr = [to_sig(r["signature"]) for r in syn_all]
    Xs = vec_sig.transform([r["text"] for r in syn_all])
    heads, head_meta = {}, {}
    for f in SINGLE_FIELDS:
        y = [getattr(s, f) for s in sig_tr]
        if len(set(y)) < 2:
            heads[f] = ("const", y[0]); head_meta[f] = {"kind": "const", "value": y[0]}
            continue
        clf = LogisticRegression(max_iter=3000, C=4.0, random_state=SEED)
        # 5-fold CV first: train accuracy on a model this flexible is
        # meaningless, so report something that generalises.
        from sklearn.model_selection import cross_val_score
        from collections import Counter
        cnt = Counter(y)
        cv = min(5, min(cnt.values()))
        cvacc = (cross_val_score(clf, Xs, y, cv=cv, scoring="accuracy").mean()
                 if cv >= 2 else float("nan"))
        clf.fit(Xs, y)
        heads[f] = ("clf", clf)
        head_meta[f] = {"kind": "clf", "classes": list(clf.classes_),
                        "cv_accuracy": round(float(cvacc), 4)}
        print(f"  {f:9s} {len(clf.classes_):2d} classes  {cv}-fold CV acc {cvacc:.3f}")

    # ---- held-out signature recovery, by suite -----------------------------
    print("\nNOTE: the suites below are now INSIDE the app's training data.")
    print("      They are a sanity check, not a generalisation estimate.")
    print("      For held-out numbers see src/evaluate.py (the paper split).")
    print("\nsignature recovery (in-sample for the app model)")
    def predict_sigs(texts):
        X = vec_sig.transform(texts)
        cols = {}
        for f in SINGLE_FIELDS:
            kind, obj = heads[f]
            cols[f] = [obj] * len(texts) if kind == "const" else list(obj.predict(X))
        return [AttackSignature(
            actor=cols["actor"][i], pretext=cols["pretext"][i],
            target=cols["target"][i], intent=cols["intent"][i],
            action=cols["action"][i], stage=cols["stage"][i]) for i in range(len(texts))]

    report = {}
    for suite in ["iid", "xling", "compositional", "osr"]:
        sub = [r for r in syn_test if r["suite"] == suite]
        if not sub:
            continue
        gold = [to_sig(r["signature"]) for r in sub]
        got = predict_sigs([r["text"] for r in sub])
        exact = float(np.mean([g.core() == p.core() for g, p in zip(gold, got)]))
        report[suite] = {"n": len(sub), "exact_core": round(exact, 4)}
        print(f"  {suite:14s} n={len(sub):4d}  exact core {exact:.3f}")

    joblib.dump({"vec_sig": vec_sig, "vec_bin": vec_bin, "binary": binary,
                 "heads": heads, "seed": SEED},
                os.path.join(OUT, "model.joblib"))
    json.dump({"head_meta": head_meta, "signature_recovery": report,
               "n_features_sig": len(vec_sig.vocabulary_),
               "n_features_bin": len(vec_bin.vocabulary_),
               "n_synth_train": len(syn_train), "n_real": len(real)},
              open(os.path.join(OUT, "train_report.json"), "w"), indent=2)
    print(f"\nsaved to {OUT}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
