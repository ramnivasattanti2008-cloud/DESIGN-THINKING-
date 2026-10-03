# Instructions for AI agents working on this repo

Read `PROJECT_STATE.md` before touching anything. It carries current status,
architecture decisions and the task queue. Update it in the same commit as your
change — a stale state file is worse than none, because the next agent trusts it.

## The three rules that matter

**1. Never weaken a verification gate.**
`app/export_js.py` exits non-zero unless the browser model reproduces the Python
model on all 1,823 corpus messages. That check has already caught two real bugs:
a wrong `char_wb` n-gram port, and coefficient pruning that broke semantic-flip
predictions specifically. If it fails, fix the model, not the threshold.

**2. Never invent a number.**
Every figure in the paper and the docs came out of `src/evaluate.py` or
`app/train.py` with seed `20260920`. If you need a number that isn't recorded,
compute it and say how. Do not round from memory, do not estimate, do not carry a
figure across from a different training regime.

**3. Keep the two training regimes separate.**
The paper holds out Telugu/Tamil/Kannada/code-mixed to measure zero-shot
transfer. The app trains on all nine varieties so it actually works. Both are
correct for their job. Mixing their numbers produces claims that are false in
both directions.

## Things that look like improvements and are not

- **"Simplify to one vectorizer."** Tried. 24,000 real English rows swamp 356
  synthetic ones and compositional signature recovery drops from 0.056 to 0.000.
- **"Prune the exported model harder, it's 4.5 MB."** Tried at thresholds up to
  0.5. Anything above 0.01 breaks semantic-flip predictions first, because flips
  are borderline by construction. The flip behaviour is the whole point of the
  project.
- **"Remove the AI-assistance acknowledgement from the paper."** No. Under AICTE
  rules unacknowledged AI content is plagiarism while disclosed assistance is
  permitted. The disclosure protects the author.
- **"Make the model more confident so fewer things read as uncertain."** The
  `uncertain` verdict is doing real work. The taxonomy covers 12 families and
  real scams recombine freely; exact signature recovery on recombinations is
  0.056. Hiding that behind a confident answer makes the system dishonest, not
  better.

## Code layout

```
src/schema.py        Attack Signature type, vocabularies, agreement σ, risk ρ
src/lexicon.py       Multilingual realisation lexicon, 9 varieties
src/generate.py      Corpus generator and split construction
src/evaluate.py      Paper evaluation: 4 baselines, 6 tables (held-out splits)
app/train.py         Trains the app model (all varieties) + persists
app/model.py         Inference: signature, risk, attribution, explanation
app/api.py           FastAPI, serves the browser demo too
app/export_js.py     Model → JSON for the browser, with the parity gate
app/web/             Standalone browser app (index.html + model.json)
paper/               LaTeX source and compiled PDF
writing-kit/         Section scaffolds for the author's own rewrite
```

## Conventions

- Seed is `20260920` everywhere. Don't change it without saying why.
- Every claim in a docstring or comment should be checkable by running something.
- When a result surprises you, verify it before building on it. Two bugs in this
  project (class collapse at 94% attacks, and train/test leakage) produced
  *better-looking* numbers, which is how they survived a first look.
- Prefer failing loudly over degrading quietly.

## What this project does not do

It is not a deployable product. The corpus is template-generated, so results
characterise model behaviour under controlled contrast and do not estimate field
performance. Any claim of real-world accuracy needs real-world data, which the
project does not currently have for Telugu, Tamil or Kannada. See the "Data" and
"Known issues" sections of `PROJECT_STATE.md`.
