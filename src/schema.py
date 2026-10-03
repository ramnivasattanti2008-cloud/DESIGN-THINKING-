"""
BHARAT-SCAM-X: Attack Signature schema.

An Attack Signature is a typed tuple over eight controlled vocabularies.
The design goal is that the signature is INVARIANT to surface realisation
(language, script, register, paraphrase) and SENSITIVE to security semantics
(who is asked to do what, to whose benefit).
"""
from dataclasses import dataclass, asdict, field
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Controlled vocabularies  (V_1 ... V_8)
# ---------------------------------------------------------------------------

ACTOR = [  # the identity the sender claims / is impersonating
    "bank", "telecom", "government_police", "courier_logistics",
    "employer_recruiter", "ecommerce_platform", "known_person",
    "utility_provider", "tech_support", "investment_platform", "none",
]

PRETEXT = [  # the narrative frame used to justify the request
    "account_suspension", "kyc_expiry", "parcel_held", "refund_due",
    "job_offer", "prize_win", "legal_action", "bill_overdue",
    "investment_return", "emergency_help", "routine_notice", "safety_advisory",
]

TARGET = [  # the asset the attacker is ultimately after
    "otp", "card_pan", "upi_pin", "account_credentials", "funds",
    "identity_document", "device_control", "none",
]

INTENT = [  # attacker's terminal goal
    "credential_theft", "funds_transfer", "malware_install",
    "data_harvest", "advance_fee", "benign",
]

ACTION = [  # the concrete act demanded of the recipient
    "share_code", "click_link", "call_number", "install_app",
    "make_payment", "reply_message", "scan_qr", "no_action", "refrain",
]

TACTIC = [  # psychological lever (grounded in Cialdini's principles)
    "authority", "urgency", "fear", "reward", "social_proof",
    "reciprocity", "familiarity", "none",
]

EVIDENCE = [  # observable surface cues
    "shortened_url", "phone_number", "monetary_amount", "deadline",
    "reference_id", "orthographic_noise", "none",
]

STAGE = [  # position in the scam kill-chain
    "lure", "engage", "extract", "launder", "not_applicable",
]

VOCABS = {
    "actor": ACTOR, "pretext": PRETEXT, "target": TARGET, "intent": INTENT,
    "action": ACTION, "tactic": TACTIC, "evidence": EVIDENCE, "stage": STAGE,
}

# Fields that are single-valued vs. multi-valued (set-valued)
SINGLE_FIELDS = ["actor", "pretext", "target", "intent", "action", "stage"]
MULTI_FIELDS = ["tactic", "evidence"]
ALL_FIELDS = SINGLE_FIELDS + MULTI_FIELDS


@dataclass(frozen=True)
class AttackSignature:
    actor: str
    pretext: str
    target: str
    intent: str
    action: str
    stage: str
    tactic: Tuple[str, ...] = field(default_factory=tuple)
    evidence: Tuple[str, ...] = field(default_factory=tuple)

    def validate(self):
        for f in SINGLE_FIELDS:
            v = getattr(self, f)
            assert v in VOCABS[f], f"{f}={v!r} not in vocabulary"
        for f in MULTI_FIELDS:
            for v in getattr(self, f):
                assert v in VOCABS[f], f"{f}={v!r} not in vocabulary"
        return True

    def core(self) -> Tuple:
        """The security-critical core: what makes two messages 'the same attack'."""
        return (self.actor, self.pretext, self.target, self.intent, self.action)

    def as_dict(self):
        d = asdict(self)
        d["tactic"] = list(self.tactic)
        d["evidence"] = list(self.evidence)
        return d


# The benign signature: no attack is being mounted.
BENIGN = AttackSignature(
    actor="none", pretext="routine_notice", target="none", intent="benign",
    action="no_action", stage="not_applicable", tactic=(), evidence=(),
)


def hamming(a: AttackSignature, b: AttackSignature) -> int:
    """Number of single-valued fields on which two signatures disagree."""
    return sum(1 for f in SINGLE_FIELDS if getattr(a, f) != getattr(b, f))


def jaccard_multi(a: AttackSignature, b: AttackSignature) -> float:
    """Mean Jaccard over the set-valued fields."""
    scores = []
    for f in MULTI_FIELDS:
        sa, sb = set(getattr(a, f)), set(getattr(b, f))
        if not sa and not sb:
            scores.append(1.0)
        else:
            scores.append(len(sa & sb) / max(1, len(sa | sb)))
    return sum(scores) / len(scores)


def signature_agreement(a: AttackSignature, b: AttackSignature) -> float:
    """
    Sigma(a,b) in [0,1]: 1.0 iff identical.
    Weighted: single-valued fields carry 6/8, set-valued 2/8.
    """
    single = sum(1.0 for f in SINGLE_FIELDS if getattr(a, f) == getattr(b, f))
    single /= len(SINGLE_FIELDS)
    multi = jaccard_multi(a, b)
    return (len(SINGLE_FIELDS) * single + len(MULTI_FIELDS) * multi) / len(ALL_FIELDS)


# Risk model: maps a signature to a scalar risk in [0,1].
# Deliberately simple and transparent -- the paper's claim is about
# representation, not about a tuned risk head.
_INTENT_RISK = {
    "credential_theft": 1.00, "funds_transfer": 1.00, "malware_install": 0.95,
    "advance_fee": 0.85, "data_harvest": 0.70, "benign": 0.00,
}
_TARGET_BOOST = {
    "otp": 0.10, "upi_pin": 0.10, "card_pan": 0.10,
    "account_credentials": 0.08, "device_control": 0.08,
    "funds": 0.05, "identity_document": 0.04, "none": 0.0,
}


def signature_risk(s: AttackSignature) -> float:
    if s.action == "refrain":
        return 0.0
    r = _INTENT_RISK.get(s.intent, 0.0)
    if r == 0.0:
        return 0.0
    return min(1.0, r * 0.9 + _TARGET_BOOST.get(s.target, 0.0))
