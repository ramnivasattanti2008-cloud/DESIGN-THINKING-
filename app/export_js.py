# -*- coding: utf-8 -*-
"""
Export the trained model to JSON so it runs in the browser with no server.

Only the signature half is exported. The binary detector's vectorizer has
24k features over 24k real messages and would make the page enormous for a
model that, on anything non-English, has no competence anyway.

Everything here is lossy on purpose (coefficient pruning + rounding), so the
script finishes by checking the exported model against the Python one on the
whole corpus. If they disagree, that is reported as a failure, not a warning.

Run:  python3 app/export_js.py
"""
import json, os, sys, math
import numpy as np
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from schema import SINGLE_FIELDS, AttackSignature, signature_risk  # noqa: E402

MODEL = os.path.join(HERE, "artifacts", "model.joblib")
OUT = os.path.join(HERE, "web", "model.json")

PRUNE = 0.01     # drop coefficients smaller than this
ROUND = 6


def char_wb_ngrams(text, nmin=2, nmax=5):
    """
    Reimplementation of sklearn's char_wb analyzer. Must match exactly or the
    browser scores drift from the trained model.

    sklearn pads each whitespace-separated word with one space either side,
    then slides n-grams inside that padded word. When the padded word is
    shorter than n, it emits the padded word once, whole.
    """
    import re as _re
    text = _re.sub(r"\s\s+", " ", text.lower())
    out = []
    for w in text.split():
        w = " " + w + " "
        wlen = len(w)
        for n in range(nmin, nmax + 1):
            offset = 0
            out.append(w[offset:offset + n])
            while offset + n < wlen:
                offset += 1
                out.append(w[offset:offset + n])
            if offset == 0:
                # sklearn stops at the first n that yields a single n-gram,
                # it does NOT keep emitting the whole padded word for larger n
                break
    return out


def main():
    b = joblib.load(MODEL)
    vec, heads = b["vec_sig"], b["heads"]
    vocab = vec.vocabulary_
    idf = vec.idf_
    print(f"vectorizer: {len(vocab)} features")

    # which features any head actually relies on
    used = np.zeros(len(vocab), dtype=bool)
    for f in SINGLE_FIELDS:
        kind, obj = heads[f]
        if kind == "clf":
            used |= (np.abs(obj.coef_) >= PRUNE).any(axis=0)
    keep_idx = np.where(used)[0]
    print(f"features kept after pruning |coef| < {PRUNE}: {len(keep_idx)}")

    remap = {int(old): i for i, old in enumerate(keep_idx)}
    inv = {v: k for k, v in vocab.items()}
    kept_vocab = {inv[int(o)]: i for o, i in remap.items()}
    kept_idf = [round(float(idf[int(o)]), ROUND) for o in keep_idx]

    out_heads = {}
    for f in SINGLE_FIELDS:
        kind, obj = heads[f]
        if kind == "const":
            out_heads[f] = {"kind": "const", "value": obj}
            continue
        C = obj.coef_[:, keep_idx]
        C = np.where(np.abs(C) < PRUNE, 0.0, C)
        out_heads[f] = {
            "kind": "clf",
            "classes": list(obj.classes_),
            "intercept": [round(float(x), ROUND) for x in obj.intercept_],
            # Two flat parallel arrays per class instead of [idx,coef] pairs.
            # Same numbers, about 40% fewer bytes of JSON punctuation.
            "ci": [[int(j) for j in np.nonzero(C[k])[0]] for k in range(C.shape[0])],
            "cv": [[round(float(C[k, j]), ROUND) for j in np.nonzero(C[k])[0]]
                   for k in range(C.shape[0])],
        }
        nnz = sum(len(r) for r in out_heads[f]["ci"])
        print(f"  {f:9s} {len(obj.classes_):2d} classes, {nnz} nonzero coefficients")

    # the 12 known families, so the browser can report nearest-family distance
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from generate import FAMILIES  # noqa: E402
    fams = {name: {f: getattr(sig, f) for f in SINGLE_FIELDS}
            for name, sig in FAMILIES.items()}

    payload = {"vocab": kept_vocab, "idf": kept_idf, "heads": out_heads,
               "families": fams, "fields": list(SINGLE_FIELDS),
               "ngram_min": 2, "ngram_max": 5}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(OUT) / 1024
    print(f"\nwrote {OUT}  ({size:.0f} KB)")

    # ---- parity check ----------------------------------------------------
    print("\nparity check against the Python model")

    def js_predict(text):
        """Mirror of what the browser will do."""
        counts = {}
        for g in char_wb_ngrams(text, 2, 5):
            j = kept_vocab.get(g)
            if j is not None:
                counts[j] = counts.get(j, 0) + 1
        if not counts:
            vals = {}
            for f in SINGLE_FIELDS:
                h = out_heads[f]
                if h["kind"] == "const":
                    vals[f] = h["value"]
                else:
                    sc = list(h["intercept"])
                    vals[f] = h["classes"][int(np.argmax(sc))]
            return vals
        # sublinear tf, idf, l2
        vecd = {j: (1.0 + math.log(c)) * kept_idf[j] for j, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vecd.values())) or 1.0
        vecd = {j: v / norm for j, v in vecd.items()}
        vals = {}
        for f in SINGLE_FIELDS:
            h = out_heads[f]
            if h["kind"] == "const":
                vals[f] = h["value"]; continue
            sc = list(h["intercept"])
            for k in range(len(h["ci"])):
                idxs, wts = h["ci"][k], h["cv"][k]
                s = 0.0
                for q in range(len(idxs)):
                    v = vecd.get(idxs[q])
                    if v is not None:
                        s += wts[q] * v
                sc[k] += s
            vals[f] = h["classes"][int(np.argmax(sc))] if len(sc) > 1 else (
                h["classes"][1] if sc[0] > 0 else h["classes"][0])
        return vals

    rows = [json.loads(l) for l in
            open(os.path.join(ROOT, "data", "bharat_scam_x.jsonl"), encoding="utf-8")]
    texts = [r["text"] for r in rows]
    X = vec.transform(texts)
    py = {}
    for f in SINGLE_FIELDS:
        kind, obj = heads[f]
        py[f] = [obj] * len(texts) if kind == "const" else list(obj.predict(X))

    mism = {f: 0 for f in SINGLE_FIELDS}
    risk_mism = 0
    for i, t in enumerate(texts):
        got = js_predict(t)
        for f in SINGLE_FIELDS:
            if got[f] != py[f][i]:
                mism[f] += 1
        a = AttackSignature(**{f: got[f] for f in SINGLE_FIELDS})
        bsig = AttackSignature(**{f: py[f][i] for f in SINGLE_FIELDS})
        if abs(signature_risk(a) - signature_risk(bsig)) > 1e-9:
            risk_mism += 1

    n = len(texts)
    ok = True
    for f in SINGLE_FIELDS:
        pct = 100 * (n - mism[f]) / n
        flag = "OK  " if mism[f] == 0 else "DIFF"
        if mism[f]:
            ok = False
        print(f"  {flag} {f:9s} agreement {pct:6.2f}%   ({mism[f]} of {n} differ)")
    print(f"  {'OK  ' if risk_mism == 0 else 'DIFF'} risk score agreement "
          f"{100*(n-risk_mism)/n:6.2f}%   ({risk_mism} of {n} differ)")

    if ok and risk_mism == 0:
        print("\nPARITY PASS: the browser model reproduces the Python model exactly.")
    else:
        print("\nPARITY FAIL: do not ship this export.")
        sys.exit(1)


if __name__ == "__main__":
    main()
