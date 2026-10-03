# Project state

**Read this first.** It is the single source of truth for what exists, what works,
what is known broken, and what to do next. Update it in the same commit as any
change you make.

Last updated: 2026-10-03

---

## What this project is

A scam detector for Indian-language messaging that tries to identify *what the
attack is* rather than whether the text looks scammy. Every message is mapped to
an **Attack Signature**: eight typed fields (actor, pretext, target, intent,
action, stage, tactic, evidence) drawn from closed vocabularies. Risk is then
computed from that signature, so the only way the model can change its risk
estimate is by changing its account of the attack.

The thing that makes it work at all is one value in the `action` vocabulary:
`refrain`, meaning "the message tells you NOT to do something." That value is
what separates a scam from the bank advisory warning against it. Remove it and
the whole framework collapses.

## Status at a glance

| Component | State | Notes |
|---|---|---|
| Attack Signature schema | **done** | `src/schema.py`, 8 fields, agreement σ, risk ρ |
| Synthetic corpus generator | **done** | 1,823 messages, 9 varieties, 12 families, seed 20260920 |
| Paper evaluation harness | **done** | `src/evaluate.py`, 4 baselines, 6 result tables |
| Research paper | **drafted, NOT submitted** | see "Known issues" |
| Trained app model | **done** | `app/train.py` → `app/artifacts/model.joblib` |
| Inference layer | **done** | `app/model.py`, occlusion attribution, explanations |
| HTTP API | **done, untested under load** | `app/api.py` (FastAPI) |
| Browser demo | **done, parity verified** | `app/web/`, runs with no server |
| Evidence extraction | **done** | regex, closes the unpredicted-fields gap |
| Nearest-family distance | **done** | says how far outside the taxonomy a message sits |
| Minimal counterfactual | **done** | smallest edit that flips the verdict |
| Action advice | **done** | India-specific: 1930, cybercrime.gov.in |
| Adversarial playground | **done** | "Fool it" tab, logs successful edits |
| Confidence surfacing | **done** | flags fields below 0.55 |
| Real-data integration | **partial** | see "Data" |
| Transformer baseline | **not started** | highest-value next task |

## How to run it

```bash
pip install -r requirements.txt

python3 src/generate.py        # rebuild corpus          (~2s)
python3 src/evaluate.py        # paper tables            (~10s)
python3 app/train.py           # train app model         (~65s)
python3 app/export_js.py       # export to browser + verify parity
uvicorn app.api:app --port 8000   # then open http://localhost:8000
```

`app/export_js.py` **exits non-zero** unless the browser model reproduces the
Python model on all 1,823 corpus messages. Do not weaken that check.

## Architecture, and why

Two vectorizers, deliberately:

- `vec_sig` (20,000 char n-gram features) fits the synthetic corpus only, and
  feeds the six signature heads. 7,000 was tried to shrink the browser export and
  cost 5 of 180 flip predictions; the size was accepted instead.
- `vec_bin` (24,000 features) fits synthetic plus 24,000 real English messages,
  and feeds the binary detector.

A single shared vectorizer was tried first and failed: 24,000 real English rows
swamped 356 synthetic ones, and compositional signature recovery fell from 0.056
to 0.000. If you are tempted to simplify this back to one vectorizer, don't.

Two training regimes, also deliberately:

- The **paper** holds out Telugu, Tamil, Kannada and code-mixed varieties to
  measure zero-shot transfer. That is the right experiment.
- The **app** trains on all nine varieties. A user pasting Telugu into a
  train-split-only model gets 2 non-zero features and a verdict of "safe", which
  is worse than useless. Paper numbers live in `src/evaluate.py`; app numbers in
  `app/train.py`. They are not comparable and should never be mixed.

## Features added 2026-10-03

**Evidence extraction** (`app/features.py`). The schema has eight fields but the
model only ever predicted six, which capped mean agreement near 0.75 even at
perfect core accuracy. Half of `evidence` is not a learning problem: shortened
URLs, phone numbers, rupee amounts, deadlines and reference IDs are regex. They
are now detected rather than predicted, in both Python and JavaScript, with
identical output.

**Nearest known family.** Reports which of the 12 families a message is closest
to and which fields differ. Uses core-field similarity, deliberately *not*
`signature_agreement` — that weights `evidence` at 1/8, and since evidence is now
detected per message while family templates carry fixed tuples, every real
message would be penalised for cues the template never claimed.

**Minimal counterfactual.** The smallest edit that flips the verdict, searched
cheapest first: negate a verb, negate plus a refrain tail, delete one token,
delete two. Roughly 0.07s per message.

This one found something. Negating the verb is **not enough** — "Never share the
OTP sent to your phone." still reads as an attack. The model only flips when the
phrase "with anyone" is also present, because every refrain clause in the
training corpus ends that way. It learned the template's ending, not what
"never" means. The app reports this to the user rather than hiding it.

**Action advice.** India-specific next steps keyed on target and actor: the 1930
helpline, cybercrime.gov.in, and the point that police do not conduct "digital
arrests".

**Adversarial playground.** A "Fool it" tab where edits are scored live and any
edit that changes the verdict is logged. Generates non-templated failure cases,
which is the corpus's weakest point.

**Confidence surfacing.** Fields below 0.55 confidence are named in the UI.

## Current numbers

App model, 5-fold cross-validation per signature field:

| field | CV accuracy |
|---|---|
| actor | 0.947 |
| pretext | 0.897 |
| target | 0.968 |
| intent | 0.931 |
| action | 0.945 |
| stage | 0.925 |

On the corpus's own contrast pairs the app model gets **180/180 flips** correct
(advisory read as safe) and **173/173 attacks** correct. That is in-sample, so it
is a sanity check, not a generalisation claim. The held-out number that matters is
flip-success 0.559 on unseen attack families, from `src/evaluate.py`.

Binary detector: 0.857 macro-F1 on held-out real English, 0.786 on synthetic.

Paper model, held-out (from `src/evaluate.py`), the numbers that matter:

| metric | value |
|---|---|
| In-distribution macro-F1 | 1.000 |
| Cross-lingual macro-F1 | 0.888 |
| Flip-success rate | 0.559 |
| False positives on real advisories | 0.293 |
| **Exact signature recovery, recombined attacks** | **0.056** |

That last row is the project's central finding, not a bug to be hidden: the model
says "attack" on 91.8% of recombined attacks while getting essentially every
detail of *what* the attack is wrong.

## Data

| Source | Rows | Use | Caveat |
|---|---|---|---|
| Synthetic corpus | 1,823 | signature labels, all 9 varieties | templated, not field data |
| vinit9638/SMS-scam-detection-dataset | 138,813 | binary detection | **no Telugu, Tamil or Kannada at all**; Devanagari rows are machine-translated; no licence file |
| Dravidian SMS (IEEE DataPort) | ~7,700 | **not yet obtained** | real messages in exactly our languages; needs a subscription or an email to the authors |

The real corpus was measured, not trusted: of 138,813 rows, 32 carry an Indic
language tag and zero contain Telugu, Tamil or Kannada script. Its "41 languages"
claim is technically true and practically empty.

## Known issues

1. **The paper is drafted but not written by the author.** Its prose was produced
   with AI assistance, which is disclosed in the acknowledgement section. That
   acknowledgement stays. Work in progress: the author rewriting each section in
   his own words using `writing-kit/`.
2. **No transformer baseline.** MuRIL or LaBSE would likely improve cross-lingual
   transfer substantially. This is the first thing a reviewer will ask about.
3. **Non-English text is unreviewed.** The Telugu, Tamil and Kannada messages were
   written without native-speaker review.
4. **The model misses unknown attack families.** "Congratulations, you won a free
   iPhone, click here" reads as *uncertain*, not *attack*, because that
   combination is not in the 12-family taxonomy. Expected, documented, not fixed.
5. **The browser export is 12.6 MB.** That is the cost of 20,000 signature
   features. Dropping to 7,000 gives a 4.5 MB export and loses 5 of 180 flips;
   12,000 gives ~7.7 MB and loses 1. Flip behaviour is the product, so the size
   was accepted. Measured, not guessed — rerun the sweep before changing it.
6. **API is untested under concurrency.** Single `Analyzer` instance, no locking.
   Occlusion attribution is O(tokens) model calls per request.

## Next tasks, in priority order

1. **Add a MuRIL or LaBSE baseline.** Run it through `src/evaluate.py` unchanged
   so the numbers are comparable. Colab with a GPU, roughly a day.
2. **Email the Dravidian dataset authors** (Elangovan, NIT Silchar; Abirami,
   Thiagarajar College) and ask for research access. Real Telugu/Tamil/Kannada
   messages would remove the project's biggest stated limitation.
3. **Native-speaker review** of the Indic messages in `data/bharat_scam_x.jsonl`.
4. **Evaluate on real data** once obtained, and report synthetic vs real side by
   side. That comparison is more interesting than either number alone.
5. Expand the taxonomy beyond 12 families, driven by what real data shows.
6. Harden the API: request limits, a model pool, caching.
7. **Fix what the counterfactual exposed.** The refrain clauses in
   `src/lexicon.py` all end with the same tail, so the model learned the tail
   rather than the negation. Vary those endings and retrain; flip behaviour
   should get meaningfully more robust, and the counterfactual becomes a 1-edit
   result instead of 2.
8. Predict `tactic` as well. `evidence` is now handled by regex; `tactic`
   (authority, urgency, fear, reward) genuinely needs a model and is the last
   unpredicted field.

## Changelog

- **2026-10-03 (later)** — Six features: evidence extraction, nearest-family
  distance, minimal counterfactual, action advice, adversarial playground,
  confidence surfacing. All ported to JS with output verified identical to
  Python. Counterfactual search revealed the model keys on the refrain clause's
  trailing phrase rather than the negation; logged as task 7.
- **2026-10-03** — App built. Signature vectorizer sized at 20,000 features after
  measuring flip accuracy against feature count (7k: 0.972, 12k: 0.994, 20k: 1.000). Two-vectorizer architecture after a shared one
  destroyed signature recovery. Browser port with enforced parity (all 1,823
  messages). FastAPI backend. Real dataset cloned and measured; found to contain
  no Dravidian-language content.
- **2026-09-20** — Paper drafted, 11 pages. Corpus generator, evaluation harness,
  four baselines. Fixed class collapse (94% attacks) and train/test leakage (8
  messages).
