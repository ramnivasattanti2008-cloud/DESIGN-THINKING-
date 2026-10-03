# Diagnostics

Target: about 350 words.

> Short section. One formula and one sentence of intuition per metric.

## What this section must establish

1. Define four metrics: CLSC, semantic-flip sensitivity, compositional recovery, open-set AUROC

## Facts you can use

- CLSC: mean pairwise sigma within a parallel group, averaged over groups
- Flip-success threshold is a risk drop of at least 0.5
- Open-set scored by maximum softmax probability

## Answer these in your own words

**Q1.** Why 0.5 as the flip threshold and not 0.1? What does a model that drops risk 0.99 to 0.60 still do to the user?

**Q2.** CLSC measures self-consistency, not correctness. Why is that worth measuring on its own?


---

## YOUR DRAFT

<!-- Write below this line. Don't paste anything from elsewhere. If you get
     stuck on a sentence, write it badly first and fix it on the second pass. -->


