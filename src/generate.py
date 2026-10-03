# -*- coding: utf-8 -*-
"""
BHARAT-SCAM-X probe corpus generator.

Produces a reproducible, fully-labelled corpus of multilingual scam and
non-scam messages together with their Attack Signatures, plus five
diagnostic evaluation suites.

Run:  python3 src/generate.py
"""
import json
import os
import random
import itertools
from collections import defaultdict

from schema import AttackSignature, BENIGN, signature_risk
from lexicon import (LANGS, SCRIPTS, ACTOR_PREFIX, PRETEXT_CLAUSE, ACTION_CLAUSE,
                     URGENCY, REFRAIN_CLAUSE, NEGATED_PRETEXT, HARD_NEGATIVES,
                     BENIGN_GENERIC)

SEED = 20260920
random.seed(SEED)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# ---------------------------------------------------------------------------
# Attack families: coherent signature tuples drawn from documented Indian
# scam modalities (bank KYC/OTP, "digital arrest", courier-customs, task-based
# job fraud, UPI collect-request refund fraud, remote-access tech support).
# ---------------------------------------------------------------------------
FAMILIES = {
    "BANK_KYC_OTP": AttackSignature(
        actor="bank", pretext="kyc_expiry", target="otp", intent="credential_theft",
        action="share_code", stage="extract",
        tactic=("authority", "urgency"), evidence=("deadline",)),

    "BANK_BLOCK_OTP": AttackSignature(
        actor="bank", pretext="account_suspension", target="otp", intent="credential_theft",
        action="share_code", stage="extract",
        tactic=("authority", "fear", "urgency"), evidence=("deadline",)),

    "BANK_KYC_LINK": AttackSignature(
        actor="bank", pretext="kyc_expiry", target="account_credentials",
        intent="credential_theft", action="click_link", stage="engage",
        tactic=("authority", "urgency"), evidence=("shortened_url", "deadline")),

    "POLICE_LEGAL_PAY": AttackSignature(
        actor="government_police", pretext="legal_action", target="funds",
        intent="funds_transfer", action="make_payment", stage="extract",
        tactic=("authority", "fear"), evidence=("monetary_amount", "reference_id")),

    "COURIER_PARCEL_PAY": AttackSignature(
        actor="courier_logistics", pretext="parcel_held", target="funds",
        intent="funds_transfer", action="make_payment", stage="extract",
        tactic=("authority", "urgency"), evidence=("monetary_amount",)),

    "UTILITY_BILL_CALL": AttackSignature(
        actor="utility_provider", pretext="bill_overdue", target="none",
        intent="data_harvest", action="call_number", stage="engage",
        tactic=("fear", "urgency"), evidence=("phone_number", "deadline")),

    "JOB_TASK_PAY": AttackSignature(
        actor="employer_recruiter", pretext="job_offer", target="funds",
        intent="advance_fee", action="make_payment", stage="lure",
        tactic=("reward", "reciprocity"), evidence=("monetary_amount",)),

    "PRIZE_FEE_PAY": AttackSignature(
        actor="ecommerce_platform", pretext="prize_win", target="funds",
        intent="advance_fee", action="make_payment", stage="lure",
        tactic=("reward", "urgency"), evidence=("monetary_amount",)),

    "REFUND_UPI_PIN": AttackSignature(
        actor="ecommerce_platform", pretext="refund_due", target="upi_pin",
        intent="credential_theft", action="scan_qr", stage="extract",
        tactic=("reward", "familiarity"), evidence=("monetary_amount",)),

    "TECH_APP_INSTALL": AttackSignature(
        actor="tech_support", pretext="account_suspension", target="device_control",
        intent="malware_install", action="install_app", stage="engage",
        tactic=("authority", "reciprocity"), evidence=("shortened_url",)),

    # --- held out for OPEN-SET evaluation (never seen in training) ---
    "INVEST_RETURN_PAY": AttackSignature(
        actor="investment_platform", pretext="investment_return", target="funds",
        intent="advance_fee", action="make_payment", stage="lure",
        tactic=("reward", "social_proof"), evidence=("monetary_amount",)),

    "FAMILY_EMERGENCY_PAY": AttackSignature(
        actor="known_person", pretext="emergency_help", target="funds",
        intent="funds_transfer", action="make_payment", stage="extract",
        tactic=("familiarity", "urgency"), evidence=("monetary_amount",)),
}

OPEN_SET_FAMILIES = ["INVEST_RETURN_PAY", "FAMILY_EMERGENCY_PAY"]
KNOWN_FAMILIES = [f for f in FAMILIES if f not in OPEN_SET_FAMILIES]
FLIP_TRAIN_FAMS = KNOWN_FAMILIES[:5]   # flips supervised
FLIP_TEST_FAMS  = KNOWN_FAMILIES[5:]   # flips held out

# Languages seen during training vs. held out for zero-shot cross-lingual test
SEEN_LANGS = ["en", "hi", "hi_Latn"]
# Flip supervision is given for these families only; the rest test transfer
# of the attack/advisory distinction to unseen attack families.

UNSEEN_LANGS = ["te", "te_Latn", "ta", "kn", "cm_hi", "cm_te"]

# Compositional-generalisation probes: (pretext, action) pairs where BOTH
# constituents occur in training, but never together.
CG_PROBES = [
    ("BANK_KYC_CALL", AttackSignature(
        actor="bank", pretext="kyc_expiry", target="none", intent="data_harvest",
        action="call_number", stage="engage",
        tactic=("authority", "urgency"), evidence=("phone_number",))),
    ("COURIER_PARCEL_LINK", AttackSignature(
        actor="courier_logistics", pretext="parcel_held", target="account_credentials",
        intent="credential_theft", action="click_link", stage="engage",
        tactic=("authority", "urgency"), evidence=("shortened_url",))),
    ("POLICE_LEGAL_OTP", AttackSignature(
        actor="government_police", pretext="legal_action", target="otp",
        intent="credential_theft", action="share_code", stage="extract",
        tactic=("authority", "fear"), evidence=("reference_id",))),
    ("PRIZE_WIN_QR", AttackSignature(
        actor="ecommerce_platform", pretext="prize_win", target="upi_pin",
        intent="credential_theft", action="scan_qr", stage="extract",
        tactic=("reward",), evidence=("monetary_amount",))),
]


def _pick_all(seq):
    return list(seq)


def realise(sig: AttackSignature, lang: str, variant: int):
    """Compose a surface message for a signature in a given language."""
    ap = ACTOR_PREFIX[lang].get(sig.actor)
    pc = PRETEXT_CLAUSE[lang].get(sig.pretext)
    ac = ACTION_CLAUSE[lang].get((sig.action, sig.target))
    if ac is None:
        # fall back: some actions are target-agnostic
        for (a, t), v in ACTION_CLAUSE[lang].items():
            if a == sig.action:
                ac = v
                break
    if not (ap and pc and ac):
        return None
    rng = random.Random(f"{sig.core()}|{lang}|{variant}|{SEED}")
    prefix = rng.choice(ap)
    pretext = pc[variant % len(pc)]
    action = ac[variant % len(ac)]
    urg = rng.choice(URGENCY[lang])
    parts = [prefix, pretext, action]
    if urg and rng.random() < 0.65:
        parts.append(urg)
    return " ".join(p for p in parts if p).strip()


def realise_flip(sig: AttackSignature, lang: str, variant: int):
    """
    Build a SEMANTIC FLIP: maximal lexical overlap with the attack message,
    inverted security semantics. The pretext is negated and the demanded
    action is replaced by its refrain counterpart.
    """
    rc = REFRAIN_CLAUSE[lang].get(sig.target)
    if rc is None:
        rc = REFRAIN_CLAUSE[lang].get("none")
    ap = ACTOR_PREFIX[lang].get(sig.actor)
    pc = PRETEXT_CLAUSE[lang].get(sig.pretext)
    if not (rc and ap and pc):
        return None
    # Same RNG seed as realise(), so the actor prefix is IDENTICAL and the
    # pretext clause is the same string. Only the demanded action is inverted.
    # The pair therefore differs by one clause, not by a whole rewrite.
    rng = random.Random(f"{sig.core()}|{lang}|{variant}|{SEED}")
    prefix = rng.choice(ap)
    pretext = pc[variant % len(pc)]
    refrain = rc[variant % len(rc)]
    msg = f"{prefix} {pretext} {refrain}"
    return " ".join(msg.split())


def flip_signature(sig: AttackSignature) -> AttackSignature:
    """The signature a correct model should assign to a flip: benign advisory."""
    return AttackSignature(
        actor=sig.actor, pretext="safety_advisory", target="none",
        intent="benign", action="refrain", stage="not_applicable",
        tactic=(), evidence=())


def record(mid, text, lang, sig, family, split, suite, pair_id=None):
    return {
        "id": mid, "text": text, "lang": lang, "script": SCRIPTS[lang],
        "family": family, "split": split, "suite": suite,
        "label": 0 if sig.intent == "benign" else 1,
        "risk": round(signature_risk(sig), 3),
        "signature": sig.as_dict(),
        "pair_id": pair_id,
    }


def build():
    rows = []
    n = itertools.count(1)
    N_VAR = 10       # paraphrase variants per (family, language)
    N_TRAIN_VAR = 7  # first 7 variants of a seen language go to train

    # ---- 1. Core attack messages ------------------------------------------
    for fam, sig in FAMILIES.items():
        for lang in LANGS:
            for v in range(N_VAR):
                txt = realise(sig, lang, v)
                if not txt:
                    continue
                if fam in OPEN_SET_FAMILIES:
                    split, suite = "test", "osr"
                elif lang in SEEN_LANGS:
                    split, suite = ("train", "iid") if v < N_TRAIN_VAR else ("test", "iid")
                else:
                    split, suite = "test", "xling"
                rows.append(record(f"m{next(n):05d}", txt, lang, sig, fam, split, suite))

    # ---- 2. Cross-lingual signature consistency (parallel sets) -----------
    # For each known family, one message per language sharing a pair_id.
    # Variant 8 is held out of training, so CLSC is not measured on seen text.
    for fam in KNOWN_FAMILIES:
        sig = FAMILIES[fam]
        pid = f"clsc_{fam}"
        for lang in LANGS:
            txt = realise(sig, lang, 8)
            if txt:
                rows.append(record(f"m{next(n):05d}", txt, lang, sig, fam,
                                   "test", "clsc", pair_id=pid))

    # ---- 3. Semantic flip pairs ------------------------------------------
    # Flips for FLIP_TRAIN_FAMS (seen languages only) are placed in TRAINING so
    # that the label `action=refrain` is learnable. If a model still fails the
    # held-out flips, that failure is informative rather than tautological.
    for fam in KNOWN_FAMILIES:
        sig = FAMILIES[fam]
        fsig = flip_signature(sig)
        train_fam = fam in FLIP_TRAIN_FAMS
        for lang in LANGS:
            variants = (5, 6) if (train_fam and lang in SEEN_LANGS) else (8, 9)
            for v in variants:
                a = realise(sig, lang, v)
                b = realise_flip(sig, lang, v)
                if not (a and b):
                    continue
                if train_fam and lang in SEEN_LANGS:
                    rows.append(record(f"m{next(n):05d}", a, lang, sig, fam,
                                       "train", "sfs_seen_attack"))
                    rows.append(record(f"m{next(n):05d}", b, lang, fsig, fam,
                                       "train", "sfs_seen_flip"))
                else:
                    pid = f"sfs_{fam}_{lang}_{v}"
                    rows.append(record(f"m{next(n):05d}", a, lang, sig, fam,
                                       "test", "sfs_attack", pair_id=pid))
                    rows.append(record(f"m{next(n):05d}", b, lang, fsig, fam,
                                       "test", "sfs_flip", pair_id=pid))

    # ---- 4. Hard negatives ------------------------------------------------
    for lang, msgs in HARD_NEGATIVES.items():
        for i, t in enumerate(msgs):
            split = "train" if i % 2 == 0 and lang in SEEN_LANGS else "test"
            rows.append(record(f"m{next(n):05d}", t, lang, BENIGN, "HARD_NEG",
                               split, "hard_negative"))

    # ---- 4b. Generic benign traffic (class balance) -----------------------
    # Composed with actor prefixes so benign messages carry the same
    # envelope structure as attacks and cannot be separated on format alone.
    for lang, msgs in BENIGN_GENERIC.items():
        prefixes = (ACTOR_PREFIX[lang]["ecommerce_platform"]
                    + ACTOR_PREFIX[lang]["known_person"]
                    + ACTOR_PREFIX[lang]["utility_provider"])
        for i, t in enumerate(msgs):
            for j, pre in enumerate([""] + prefixes[:3]):
                txt = (pre + " " + t).strip() if pre else t
                if lang in SEEN_LANGS:
                    split = "train" if (i * 4 + j) % 5 != 4 else "test"
                else:
                    split = "test"
                rows.append(record(f"m{next(n):05d}", txt, lang, BENIGN,
                                   "BENIGN", split, "benign_generic"))

    # ---- 5. Compositional generalisation ----------------------------------
    for fam, sig in CG_PROBES:
        for lang in LANGS:
            for v in range(2):
                txt = realise(sig, lang, v)
                if txt:
                    rows.append(record(f"m{next(n):05d}", txt, lang, sig, fam,
                                       "test", "compositional"))

    # ---- 6. Deduplicate ---------------------------------------------------
    # Template composition can collide; keep the first occurrence and make
    # sure no test item is string-identical to a training item.
    seen_text, deduped = set(), []
    train_text = {r["text"] for r in rows if r["split"] == "train"}
    for r in rows:
        key = (r["text"], r["suite"])
        if key in seen_text:
            continue
        # No test item may be string-identical to any training item, in any
        # suite. Dropping one half of an SFS pair simply removes that pair,
        # which the evaluator handles by requiring both halves to be present.
        if r["split"] == "test" and r["text"] in train_text:
            continue
        seen_text.add(key)
        deduped.append(r)
    return deduped


def summarise(rows):
    by = defaultdict(int)
    for r in rows:
        by[(r["split"], r["suite"])] += 1
    lang_counts = defaultdict(int)
    for r in rows:
        lang_counts[r["lang"]] += 1
    return by, lang_counts


if __name__ == "__main__":
    rows = build()
    os.makedirs(DATA, exist_ok=True)
    out = os.path.join(DATA, "bharat_scam_x.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by, lang_counts = summarise(rows)
    print(f"total messages: {len(rows)}")
    print(f"written to: {out}\n")
    print("split x suite:")
    for k in sorted(by):
        print(f"  {k[0]:5s} {k[1]:15s} {by[k]:5d}")
    print("\nper language:")
    for k in LANGS:
        print(f"  {k:8s} {lang_counts[k]:5d}")
    n_pos = sum(1 for r in rows if r["label"] == 1)
    print(f"\nattack: {n_pos}  benign: {len(rows)-n_pos}")
