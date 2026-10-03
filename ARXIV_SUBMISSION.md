# Getting this onto arXiv

Cost: ₹0. arXiv never charges. Anyone asking you for money to publish is not
arXiv.

## Before you start — fix these

1. **Your name.** The paper says "Ram Nivas Attanti", inferred from your email.
   If that's wrong, fix line ~25 of `paper/bharat_scam_x.tex` before submitting.
   A wrong name on a permanent public record is annoying to undo.
2. **Your affiliation.** It currently reads "JAIN (Deemed-to-be University),
   Bengaluru". Correct the campus if you're elsewhere.
3. **The acknowledgement.** There is a section declaring AI assistance in the
   implementation and drafting. **Leave it in.** arXiv and most institutions now
   expect this disclosure, it costs you nothing, and removing it creates a
   problem that a single sentence would have avoided.

## The endorsement problem — deal with this first

First-time submitters to `cs.CR` or `cs.CL` need an **endorsement** from an
established arXiv author in that category. This is the step that takes days, so
start it now, not after you've polished the PDF.

How to get one:
- A professor in your department who has published on arXiv. Ask directly, send
  them the PDF, mention you need a cs.CR endorsement.
- Any co-author with arXiv history. Adding a faculty supervisor as co-author
  solves endorsement *and* strengthens the paper — worth asking.
- arXiv shows you an endorsement code when you try to submit. You send that code
  to whoever endorses you.

**If nobody endorses you in time:** your 60 marks do not depend on this. Submit
the PDF to your faculty. Publication and assignment submission are separate
things; do not let one block the other.

## Submission steps

1. Create an account at `arxiv.org/user/register`. **Use your university email
   if you have one** — it materially improves your endorsement odds over Gmail.
2. `arxiv.org` → "Submit" → start a new submission.
3. Licence: choose **CC BY 4.0** unless you have a reason not to.
4. Category: **primary `cs.CR`** (Cryptography and Security), **cross-list
   `cs.CL`** (Computation and Language). That pairing fits this paper well.
5. Upload a `.tar.gz` containing exactly these four files — arXiv compiles your
   LaTeX itself, so send source, not just a PDF:
   - `bharat_scam_x.tex`
   - `refs.bib`
   - `bharat_scam_x.bbl`  ← **this one matters.** arXiv doesn't always run
     BibTeX, so ship the generated `.bbl` or your references come out empty.
   - `fig1_gap.pdf`
6. Paste the abstract into the abstract box as **plain text** — strip the LaTeX
   commands (`\bsx`, `\emph{}`, `$...$`). arXiv's box doesn't render them.
7. Check the compiled preview arXiv generates. If it fails, the error is almost
   always a missing figure or a `.bbl` you forgot.
8. Submit. Moderation typically takes 1–3 business days. You'll get a permanent
   arXiv ID and a URL like `arxiv.org/abs/2609.XXXXX`.

The tarball is already built for you: `arxiv_submission.tar.gz`.

## For your resume

Once it's live:

> Attanti, R. (2026). *Beyond Keywords: Attack Signatures and a Diagnostic
> Benchmark for Multilingual Scam Detection in Indian Languages.*
> arXiv:2609.XXXXX

Call it a **preprint**, not a "published paper". arXiv is not peer-reviewed, and
anyone technical who reads your resume knows the difference. Claiming peer review
you don't have is the kind of thing that ends interviews.

## If you want it actually peer-reviewed later

Reasonable targets, roughly in order of ambition:
- **Workshop at an NLP venue** (e.g. a low-resource-languages or NLP-for-social-good
  workshop) — most realistic first acceptance, and workshop papers are real
  publications.
- **LREC** — corpus and resource papers are exactly its remit, which fits this.
- **ACL/EMNLP Findings** — would need the transformer baselines added first.

Before any of those, add a MuRIL or LaBSE baseline. That is the single biggest
gap reviewers will name, and it's a day of work with a GPU.

## Avoid

Any venue that emails you an invitation, promises review in 72 hours, or charges
a publication fee for a student paper. IJSER, IJRASET, IJARIIE and similar are
pay-to-publish. Indian tech recruiters and grad committees recognise these names
and read them as a negative signal — a predatory publication is worse on your
resume than no publication.
