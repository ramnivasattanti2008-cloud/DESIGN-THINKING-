# Bharat-Scam-X

Scam detection for Indian-language messaging that works out **what the attack is**,
not just whether the text looks scammy.

Every message maps to an **Attack Signature**: eight typed fields drawn from closed
vocabularies — who the sender is impersonating, what story they're telling, what
they're after, what they want you to do, which persuasion levers they're pulling.
Risk is computed from that signature, so the model can only change its risk
estimate by changing its account of the attack.

Works across nine Indian language varieties: English, Hindi (Devanagari and
Roman), Telugu (Telugu script and Roman), Tamil, Kannada, and English-Hindi and
English-Telugu code-mixed.

## The idea in one example

```
Bank notice: Your KYC has expired. Share the OTP sent to your phone.
                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  attack,  risk 1.00

Bank notice: Your KYC has expired. Never share the OTP with anyone.
                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  advisory, risk 0.00
```

Same sender, same story, most of the same words. One is credential theft, the
other is the message your bank sends to prevent it. A keyword filter cannot tell
them apart. This one mostly can, because `refrain` — "do NOT do this" — is a value
in the action vocabulary.

Mostly, not always: flip-success on held-out attack families is **0.559**, against
0.175 for a character n-gram model and 0.028 for a keyword rule. Three times
better than the alternatives and still wrong four times in ten.

## Quick start

```bash
pip install -r requirements.txt

python3 app/train.py              # train          (~65s, CPU)
python3 app/export_js.py          # browser export + parity check
uvicorn app.api:app --port 8000   # http://localhost:8000
```

The browser app also runs with no Python at all — serve `app/web/` over any static
host.

## API

```bash
curl -X POST localhost:8000/analyze -H 'Content-Type: application/json' \
  -d '{"text":"Dear customer, Your KYC has expired. Share the OTP sent to your phone."}'
```

```json
{
  "verdict": "attack",
  "structured_risk": 1.0,
  "statistical_risk": 0.504,
  "signature": {"actor":"bank","pretext":"kyc_expiry","target":"otp",
                "intent":"credential_theft","action":"share_code","stage":"extract"},
  "explanation": "The sender is pretending to be a bank. The message claims your
                  KYC has expired, and wants you to share a one-time password.
                  The goal is to steal a credential.",
  "attribution": [{"token":"Share","delta":0.9}, ...]
}
```

Attribution is measured by removing each word and re-scoring, so it reports what
the model actually used rather than a guess read off coefficients.

## How it's put together

Two models, because two different jobs need two different training sets:

- **Signature heads** — six logistic regressions over character n-grams, trained on
  a constructed corpus of 1,823 messages with full signature labels. This is the
  only source that has those labels.
- **Binary detector** — trained on the same corpus plus 24,000 real English
  messages. Better on real-world English, no competence on Indic scripts, and the
  app ignores it when the input is mostly non-Latin.

They each get their own vectorizer. Sharing one lets the real English data swamp
the synthetic corpus and destroys signature recovery entirely.

## Honest limits

The corpus is **template-generated**, not collected from real phones. Results
characterise model behaviour under controlled contrast; they are not estimates of
field accuracy.

Exact signature recovery on **recombined** attacks — built only from components
seen in training, just combined differently — is **0.056**, while binary detection
on those same messages stays at 0.918. The model says "attack" while being wrong
about nearly every detail of what the attack is. Real novel scams are mostly
recombinations, so this is the limitation that matters most.

There is no transformer baseline yet. MuRIL or LaBSE would likely improve
cross-lingual transfer and it's the first thing a reviewer asks about.

The Telugu, Tamil and Kannada messages have not been checked by native speakers.

## Repository

See **`PROJECT_STATE.md`** for current status, architecture decisions and the task
queue, and **`AGENTS.md`** if you are an AI agent working on this.

```
src/      schema, corpus generator, paper evaluation harness
app/      trained model, inference, FastAPI, browser export
app/web/  standalone browser app
paper/    LaTeX source and PDF
```

## Ethics

All messages are synthetic instances of publicly documented fraud patterns. No
real institution branding, no resolving URLs, no real phone numbers, no personal
data.
