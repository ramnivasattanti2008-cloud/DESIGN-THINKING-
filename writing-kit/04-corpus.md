# The corpus

Target: about 500 words.

> The flip-supervision point is the one a sharp reviewer will probe. If you can't explain it, the result looks like a tautology.

## What this section must establish

1. How messages are built
2. The nine varieties and which are held out
3. The splits and why they are what they are

## Facts you can use

- 1,823 messages, 1,563 unique strings, 12 families, 9 varieties
- Seen: en, hi, hi_Latn. Held out: te, te_Latn, ta, kn, cm_hi, cm_te
- 143 contrast pairs, mean token overlap 0.552
- Training: 229 attack / 127 benign
- Flips for 5 of 10 families are in TRAINING
- Seed 20260920, zero train/test text overlap

## Answer these in your own words

**Q1.** Why are flips for half the families in the training set? What would the flip result mean if they weren't?

**Q2.** An earlier version of this corpus was 94% attacks and every model collapsed to always predicting 'attack'. Why does class balance matter here specifically?

**Q3.** Why generate the signature first and the text second, rather than labelling scraped messages?


---

## YOUR DRAFT

<!-- Write below this line. Don't paste anything from elsewhere. If you get
     stuck on a sentence, write it badly first and fix it on the second pass. -->


