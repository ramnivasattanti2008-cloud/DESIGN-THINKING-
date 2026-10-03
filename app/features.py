# -*- coding: utf-8 -*-
"""
Features layered on top of the signature model.

  extract_evidence   regex-detected surface cues (the `evidence` vocabulary)
  nearest_family     closest known attack family, with a distance
  counterfactual     the smallest edit that flips the verdict
  advice             what the recipient should actually do

`evidence` matters more than it looks. The schema has eight fields but the
model only ever predicted six, which is why mean signature agreement caps near
0.75 even when the core is perfect. Half of `evidence` is not a learning
problem at all: a shortened URL either is or is not present. Detecting those
with regex closes a documented hole for free.
"""
import os, re, sys
from typing import List, Tuple, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from schema import AttackSignature, signature_agreement, SINGLE_FIELDS  # noqa: E402
from generate import FAMILIES  # noqa: E402

# ---------------------------------------------------------------------------
# Evidence detection
# ---------------------------------------------------------------------------
SHORTENERS = r"(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|is\.gd|cutt\.ly|rb\.gy|ow\.ly|rebrand\.ly|shorturl\.at|tiny\.cc)"

RE_SHORT_URL = re.compile(SHORTENERS, re.I)
RE_ANY_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
# Indian mobile numbers, short codes (1930, 1800-xxx), and +91 forms
RE_PHONE = re.compile(
    r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"
    r"|(?<!\d)1(?:930|800[\s-]?\d{3}[\s-]?\d{3,4})(?!\d)"
)
RE_MONEY = re.compile(
    r"(?:₹|\bRs\.?|\bINR\b)\s?\d[\d,]*"
    r"|\d[\d,]*\s?(?:रुपये|रुपए|రూపాయ\w*|ரூபாய்|ರೂಪಾಯಿ|rupay\w*|rupee\w*)",
    re.I)
RE_DEADLINE = re.compile(
    r"\b(?:within\s+\d+\s*(?:hour|hrs?|minute|min)s?|in\s+\d+\s*(?:hour|hrs?)s?"
    r"|today|tonight|immediately|urgent(?:ly)?|right\s+now|before\s+\d)"
    r"|तुरंत|आज|घंटे|వెంటనే|ఈరోజు|గంటల్లో|உடனடியாக|இன்று|ತಕ್ಷಣ|ಇಂದು"
    r"|\bturant\b|\bventane\b|\bimmediately\b", re.I)
RE_REF = re.compile(
    r"\b(?:[A-Z]{2,4}\d{4,}|A/c\s?[Xx*]{2,}\d+|(?:ref|case|order|txn|id)[\s.:#-]*[A-Z0-9]{5,})\b")
RE_UPI = re.compile(r"\b[\w.\-]{2,}@(?:ok\w+|paytm|ybl|upi|axl|ibl|apl|sbi)\b", re.I)

EVIDENCE_PATTERNS = [
    ("shortened_url", RE_SHORT_URL),
    ("phone_number", RE_PHONE),
    ("monetary_amount", RE_MONEY),
    ("deadline", RE_DEADLINE),
    ("reference_id", RE_REF),
]


def _orthographic_noise(text: str) -> bool:
    """Shouty caps or repeated punctuation, the way bulk scam text often reads."""
    if re.search(r"[!?]{2,}", text):
        return True
    letters = [c for c in text if c.isalpha() and c.isascii()]
    if len(letters) >= 12:
        caps = sum(1 for c in letters if c.isupper())
        if caps / len(letters) > 0.55:
            return True
    return bool(re.search(r"\b[A-Z]{5,}\b.*\b[A-Z]{5,}\b", text))


def extract_evidence(text: str) -> List[str]:
    """Surface cues present in the message. Detected, not predicted."""
    found = []
    for name, pat in EVIDENCE_PATTERNS:
        if pat.search(text):
            found.append(name)
    if _orthographic_noise(text):
        found.append("orthographic_noise")
    return found


def evidence_spans(text: str):
    """Where each cue sits, so the UI can point at it."""
    out = []
    for name, pat in EVIDENCE_PATTERNS:
        for m in pat.finditer(text):
            out.append({"kind": name, "text": m.group(0), "start": m.start(), "end": m.end()})
    for m in RE_UPI.finditer(text):
        out.append({"kind": "upi_id", "text": m.group(0), "start": m.start(), "end": m.end()})
    for m in RE_ANY_URL.finditer(text):
        if not RE_SHORT_URL.search(m.group(0)):
            out.append({"kind": "url", "text": m.group(0), "start": m.start(), "end": m.end()})
    return sorted(out, key=lambda d: d["start"])


# ---------------------------------------------------------------------------
# Nearest known family
# ---------------------------------------------------------------------------
def _core_similarity(a: AttackSignature, b: AttackSignature) -> float:
    """
    Fraction of the six single-valued fields that agree.

    Deliberately NOT signature_agreement(): that weights `evidence` at 1/8, and
    since evidence is now regex-detected per message while the family templates
    carry fixed tuples, every real message would be penalised for cues the
    template never claimed. "Which family is this" is a question about the
    core, not about whether a URL happened to be present.
    """
    return sum(1.0 for f in SINGLE_FIELDS
               if getattr(a, f) == getattr(b, f)) / len(SINGLE_FIELDS)


def nearest_family(sig: AttackSignature, k: int = 3) -> List[Tuple[str, float]]:
    scored = [(name, round(_core_similarity(sig, fam), 3))
              for name, fam in FAMILIES.items()]
    scored.sort(key=lambda t: -t[1])
    return scored[:k]


def family_gap(sig: AttackSignature) -> dict:
    """
    How far outside the taxonomy this message sits. The 12 families are all the
    model knows; a real scam that recombines them freely scores low here, and
    that is worth saying out loud rather than hiding behind a confident label.
    """
    top = nearest_family(sig, 3)
    best_name, best_sim = top[0]
    diffs = [f for f in SINGLE_FIELDS
             if getattr(sig, f) != getattr(FAMILIES[best_name], f)]
    if not diffs:
        note = f"Matches the {best_name} family on every field."
    elif best_sim >= 0.66:
        note = (f"Closest to {best_name} ({len(SINGLE_FIELDS)-len(diffs)} of "
                f"{len(SINGLE_FIELDS)} fields match), but "
                f"{', '.join(diffs)} {'differ' if len(diffs) > 1 else 'differs'}. "
                f"This looks like a recombination of known parts, which is "
                f"exactly where this model is weakest.")
    else:
        note = (f"No close match among the 12 known families (best is {best_name}, "
                f"{len(SINGLE_FIELDS)-len(diffs)} of {len(SINGLE_FIELDS)} fields). "
                f"Treat this as outside what the model has seen.")
    return {"top": top, "note": note}


# ---------------------------------------------------------------------------
# What to actually do
# ---------------------------------------------------------------------------
_GENERIC = [
    "Do not reply. A reply confirms your number is live and reaches a person.",
    "Do not call any number printed in the message. Look the organisation up yourself.",
    "Report it on the national cybercrime helpline 1930, or at cybercrime.gov.in.",
]
_BY_TARGET = {
    "otp": ["Never share an OTP. No bank, telecom or government office will ask for one.",
            "If you already shared it, call your bank's official number now and freeze the account."],
    "upi_pin": ["Entering your UPI PIN never receives money. It only sends money.",
                "If you already entered it, raise a dispute in your UPI app and call your bank."],
    "card_pan": ["Never type a card number into a link from a message.",
                 "If you already did, block the card from your bank's app."],
    "account_credentials": ["Open your bank only from its official app, never from a link.",
                            "If you logged in through the link, change the password now from the app."],
    "device_control": ["Uninstall any screen-sharing app you were asked to install, now.",
                       "AnyDesk, TeamViewer and QuickSupport give the caller full control of your phone."],
    "funds": ["Do not transfer anything. Nobody legitimate demands payment by SMS to avoid arrest.",
              "If you already paid, report within 24 hours. Fast reports have a real chance of recovery."],
    "identity_document": ["Do not send Aadhaar, PAN or photos of documents to an unverified contact."],
}
_BY_ACTOR = {
    "government_police": ["Police do not arrest or fine people over a phone call or SMS. "
                          "There is no such thing as a 'digital arrest'."],
    "bank": ["Call the number printed on your debit card, not any number in the message."],
    "known_person": ["Call the person on the number you already have saved and check it is really them."],
}


def advice(sig: AttackSignature, verdict: str) -> List[str]:
    if verdict == "safe":
        return []
    steps = list(_BY_TARGET.get(sig.target, []))
    steps += _BY_ACTOR.get(sig.actor, [])
    steps += _GENERIC
    seen, out = set(), []
    for s in steps:
        if s not in seen:
            seen.add(s); out.append(s)
    return out[:6]


# ---------------------------------------------------------------------------
# Minimal counterfactual edit
# ---------------------------------------------------------------------------
NEGATORS = ["never", "do not", "don't"]
SAFE_SWAPS = {
    "share": "never share", "send": "never send", "pay": "never pay",
    "call": "do not call", "click": "do not click", "install": "do not install",
    "scan": "do not scan", "enter": "never enter", "reply": "do not reply",
    "transfer": "never transfer", "deposit": "never deposit", "tell": "never tell",
    "download": "do not download", "give": "never give",
}


# Tails the training templates always attached to a refrain clause. The model
# turns out to need one of these as well as the negation, which is itself worth
# reporting: it learned the template's ending, not what "never" means.
REFRAIN_TAILS = ["with anyone", "to anyone", "with anyone; the bank never asks for it"]


def counterfactual(text: str, predict_verdict, max_tokens: int = 60) -> Optional[dict]:
    """
    Smallest edit that flips the verdict, searched cheapest first:
    negate a verb, then negate and add a refrain tail, then delete one token,
    then two.

    `predict_verdict` is injected so this does not care how the model is loaded.
    The result carries a `note` when the edit reveals something about the model
    rather than about the message.
    """
    toks = text.split()
    if not toks or len(toks) > max_tokens:
        return None
    start = predict_verdict(text)

    def result(kind, edits, cand, changed, note=None):
        return {"kind": kind, "edits": edits, "text": cand, "changed": changed,
                "from_verdict": start, "to_verdict": predict_verdict(cand),
                "note": note}

    verbs = [(i, t, re.sub(r"[^\w']", "", t).lower()) for i, t in enumerate(toks)]
    verbs = [(i, t, b) for i, t, b in verbs if b in SAFE_SWAPS]

    # 1. negate an imperative verb
    for i, t, bare in verbs:
        cand = " ".join(toks[:i] + [SAFE_SWAPS[bare]] + toks[i + 1:])
        if predict_verdict(cand) != start:
            return result("negate", 1, cand,
                          [{"from": t, "to": SAFE_SWAPS[bare], "index": i}])

    # 2. negate and add the tail the templates always carried
    for i, t, bare in verbs:
        stem = toks[:i] + [SAFE_SWAPS[bare]] + toks[i + 1:]
        base = " ".join(stem).rstrip(" .")
        for tail in REFRAIN_TAILS:
            cand = f"{base} {tail}."
            if predict_verdict(cand) != start:
                return result(
                    "negate+tail", 2, cand,
                    [{"from": t, "to": SAFE_SWAPS[bare], "index": i},
                     {"from": "", "to": tail, "index": len(stem)}],
                    note=("Negating the verb alone was not enough. The model also "
                          f"needed the phrase \u201c{tail}\u201d, which every refrain "
                          "clause in the training corpus happens to end with. It "
                          "learned the template's ending, not what \u201cnever\u201d means."))

    # 3. single-token deletion
    for i in range(len(toks)):
        cand = " ".join(toks[:i] + toks[i + 1:])
        if cand and predict_verdict(cand) != start:
            return result("delete", 1, cand, [{"from": toks[i], "to": "", "index": i}])

    # 4. pairs, capped so this stays interactive
    if len(toks) <= 25:
        for i in range(len(toks)):
            for j in range(i + 1, len(toks)):
                cand = " ".join(t for k, t in enumerate(toks) if k not in (i, j))
                if cand and predict_verdict(cand) != start:
                    return result("delete", 2, cand,
                                  [{"from": toks[i], "to": "", "index": i},
                                   {"from": toks[j], "to": "", "index": j}])
    return None
