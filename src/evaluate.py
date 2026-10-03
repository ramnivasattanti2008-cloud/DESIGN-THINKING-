# -*- coding: utf-8 -*-
"""
BHARAT-SCAM-X evaluation harness.

Runs four baselines over the probe corpus and reports the five diagnostic
metrics defined in the paper.  All numbers printed here are produced by this
script; nothing is hand-entered.

Run:  python3 src/evaluate.py
"""
import json, os, re, math, itertools, random
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.metrics import f1_score, accuracy_score, roc_auc_score

from schema import (AttackSignature, SINGLE_FIELDS, MULTI_FIELDS,
                    signature_agreement, signature_risk)

SEED = 20260920
random.seed(SEED); np.random.seed(SEED)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "bharat_scam_x.jsonl")
RESULTS = os.path.join(HERE, "..", "results")


def load():
    with open(DATA, encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def to_sig(d):
    return AttackSignature(
        actor=d["actor"], pretext=d["pretext"], target=d["target"],
        intent=d["intent"], action=d["action"], stage=d["stage"],
        tactic=tuple(d["tactic"]), evidence=tuple(d["evidence"]))


# ---------------------------------------------------------------------------
# Baseline 1: keyword rule  (the strawman the paper argues against)
# ---------------------------------------------------------------------------
KEYWORDS = [
    r"otp", r"kyc", r"pin\b", r"cvv", r"bank", r"account", r"block",
    r"urgent", r"immediate", r"verify", r"click", r"link", r"upi",
    r"refund", r"prize", r"win", r"arrest", r"parcel", r"customs",
    r"bit\.ly", r"tinyurl", r"anydesk", r"rs\s?\d", r"₹",
    # Devanagari / Telugu / Tamil / Kannada surface cues
    r"ओटीपी", r"केवाईसी", r"खाता", r"रुपये", r"तुरंत",
    r"ఓటీపీ", r"కేవైసీ", r"ఖాతా", r"రూపాయ", r"వెంటనే",
    r"ஓடிபி", r"கேஒய்சி", r"கணக்கு", r"ரூபாய்",
    r"ಕೆವೈಸಿ", r"ಖಾತೆ", r"ರೂಪಾಯಿ",
]
KW_RE = [re.compile(k, re.I) for k in KEYWORDS]


def keyword_score(text, thresh=2):
    hits = sum(1 for r in KW_RE if r.search(text))
    return hits, int(hits >= thresh)


# ---------------------------------------------------------------------------
# Baseline 2/3: lexical classifiers
# ---------------------------------------------------------------------------
def make_word_lr():
    return make_pipeline(
        TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True),
        LogisticRegression(max_iter=2000, C=4.0, random_state=SEED))


def make_char_lr():
    return make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1, sublinear_tf=True),
        LogisticRegression(max_iter=2000, C=4.0, random_state=SEED))


# ---------------------------------------------------------------------------
# Baseline 4: structured signature predictor
#   one classifier per signature field; risk derived from the predicted tuple
# ---------------------------------------------------------------------------
class StructuredSignatureModel:
    def __init__(self, make_clf=make_char_lr):
        self.make_clf = make_clf
        self.heads = {}

    def fit(self, texts, sigs):
        for f in SINGLE_FIELDS:
            y = [getattr(s, f) for s in sigs]
            if len(set(y)) < 2:
                self.heads[f] = ("const", y[0]); continue
            clf = self.make_clf(); clf.fit(texts, y)
            self.heads[f] = ("clf", clf)
        return self

    def predict_sig(self, texts):
        cols = {}
        for f in SINGLE_FIELDS:
            kind, obj = self.heads[f]
            cols[f] = [obj] * len(texts) if kind == "const" else list(obj.predict(texts))
        out = []
        for i in range(len(texts)):
            out.append(AttackSignature(
                actor=cols["actor"][i], pretext=cols["pretext"][i],
                target=cols["target"][i], intent=cols["intent"][i],
                action=cols["action"][i], stage=cols["stage"][i],
                tactic=(), evidence=()))
        return out

    def predict_risk(self, texts):
        return np.array([signature_risk(s) for s in self.predict_sig(texts)])

    def predict_binary(self, texts):
        return (self.predict_risk(texts) > 0.5).astype(int)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def token_jaccard(a, b):
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    return len(ta & tb) / max(1, len(ta | tb))


def suite_binary(rows, pred):
    y = np.array([r["label"] for r in rows])
    p = np.array(pred)
    if len(set(y)) < 2:
        # single-class suite: report accuracy and (if benign) false-positive rate
        acc = accuracy_score(y, p)
        fpr = float(np.mean(p == 1)) if y[0] == 0 else None
        return {"n": len(y), "acc": round(acc, 4), "f1": None, "fpr": None if fpr is None else round(fpr, 4)}
    return {"n": len(y), "acc": round(accuracy_score(y, p), 4),
            "f1": round(f1_score(y, p, average="macro"), 4), "fpr": None}


def clsc_metric(rows, pred_sigs):
    """Cross-Lingual Signature Consistency: mean pairwise agreement within a
    parallel group, averaged over groups."""
    groups = defaultdict(list)
    for r, s in zip(rows, pred_sigs):
        groups[r["pair_id"]].append(s)
    vals = []
    for pid, sigs in groups.items():
        if len(sigs) < 2:
            continue
        ps = [signature_agreement(a, b) for a, b in itertools.combinations(sigs, 2)]
        vals.append(sum(ps) / len(ps))
    return float(np.mean(vals)) if vals else float("nan")


def sfs_metric(pairs, risk_fn):
    """
    Semantic Flip Sensitivity.
      flip_success: fraction of pairs where risk(attack) - risk(flip) >= 0.5
      mean_delta  : mean risk drop
      jaccard     : mean token overlap of the pair (minimality evidence)
    """
    succ, deltas, jacs = [], [], []
    for a, b in pairs:
        ra, rb = risk_fn(a["text"]), risk_fn(b["text"])
        deltas.append(ra - rb)
        succ.append(1.0 if (ra - rb) >= 0.5 else 0.0)
        jacs.append(token_jaccard(a["text"], b["text"]))
    return {"n": len(pairs),
            "flip_success": round(float(np.mean(succ)), 4),
            "mean_delta": round(float(np.mean(deltas)), 4),
            "mean_jaccard": round(float(np.mean(jacs)), 4)}


def sig_accuracy(gold_sigs, pred_sigs):
    exact = np.mean([g.core() == p.core() for g, p in zip(gold_sigs, pred_sigs)])
    per_field = {f: round(float(np.mean([getattr(g, f) == getattr(p, f)
                                         for g, p in zip(gold_sigs, pred_sigs)])), 4)
                 for f in SINGLE_FIELDS}
    mean_sigma = np.mean([signature_agreement(g, p) for g, p in zip(gold_sigs, pred_sigs)])
    return {"exact_core": round(float(exact), 4),
            "mean_sigma": round(float(mean_sigma), 4), "per_field": per_field}


# ---------------------------------------------------------------------------
def main():
    rows = load()
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    Xtr = [r["text"] for r in train]
    ytr = [r["label"] for r in train]
    sig_tr = [to_sig(r["signature"]) for r in train]

    print(f"train n={len(train)}  test n={len(test)}\n")

    # ---- fit models ------------------------------------------------------
    word_lr = make_word_lr().fit(Xtr, ytr)
    char_lr = make_char_lr().fit(Xtr, ytr)
    struct = StructuredSignatureModel().fit(Xtr, sig_tr)

    MODELS = {
        "Keyword-Rule": lambda X: [keyword_score(t)[1] for t in X],
        "TFIDF-Word-LR": lambda X: list(word_lr.predict(X)),
        "TFIDF-Char-LR": lambda X: list(char_lr.predict(X)),
        "Struct-Sig-Char": lambda X: list(struct.predict_binary(X)),
    }
    RISK = {
        "Keyword-Rule": lambda t: min(1.0, keyword_score(t)[0] / 4.0),
        "TFIDF-Word-LR": lambda t: float(word_lr.predict_proba([t])[0][1]),
        "TFIDF-Char-LR": lambda t: float(char_lr.predict_proba([t])[0][1]),
        "Struct-Sig-Char": lambda t: float(struct.predict_risk([t])[0]),
    }

    out = {"config": {"seed": SEED, "n_train": len(train), "n_test": len(test)}}

    # ---- 1. binary performance per evaluation CONDITION -------------------
    # Each condition mixes attack and benign items, so macro-F1 is meaningful
    # and a degenerate all-positive predictor cannot score well.
    SEEN = {"en", "hi", "hi_Latn"}
    NEG_SUITES = {"benign_generic", "hard_negative"}

    def cond(pos_suites, neg_suites, langs=None):
        def keep(r):
            return langs is None or r["lang"] in langs
        pos = [r for r in test if r["suite"] in pos_suites and keep(r)]
        neg = [r for r in test if r["suite"] in neg_suites and keep(r)]
        return pos + neg

    CONDITIONS = {
        "IID":          cond({"iid"}, NEG_SUITES, SEEN),
        "Cross-ling":   cond({"xling"}, NEG_SUITES,
                             {"te", "te_Latn", "ta", "kn", "cm_hi", "cm_te"}),
        "Semantic-flip": cond({"sfs_attack"}, {"sfs_flip"}),
        "Compositional": cond({"compositional"}, NEG_SUITES),
        "Open-set":     cond({"osr"}, NEG_SUITES),
    }
    out["conditions"] = {k: {"n": len(v),
                             "n_pos": sum(1 for r in v if r["label"] == 1),
                             "n_neg": sum(1 for r in v if r["label"] == 0)}
                         for k, v in CONDITIONS.items()}

    out["binary"] = {}
    print("=" * 78)
    print("TABLE 1  Binary detection, macro-F1 (each condition mixes attack + benign)")
    print("=" * 78)
    print(f"{'model':17s}" + "".join(f"{k:>14s}" for k in CONDITIONS))
    for name, fn in MODELS.items():
        out["binary"][name] = {}
        line = f"{name:17s}"
        for k, sub in CONDITIONS.items():
            m = suite_binary(sub, fn([r["text"] for r in sub]))
            out["binary"][name][k] = m
            line += f"{m['f1']:>14.3f}"
        print(line)
    print("\n  condition sizes: " + "  ".join(
        f"{k} n={v['n']} (+{v['n_pos']}/-{v['n_neg']})" for k, v in out["conditions"].items()))

    # ---- 1b. false-positive rate on benign probes -------------------------
    print("\n" + "=" * 78)
    print("TABLE 1b  False-positive rate on benign text (lower is better)")
    print("=" * 78)
    print(f"{'model':17s}{'hard negatives':>18s}{'semantic flips':>18s}{'generic benign':>18s}")
    out["fpr"] = {}
    for name, fn in MODELS.items():
        out["fpr"][name] = {}
        line = f"{name:17s}"
        for s in ("hard_negative", "sfs_flip", "benign_generic"):
            sub = [r for r in test if r["suite"] == s]
            p = fn([r["text"] for r in sub])
            fpr = float(np.mean(np.array(p) == 1))
            out["fpr"][name][s] = round(fpr, 4)
            line += f"{fpr:>18.3f}"
        print(line)

    # ---- 2. semantic flip sensitivity ------------------------------------
    by_pair = defaultdict(dict)
    for r in test:
        if r["suite"] in ("sfs_attack", "sfs_flip") and r["pair_id"]:
            by_pair[r["pair_id"]][r["suite"]] = r
    pairs = [(d["sfs_attack"], d["sfs_flip"]) for d in by_pair.values()
             if "sfs_attack" in d and "sfs_flip" in d]

    print("\n" + "=" * 74)
    print("TABLE 2  Semantic Flip Sensitivity")
    print("=" * 74)
    print(f"{'model':17s}{'n':>6s}{'flip-success':>15s}{'mean risk drop':>17s}{'token overlap':>16s}")
    out["sfs"] = {}
    for name in MODELS:
        m = sfs_metric(pairs, RISK[name])
        out["sfs"][name] = m
        print(f"{name:17s}{m['n']:>6d}{m['flip_success']:>15.3f}"
              f"{m['mean_delta']:>17.3f}{m['mean_jaccard']:>16.3f}")

    # ---- 3. cross-lingual signature consistency --------------------------
    clsc_rows = [r for r in test if r["suite"] == "clsc"]
    pred = struct.predict_sig([r["text"] for r in clsc_rows])
    clsc_all = clsc_metric(clsc_rows, pred)
    seen = {"en", "hi", "hi_Latn"}
    sub_seen = [(r, s) for r, s in zip(clsc_rows, pred) if r["lang"] in seen]
    sub_uns = [(r, s) for r, s in zip(clsc_rows, pred) if r["lang"] not in seen]
    clsc_seen = clsc_metric([r for r, _ in sub_seen], [s for _, s in sub_seen])
    clsc_uns = clsc_metric([r for r, _ in sub_uns], [s for _, s in sub_uns])
    out["clsc"] = {"all": round(clsc_all, 4), "seen_langs": round(clsc_seen, 4),
                   "unseen_langs": round(clsc_uns, 4)}
    print("\n" + "=" * 74)
    print("TABLE 3  Cross-Lingual Signature Consistency (Struct-Sig-Char)")
    print("=" * 74)
    print(f"  all 9 varieties        CLSC = {clsc_all:.3f}")
    print(f"  seen varieties only    CLSC = {clsc_seen:.3f}")
    print(f"  unseen varieties only  CLSC = {clsc_uns:.3f}")

    # ---- 4. signature accuracy by suite ----------------------------------
    print("\n" + "=" * 74)
    print("TABLE 4  Attack Signature recovery (Struct-Sig-Char)")
    print("=" * 74)
    out["signature"] = {}
    print(f"{'suite':16s}{'n':>6s}{'exact core':>13s}{'mean sigma':>13s}"
          f"{'actor':>9s}{'intent':>9s}{'action':>9s}")
    for s in ["iid", "xling", "compositional", "osr"]:
        sub = [r for r in test if r["suite"] == s]
        if not sub:
            continue
        gold = [to_sig(r["signature"]) for r in sub]
        pr = struct.predict_sig([r["text"] for r in sub])
        m = sig_accuracy(gold, pr)
        out["signature"][s] = m
        print(f"{s:16s}{len(sub):>6d}{m['exact_core']:>13.3f}{m['mean_sigma']:>13.3f}"
              f"{m['per_field']['actor']:>9.3f}{m['per_field']['intent']:>9.3f}"
              f"{m['per_field']['action']:>9.3f}")

    # ---- 5. open-set detection -------------------------------------------
    known = [r for r in test if r["suite"] in ("iid", "xling") and r["label"] == 1]
    unknown = [r for r in test if r["suite"] == "osr"]
    print("\n" + "=" * 74)
    print("TABLE 5  Open-set detection of unseen attack families (AUROC)")
    print("=" * 74)
    out["osr"] = {}
    fam_clf = make_char_lr().fit(
        [r["text"] for r in train if r["label"] == 1],
        [r["family"] for r in train if r["label"] == 1])

    def msp(texts):
        return fam_clf.predict_proba(texts).max(axis=1)

    s_known = msp([r["text"] for r in known])
    s_unknown = msp([r["text"] for r in unknown])
    ys = np.r_[np.zeros(len(s_known)), np.ones(len(s_unknown))]
    scores = np.r_[-s_known, -s_unknown]     # low confidence => unknown
    auroc = roc_auc_score(ys, scores)
    out["osr"]["msp_auroc"] = round(float(auroc), 4)
    out["osr"]["n_known"] = len(known); out["osr"]["n_unknown"] = len(unknown)
    print(f"  Maximum-Softmax-Probability over family head")
    print(f"  known n={len(known)}  unknown n={len(unknown)}   AUROC = {auroc:.3f}")
    print(f"  (0.5 = chance. Note this suite is comparatively EASY: the two")
    print(f"   held-out families introduce actor and pretext vocabulary absent")
    print(f"   from training, so novelty is lexically visible. It should not be")
    print(f"   read as evidence that open-set scam detection is solved.)")

    # Per-language CLSC breakdown (reported in the appendix table)
    per_lang = {}
    for lg in sorted({r["lang"] for r in clsc_rows}):
        sub = [(r, s) for r, s in zip(clsc_rows, pred) if r["lang"] == lg]
        gold = [to_sig(r["signature"]) for r, _ in sub]
        per_lang[lg] = round(float(np.mean(
            [signature_agreement(g, p) for g, (_, p) in zip(gold, sub)])), 4)
    out["clsc"]["per_language_vs_gold"] = per_lang
    print("\n" + "=" * 74)
    print("TABLE 6  Per-variety signature agreement with gold (Struct-Sig-Char)")
    print("=" * 74)
    for lg, v in per_lang.items():
        print(f"  {lg:9s} sigma = {v:.3f}")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "results.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {os.path.join(RESULTS,'results.json')}")


if __name__ == "__main__":
    main()
