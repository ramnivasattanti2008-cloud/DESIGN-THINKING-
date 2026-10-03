# -*- coding: utf-8 -*-
"""
BHARAT-SCAM-X inference.

Given a message, returns:
  - the predicted Attack Signature (8 fields)
  - a structured risk, derived from that signature
  - a statistical risk from the binary detector trained on real data
  - per-token attribution by occlusion
  - a plain-language account of what the attack is doing

The two risks come from different models trained on different data, and the
app shows both. When they disagree that is information, not a bug: the
structured model knows the attack taxonomy but only ever saw templates, while
the statistical model saw 24k real messages but has no idea what an attack is.
"""
import os, re, sys
import numpy as np
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)
from schema import AttackSignature, SINGLE_FIELDS, signature_risk  # noqa: E402
from features import (extract_evidence, evidence_spans, nearest_family,  # noqa: E402
                      family_gap, advice, counterfactual)

ARTIFACTS = os.path.join(HERE, "artifacts", "model.joblib")

# Readable names for the controlled vocabularies
ACTOR_EN = {
    "bank": "a bank", "telecom": "a mobile operator",
    "government_police": "the police or a government department",
    "courier_logistics": "a courier or delivery service",
    "employer_recruiter": "an employer or recruiter",
    "ecommerce_platform": "an online shopping platform",
    "known_person": "someone you know",
    "utility_provider": "an electricity or utility provider",
    "tech_support": "technical support",
    "investment_platform": "an investment platform", "none": "nobody in particular",
}
PRETEXT_EN = {
    "account_suspension": "claims your account is about to be blocked",
    "kyc_expiry": "claims your KYC has expired",
    "parcel_held": "claims a parcel is stuck",
    "refund_due": "claims a refund is waiting for you",
    "job_offer": "offers you work",
    "prize_win": "says you have won something",
    "legal_action": "threatens legal trouble",
    "bill_overdue": "says a bill is unpaid",
    "investment_return": "promises investment returns",
    "emergency_help": "claims an emergency",
    "routine_notice": "reads as a routine notice",
    "safety_advisory": "reads as a safety warning",
}
ACTION_EN = {
    "share_code": "share a one-time password",
    "click_link": "open a link and log in",
    "call_number": "call a phone number",
    "install_app": "install an app and hand over access",
    "make_payment": "send money",
    "reply_message": "reply to the message",
    "scan_qr": "scan a QR code and enter your UPI PIN",
    "no_action": "do nothing",
    "refrain": "NOT do something (this reads as a warning, not an attack)",
}
INTENT_EN = {
    "credential_theft": "steal a credential", "funds_transfer": "take money directly",
    "malware_install": "get control of your device",
    "data_harvest": "collect personal information",
    "advance_fee": "collect an upfront fee for something that does not exist",
    "benign": "nothing harmful",
}
TACTIC_EN = {
    "authority": "pretending to be an authority", "urgency": "time pressure",
    "fear": "fear", "reward": "the promise of a reward",
    "social_proof": "suggesting others have done it",
    "reciprocity": "offering help first", "familiarity": "pretending to know you",
}


class Analyzer:
    def __init__(self, path=ARTIFACTS):
        b = joblib.load(path)
        self.vec_sig = b["vec_sig"]
        self.vec_bin = b["vec_bin"]
        self.binary = b["binary"]
        self.heads = b["heads"]

    # -- core prediction ---------------------------------------------------
    def signature(self, text: str) -> AttackSignature:
        X = self.vec_sig.transform([text])
        vals = {}
        for f in SINGLE_FIELDS:
            kind, obj = self.heads[f]
            vals[f] = obj if kind == "const" else obj.predict(X)[0]
        return AttackSignature(
            actor=vals["actor"], pretext=vals["pretext"], target=vals["target"],
            intent=vals["intent"], action=vals["action"], stage=vals["stage"])

    def field_confidence(self, text: str):
        X = self.vec_sig.transform([text])
        out = {}
        for f in SINGLE_FIELDS:
            kind, obj = self.heads[f]
            out[f] = 1.0 if kind == "const" else float(obj.predict_proba(X).max())
        return out

    def statistical_risk(self, text: str) -> float:
        return float(self.binary.predict_proba(self.vec_bin.transform([text]))[0][1])

    def structured_risk(self, text: str) -> float:
        return float(signature_risk(self.signature(text)))

    # -- attribution by occlusion -----------------------------------------
    def attribution(self, text: str):
        """
        Drop each token and measure how far the structured risk falls.
        Model-agnostic and exact for what it claims, unlike reading
        coefficients off character n-grams and hoping they map to words.
        """
        toks = re.findall(r"\S+", text)
        if not toks:
            return []
        base = self.structured_risk(text)
        out = []
        for i, t in enumerate(toks):
            ablated = " ".join(toks[:i] + toks[i + 1:])
            out.append({"token": t, "delta": round(base - self.structured_risk(ablated), 4)})
        return out

    # -- explanation -------------------------------------------------------
    def explain(self, sig: AttackSignature) -> str:
        if sig.action == "refrain":
            return ("This reads as a safety warning rather than an attack. It tells "
                    "you NOT to do something, which is the opposite of what a scam "
                    "asks for.")
        if sig.intent == "benign":
            return "Nothing here matches a known attack pattern."
        who = ACTOR_EN.get(sig.actor, sig.actor)
        story = PRETEXT_EN.get(sig.pretext, sig.pretext)
        ask = ACTION_EN.get(sig.action, sig.action)
        goal = INTENT_EN.get(sig.intent, sig.intent)
        s = (f"The sender is pretending to be {who}. The message {story}, "
             f"and wants you to {ask}. The goal is to {goal}.")
        if sig.tactic:
            levers = ", ".join(TACTIC_EN.get(t, t) for t in sig.tactic)
            s += f" It works by using {levers}."
        return s

    @staticmethod
    def _stat_in_domain(text: str) -> bool:
        """
        The statistical model trained on English real-world SMS. On Telugu or
        Tamil script it has no competence, and its confident 0.0 should not be
        allowed to dilute a confident structured detection.
        """
        if not text:
            return False
        non_ascii = sum(1 for c in text if ord(c) > 127)
        return (non_ascii / max(1, len(text))) < 0.30

    # -- the one call the app uses ----------------------------------------
    def analyze(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            return {"error": "empty message"}
        sig = self.signature(text)
        # evidence is detected, not predicted: the model never learned these
        # fields, and a shortened URL either is or is not present.
        ev = extract_evidence(text)
        sig = AttackSignature(
            actor=sig.actor, pretext=sig.pretext, target=sig.target,
            intent=sig.intent, action=sig.action, stage=sig.stage,
            tactic=sig.tactic, evidence=tuple(ev))
        srisk = float(signature_risk(sig))
        stat = self.statistical_risk(text)
        conf = self.field_confidence(text)
        attrib = self.attribution(text)
        in_dom = self._stat_in_domain(text)
        agree = (srisk > 0.5) == (stat > 0.5)
        return {
            "text": text,
            "signature": sig.as_dict(),
            "structured_risk": round(srisk, 3),
            "statistical_risk": round(stat, 3),
            "models_agree": agree,
            "statistical_in_domain": in_dom,
            "verdict": self._verdict(srisk, stat, sig.action, in_dom),
            "field_confidence": {k: round(v, 3) for k, v in conf.items()},
            "explanation": self.explain(sig),
            "attribution": attrib,
            "evidence": ev,
            "evidence_spans": evidence_spans(text),
            "family": family_gap(sig),
            "advice": advice(sig, self._verdict(srisk, stat, sig.action, in_dom)),
            "counterfactual": counterfactual(text, self._quick_verdict),
            "low_confidence_fields": [k for k, v in conf.items() if v < 0.55],
            "attribution_note": (
                "No single word was decisive: the signature survived removal of "
                "every individual word, so the reading comes from the message as "
                "a whole rather than one keyword."
                if attrib and max(abs(a["delta"]) for a in attrib) < 5e-4 else
                "Measured by removing each word and re-scoring."),
            "note": (
                None if (agree or not in_dom) else
                "The two models disagree. The structured model knows the attack "
                "taxonomy but only trained on templates; the statistical model "
                "saw 24,000 real messages but has no concept of an attack."
            ) if in_dom else
            "This message is mostly non-Latin script. The statistical model "
            "trained on English only, so its score is ignored here and the "
            "verdict comes from the structured model alone.",
        }

    def _quick_verdict(self, t: str) -> str:
        """One signature pass per candidate; the search calls this a lot."""
        s = self.signature(t)
        return self._verdict(signature_risk(s), self.statistical_risk(t),
                             s.action, self._stat_in_domain(t))

    @staticmethod
    def _verdict(srisk, stat, action, stat_in_domain):
        # An explicit "do NOT do this" is the one thing the structured model is
        # built to recognise, so it settles the question on its own.
        if action == "refrain":
            return "safe"
        if srisk >= 0.5:
            return "attack"
        if not stat_in_domain:
            return "safe"
        # Structured model found no known family. The statistical model gets a
        # say, because the taxonomy only covers 12 families and real scams
        # recombine freely -- which is this project's own headline finding.
        if stat >= 0.60:
            return "attack"
        if stat >= 0.45:
            return "uncertain"
        return "safe"


_singleton = None


def get_analyzer():
    global _singleton
    if _singleton is None:
        _singleton = Analyzer()
    return _singleton


if __name__ == "__main__":
    a = get_analyzer()
    tests = [
        "Dear customer, Your KYC has expired. Share the OTP sent to your phone.",
        "Dear customer, Your KYC has expired. Never share the OTP sent to your phone with anyone.",
        "ఎస్‌బిఐ సమాచారం: మీ కేవైసీ పత్రం మళ్లీ సమర్పించాలి. ఓటీపీ చెబితే ధృవీకరణ పూర్తవుతుంది.",
        "Your order has been shipped and will arrive by Friday.",
        "Congratulations! You have won a free iPhone, click here to claim now!!!",
    ]
    for t in tests:
        r = a.analyze(t)
        print(f"\n{t[:78]}")
        print(f"  verdict={r['verdict']}  structured={r['structured_risk']}  "
              f"statistical={r['statistical_risk']}  agree={r['models_agree']}")
        print(f"  {r['explanation'][:150]}")
