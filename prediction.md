# Prediction: do you need RAG?

Written 2026-11-01, **before any run**, from prior published work and judgement. These are predictions, not results; the
results are reported next to them, right or wrong.

Method and terms: `methodology.md`. "Correct" is out of the 20 frozen questions.

| # | Prediction | Expected | Would be wrong if |
| :-- | :-- | :-- | :-- |
| P1 | At 10 files, all three methods do about equally well | each 18–20 of 20 | any method scores under 16 |
| P2 | Pasting costs far more text in the prompt as the set grows | at 100 files, over 10× retrieval's tokens | under 3× |
| P3 | At 1,000 files, pasting stops being a real option | over 200,000 tokens; the run fails or scores below agent search | it fits and scores best |
| P4 | Agent search does better on literal questions than paraphrased ones | a gap of 2–4 of 10 at 1,000 files | no gap, or paraphrased better |
| P5 | The gap is smaller than people expect, because an agent can try other words | agent search at 7+ of 10 on paraphrased questions | under 5 of 10 |
| P6 | Baseline RAG beats agent search on paraphrased questions at 1,000 files | by 1–2 of 10 | agent search wins or ties |
| P7 | Agent search takes longer per answer than baseline RAG | over 2× the time at 1,000 files | under 1.5× |
| P8 | A vector database makes no difference a person would notice at these sizes | search under 100 ms with and without | brute force over 500 ms |
| P9 | A vector database returns the same answers as brute force here | identical or near-identical top results | recall under 0.95 |

**Least certain:** P5 and P6. If agent search also wins on paraphrased questions, the answer gets simpler and the case
for RAG at these sizes weakens; the result is reported either way.

**If the result is boring:** a tie across methods is still the reader's answer: at this size, use the simplest one.

---

Edited for publication on 2026-11-06: the method reference now points to `methodology.md`; the opening and closing
paragraphs were rewritten in the third person; in P2, "on the sheet" now reads "in the prompt", and in the last line
"viewer" reads "reader". SHA-256 of the file as written on 2026-11-01 (18:40 UTC+1):
`32c7ec244355dc98bffd005bea8db04df58b0df1034945b31645bad91399667b`. Every prediction, number and threshold is unchanged.
The results against these predictions: `NUANCES.md`, section 6.
