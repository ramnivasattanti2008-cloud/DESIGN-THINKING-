# BHARAT-SCAM-X — Viva / defence notes

Read this before you submit. If you can answer the questions in Section 4 you
will be fine. If you can't, fix that first — a paper you can't defend is worth
less than a plain assignment.

---

## 1. What the paper actually claims

**Claim:** In-distribution accuracy is a poor proxy for whether a scam detector
has understood an attack, and we can demonstrate the gap quantitatively.

**Not claimed:** that this system is deployable, that the numbers predict
real-world performance, or that we beat any existing production system. The
paper says this explicitly in three places. Do not overstate it in your
presentation — overstating is what gets papers torn apart.

**The three headline numbers:**

| Finding | Number | Where |
|---|---|---|
| Best lexical model, in-distribution macro-F1 | 0.942 | Table 3 |
| Same model, flip-success on minimal-edit pairs | 0.175 | Table 5 |
| Structured model, exact signature recovery on recombinations | 0.056 | Table 6 |

The story in one sentence: *a model that looks 94% correct recovers the right
attack structure 5.6% of the time when familiar pieces are combined in an
unfamiliar way.*

---

## 2. Why each design decision was made

**Why a synthetic corpus instead of scraping real scam SMS?**
Because the two central experiments are impossible on scraped data. To measure
cross-lingual consistency you need *the same attack* in nine languages — that
parallel data doesn't exist in the wild. To measure semantic-flip sensitivity you
need pairs that differ by one clause and flip the label — you can't find those,
you have to build them. SCAN, COGS and CheckList are all synthetic for the same
reason, and all are heavily cited. The cost is that absolute numbers mean
nothing outside the corpus, which the paper states.

**Why is `refrain` a value in the ACTION vocabulary?**
It is the single mechanism that lets the schema distinguish "share your OTP"
from "never share your OTP". Without it, an attack and its advisory have
identical signatures and the whole framework collapses. This is the most
important single design decision in the paper.

**Why derive risk from the signature instead of learning it directly?**
Because it forces the model to change its *account of the attack* in order to
change its risk score. A directly-learned risk head can move its output for
reasons unrelated to structure, which would make the flip metric measure
nothing.

**Why put flips for 5 of 10 families in training?**
Critical point — examiners may probe this. If `refrain` never appeared in
training, no model could ever predict it, and failing the flip test would be
logically guaranteed rather than informative. By supervising half the families,
the held-out flip suite measures whether the attack/advisory distinction
*transfers*. That makes the result meaningful.

**Why is macro-F1 reported on mixed conditions rather than per-suite?**
Because several suites are single-class. Reporting "accuracy" on an all-attack
suite rewards a model that always says "attack". Every condition in Table 3
contains both classes for exactly this reason.

**Why no BERT/MuRIL baseline?**
Honest answer: PyTorch could not be installed in the environment the experiments
were run in. The paper states this as a limitation rather than hiding it, and
predicts multilingual encoders would improve the cross-lingual column
specifically. If an examiner asks "why didn't you use a transformer" — that is
the answer, and saying it plainly is much stronger than inventing a
methodological justification.

---

## 3. Two bugs that were found and fixed — good material to mention

Mentioning these shows you understand the methodology rather than just running
scripts. Examiners respond well to this.

**Bug 1 — class collapse.** The first corpus version was 94% attacks. Every
trained model learned to always predict "attack" and scored ~1.00 on all-positive
suites. Looked like a great result; was an artifact. Fixed by adding 74 generic
benign messages across all nine varieties, bringing training to 229 attack / 127
benign.

**Bug 2 — train/test leakage.** Deduplication originally only checked two of the
suites, leaving 8 test messages string-identical to training messages. Now no
test item matches any training item in any suite. Results barely moved, which is
itself worth knowing — it means the earlier numbers weren't driven by leakage.

There was also a third fix worth knowing: the first version of the semantic flip
rewrote the whole message, giving only 0.246 token overlap. That doesn't support
calling it a "minimal edit". It was rebuilt to share the prefix and pretext
exactly, raising overlap to 0.552.

---

## 4. Questions you should be ready for

**"Isn't this just a keyword problem with extra steps?"**
No — the keyword baseline is in the paper and it's the *worst* model on every
condition (0.028 flip-success). The point of including it is to show that the
naive approach fails, and then to show that the sophisticated approach fails
too, differently.

**"Your data is fake, so what does this prove?"**
It proves something about models, not about the world. The corpus is an
instrument for measuring model behaviour under controlled contrast, the same way
a test suite measures software behaviour. It does not estimate field accuracy
and the paper never claims it does.

**"Why does the structured model do worse cross-lingually?"**
Because it must get six fields right instead of one bit. Six chances to fail
versus one. This is stated in the Results section — structure is not free.

**"What is sigma (σ) and why weight it 6/8 to 2/8?"**
σ is signature agreement: fraction of matching single-valued fields plus Jaccard
on the two set-valued fields, weighted by field count (6 single, 2 set-valued).
The weighting is by cardinality, not tuned. Note the structured baseline never
predicts the set-valued fields, which caps its mean σ near 0.75 even at perfect
core accuracy — that's why Table 6 shows σ=0.750 alongside exact-core=1.000.

**"Why threshold the flip at a 0.5 risk drop?"**
Because a security-meaning inversion should move risk across the decision
midpoint, not just nudge it. A model that drops risk 0.99→0.60 still blocks the
advisory. The threshold encodes the operational requirement.

**"Is AUROC 0.905 on open-set a good result?"**
It's an *easy* suite and the paper says so. The two held-out families introduce
new vocabulary, so their novelty is lexically visible. A hard open-set case is a
new pretext in familiar words. This is the weakest of the five diagnostics and
the paper flags it rather than claiming it as a win.

---

## 5. Weaknesses to own, not hide

If you raise these before the examiner does, you look rigorous. If they raise
them first, you look caught out.

1. **Non-English text has not been reviewed by native speakers.** The Telugu,
   Tamil and Kannada realisations were authored without independent linguistic
   review. Stated in Limitations. If you have friends who speak these — getting
   them to check is the single cheapest improvement available to you.
2. **Template artifacts may be partly learnable** — attacks and benign items come
   from different generators, so a model could exploit generation quirks. Mitigated
   but not eliminated.
3. **Small scale.** 1,823 items, 12 families, 9 varieties. Bengali, Marathi,
   Gujarati, Malayalam, Odia, Punjabi all absent.
4. **The risk function ρ is stipulated, not calibrated** against any harm data.

---

## 6. Honest positioning

This is a **framework-and-benchmark paper**, the kind that proposes a way of
measuring something and demonstrates the measurement matters. That is a real and
recognised contribution. It is not a state-of-the-art systems paper, and if you
present it as one you will be caught, because there is no SOTA comparison in it.

The strongest thing you can say: *"Existing evaluation hides these failures. Here
is a way to see them, and here is evidence that they're large."*
