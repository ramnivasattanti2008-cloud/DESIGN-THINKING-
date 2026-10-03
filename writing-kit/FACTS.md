# Every number, in one place

Pull from here when you write. Don't invent a figure and don't round from
memory. If a number you want isn't here, ask me and I'll compute it rather than
guess.

All of this came out of `src/evaluate.py` with seed `20260920`.

---

## Corpus

| | |
|---|---|
| Total messages | 1,823 |
| Unique strings | 1,563 (some items serve two diagnostic suites) |
| Training split | 356 (229 attack / 127 benign) |
| Test split | 1,467 |
| Attack families | 12 |
| Language varieties | 9 |
| Mean message length | 15 words |
| Train/test text overlap | 0 |

**Varieties.** Seen in training: English (en), Hindi Devanagari (hi), Hindi
romanised (hi_Latn). Held out, zero-shot: Telugu (te), Telugu romanised
(te_Latn), Tamil (ta), Kannada (kn), English-Hindi code-mixed (cm_hi),
English-Telugu code-mixed (cm_te).

**Contrast pairs.** 143 held-out pairs. Mean token-level Jaccard overlap
**0.552**.

---

## Table 1: macro-F1 by condition

Condition sizes: IID n=104 (+71/-33), Cross-ling n=740 (+506/-234),
Semantic-flip n=293 (+143/-150), Compositional n=339 (+72/-267),
Open-set n=438 (+171/-267).

| Model | IID | Cross-ling | Sem. flip | Composit. | Open-set |
|---|---|---|---|---|---|
| Keyword rule | 0.706 | 0.686 | 0.570 | 0.747 | 0.640 |
| TF-IDF word + LR | 0.917 | 0.943 | 0.677 | 0.891 | 0.946 |
| TF-IDF char + LR | 0.942 | 0.936 | 0.700 | 0.921 | 0.965 |
| Struct-Sig (ours) | 1.000 | 0.888 | 0.781 | 0.918 | 0.920 |

## Table 2: false-positive rate on benign text

Lower is better. "Semantic flips" are genuine security advisories.

| Model | Hard negatives | Semantic flips | Generic benign |
|---|---|---|---|
| Keyword rule | 0.200 | 0.420 | 0.000 |
| TF-IDF word + LR | 0.382 | 0.560 | 0.009 |
| TF-IDF char + LR | 0.273 | 0.507 | 0.000 |
| Struct-Sig (ours) | 0.000 | 0.293 | 0.000 |

## Table 3: semantic flip sensitivity (143 pairs)

| Model | Flip-success | Mean risk drop | Token overlap |
|---|---|---|---|
| Keyword rule | 0.028 | 0.063 | 0.552 |
| TF-IDF word + LR | 0.189 | 0.256 | 0.552 |
| TF-IDF char + LR | 0.175 | 0.277 | 0.552 |
| Struct-Sig (ours) | 0.559 | 0.494 | 0.552 |

## Table 4: signature recovery (Struct-Sig only)

| Suite | n | Exact core | Mean σ | actor | pretext | target | intent | action | stage |
|---|---|---|---|---|---|---|---|---|---|
| In-distribution | 71 | 1.000 | 0.750 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Cross-lingual | 506 | 0.642 | 0.600 | 0.793 | 0.708 | 0.844 | 0.765 | 0.919 | 0.773 |
| Compositional | 72 | **0.056** | 0.441 | 0.431 | 0.319 | 0.667 | 0.611 | 0.681 | 0.819 |
| Open-set | 171 | 0.000 | 0.342 | 0.000 | 0.000 | 0.889 | 0.468 | 0.959 | 0.421 |

Note: mean σ caps near 0.75 even at perfect core accuracy, because the
structured baseline never predicts the two set-valued fields (tactic, evidence).
Say this in the paper. It's the kind of detail that shows you understand your own
metric.

Note: actor = 0.000 on open-set is true by construction. The two held-out
families use actor values (`investment_platform`, `known_person`) that never
appear in training, so the classifier cannot emit them. Expected, not surprising.

## Table 5: cross-lingual consistency

CLSC: 0.837 across all nine. 1.000 on the three seen varieties. 0.787 on the six
held out.

Agreement with gold, per variety:

| Variety | σ |
|---|---|
| cm_hi | 0.750 |
| en | 0.750 |
| hi | 0.750 |
| hi_Latn | 0.750 |
| cm_te | 0.738 |
| kn | 0.625 |
| ta | 0.613 |
| te_Latn | 0.475 |
| te | 0.450 |

## Table 6: open-set

Maximum-softmax-probability over the family head. Known n=577, unknown n=171.
**AUROC 0.905.** Call this an easy suite and say why: the two held-out families
bring in vocabulary absent from training, so novelty is lexically visible.

---

## External facts

India, calendar year 2025, Ministry of Home Affairs figures tabled February 2026:
roughly **28.15 lakh** cybercrime complaints and about **₹22,495 crore** in
reported losses. Investment scams accounted for 76% of money lost.

---

## The eight signature fields

actor, pretext, target, intent, action, stage (single-valued) plus tactic,
evidence (set-valued). Agreement σ weights the six single-valued fields 6/8 and
the two set-valued 2/8, using Jaccard on the sets.

The `action` vocabulary includes **`refrain`**, meaning an instruction *not* to
do something. This is the value that separates an attack from the advisory
warning against it.

---

## References you'll cite

| Topic | Citation |
|---|---|
| SMS spam baseline | Almeida, Gómez Hidalgo & Yamakami, DocEng 2011 |
| SMS scam robustness | Salman, Ikram & Kaafar, arXiv:2210.10451 |
| Smishing corpus | Timko & Rahman, SmishTank, 2024 |
| Indic encoders | Khanuja et al., MuRIL, arXiv:2103.10730 |
| Indic benchmarks | Kakwani et al., IndicNLPSuite, Findings of EMNLP 2020 |
| Sentence embeddings | Feng et al., LaBSE, ACL 2022 |
| Behavioural testing | Ribeiro et al., CheckList, ACL 2020 |
| Contrast sets | Gardner et al., Findings of EMNLP 2020 |
| Compositionality | Lake & Baroni, ICML 2018; Kim & Linzen, EMNLP 2020 |
| Open-set | Scheirer et al., TPAMI 2013; Hendrycks & Gimpel, ICLR 2017 |
| LLM phishing | Hazell, arXiv:2305.06972; Chen et al., PEEK, arXiv:2411.11389 |
| Persuasion | Cialdini, *Influence*, 2007 |

All verified. The full BibTeX is in `paper/refs.bib`.
