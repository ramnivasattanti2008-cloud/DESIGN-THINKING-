# How this works

You write the paper. I answer questions, check your facts, and tell you when
something is wrong. I don't write your sentences.

That's the whole deal, and it's the only version that survives a viva.

---

## The order

Don't go top to bottom. Go easiest first, so you build momentum.

| Order | File | Why this order |
|---|---|---|
| 1 | `01-introduction.md` (just Q1) | The scam message you've actually seen. Nobody can write this but you. |
| 2 | `07-limitations.md` | Easiest section in the paper. You're just listing what's wrong, and it's all in the file. |
| 3 | `08-ethics.md` | Two paragraphs. |
| 4 | `04-corpus.md` | Describing what exists. No argument needed. |
| 5 | `03-framework.md` | Definitions. |
| 6 | `05-metrics.md` | Definitions. |
| 7 | `06-results.md` | Now you argue. Three questions, three paragraphs. |
| 8 | `01-introduction.md` (rest) | Easier once you know what you're introducing. |
| 9 | `02-related-work.md` | Last, because it needs you to have read a few abstracts. |

Rough total: 4 to 6 hours. Spread it over two evenings.

## The loop

1. Open a section file
2. Answer the questions under "Answer these in your own words". Just answer them, in any order, badly
3. Those answers *are* the section. Join them up, cut what repeats
4. Send it to me. I'll tell you what's factually wrong, what's unclear, and what a reviewer would attack
5. You revise

I'll flag problems. I won't rewrite your sentences, because then they stop being
yours and we're back where we started.

## Rules for yourself

**Never invent a number.** Every figure is in `FACTS.md`. If one you want isn't
there, ask me and I'll compute it from the data.

**Write badly first.** A bad sentence you can fix beats a blank page. Nobody
writes a good first draft.

**Don't try to sound like a paper.** Papers sound like papers because of what
they contain, not how they're phrased. "The model gets this wrong 94% of the
time" is fine. You can tidy it later.

**If you don't understand something, ask.** Don't write around a gap. If you
can't explain why `refrain` is in the action vocabulary, ask me and I'll explain
it until it clicks. That's what I'm for here.

## Two things that make the work itself more yours

**Get the Indic text checked.** Find Telugu, Tamil and Kannada speakers on campus.
Have them read the messages in `data/bharat_scam_x.jsonl` and flag anything that
sounds wrong. Fix it, regenerate, note what changed. That's original work and it
removes a stated limitation.

**Run one more baseline.** Install MuRIL or LaBSE in Google Colab, feed it through
the existing harness, report the numbers. It's the first gap a reviewer names.
One day's work. After that, the cross-lingual result is one you produced.

Do either and the paper stops being something you're nervous about.

## Keep the acknowledgement

The AI-assistance note stays in. Under AICTE rules unacknowledged AI content is
plagiarism, while acknowledged assistance with your own research and your own
words is allowed. Check whether JAIN has a declaration form. If it does, filling
it in takes five minutes and closes the question for good.

## Start now

Open `01-introduction.md`. Answer Q1 only: describe a scam message you've actually
received, what it said, what language, what it wanted.

Three sentences. Send them to me when you're done.

---

## Keeping the similarity score down

You're aiming at a number stricter than anyone asks for. UGC's own threshold is
10%, and under that is simply accepted. A real original paper usually lands
somewhere around 3 to 8%, because technical terms match no matter who wrote them.
"Logistic regression", "one-time password", "false positive rate", your own
reference list. None of that is plagiarism and none of it is avoidable.

Under 1% is close to impossible for any genuine paper. Don't chase it.

Two settings worth asking your department to turn on before they run the check:
exclude bibliography, and exclude quoted material. Both are standard Turnitin
options and together they usually cut the number in half. Your reference list is
488 words, about 10.5% of the document, and it matches by design because
citations are meant to be verbatim.

Now that you're writing it yourself, there's one place real similarity can creep
in: Related Work. You'll be reading abstracts and then writing about them, and
phrasing sticks.

The fix is mechanical. Read the abstract. Close the tab. Then write what it said.
If you can't say it without looking, you haven't understood it yet, and going
back to read it again is the right move rather than paraphrasing around the gap.

Never paste a sentence into your draft "to reword later". It never gets reworded.
That's how copied phrasing ends up in a final submission, and it's the single most
common way honest students fail a similarity check.
