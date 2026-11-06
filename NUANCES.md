# Findings and nuances: do you need RAG?

Every number here comes from `findings.json`, produced by `analysis/findings.py`. The field is named in brackets.
- **Setup:** one machine (`x86-laptop`); Claude Code 2.1.286 with `claude-sonnet-5-5`, one fresh session per answer; 20
  frozen questions (sha256 `adb22f0b…`).
- **Documents:** subsets of GitLab's public handbook at a pinned commit, licensed CC BY-SA 4.0.
- **Method:** `methodology.md`. Scoring: `scoring/README.md`.
- **Sample size:** one answer per question per setup, plus 4 questions × 5 runs at 100 files. With 10 questions per
  group, a difference of 1 or 2 answers is within noise.

## 1. Scores

Correct answers, main run [`scores_main`]. Each method is shown at 10 / 100 / 1,000 files.

| Method | Document's words (literal) | Reworded (paraphrased) | Couldn't find it | Wrong |
| :-- | :-- | :-- | :-- | :-- |
| Paste | 10 / 10 / – | 10 / 9 / – | 0 / 0 / – | 0 / 1 / – |
| Agent search | 10 / 10 / 10 | 9 / 9 / 8 | 0 / 0 / 0 | 1 / 1 / 2 |
| Baseline RAG | 10 / 10 / 9 | 8 / 7 / 6 | 2 / 2 / 2 | 0 / 1 / 3 |

Totals [`scores_main.<method>.total`]:

| Method | All questions | Reworded only | Without P4 |
| :-- | --: | --: | --: |
| Paste | 39/40 | 19/20 | 38/38 |
| Agent search | 56/60 | 26/30 | 55/57 |
| Baseline RAG | 50/60 | 21/30 | 48/57 |

**Repeats at 100 files** [`repeats_100_files`], 4 questions × 5 runs:
- Agent search: 20/20.
- RAG: 15/20. All 5 misses are P8 (the full team calendar), "couldn't find it" every time. For P8, RAG's result
  repeated: its search returns the same chunks for the same question.
- Paste had no repeats: at 100 files each paste answer used about 12% of the five-hour subscription limit (section 4).

**P4 (Spanish) is a weak question.** The handbook says all written communication is in English. It also allows a few
phrases in another language in one-to-one messages. 4 of the 15 misses are P4: agent search twice, paste and RAG once
each [`misses_main`]. The "Without P4" column removes it.

## 2. Why RAG missed: the search, not the model

Recomputing RAG's search for every question and size reproduces the logged chunks exactly in 60 of 60 cases
[`rag_passage.retrieval_matches_logged_files`]. For each case, `analysis/rag_passages.py` checks whether the chunk
holding the answer sentence was in the top 20:

| | RAG correct | RAG not correct |
| :-- | --: | --: |
| Answer chunk in the top 20 | 50 | 0 |
| Answer chunk not in the top 20 | 0 | 10 |

**Every RAG miss is a search miss, and every search hit was answered correctly** [`rag_passage`].

**More files push the answer down.** As the set grows, other text crowds the answer chunk out of the top 20. Its rank
among all chunks [`rag_passage.best_rank_by_set`]:

| Question | 10 files | 100 files | 1,000 files |
| :-- | --: | --: | --: |
| P10 (password sensitivity) | 15 | 75 | 641 |
| P8 (calendar full) | 28 | 37 | 157 |
| P5 (recording time) | 28 | 35 | 111 |
| L3 (renewal) | 6 | 9 | 43 |

Two reworded questions (P5 and P8) miss at every size, because their words share little with the handbook's ("taped" for
recording; "too many of us are away" for "PTO capacity has been reached").

**How RAG answers when it misses** [`misses_main`]:
- Six times it says it couldn't find the answer.
- Four times it gives a confident answer built from nearby text. Examples:
  - L3 at 1,000 files: "about Day 270 … roughly three months before", from a different team's renewal page. The expected
    answer is "at least 90 days".
  - P8 at 1,000 files: "coordinate with your team", from a team-specific page.

These are the misses that look fine.

**The source file is not enough.** In 6 of the 10 misses, the source file was among the 20 chunks
[`rag_misses_source_retrieved`], but its answer passage was not. RAG reads chunks, not files.

## 3. Why agent search missed

- **Misses:** 4 in the main run, all on reworded questions [`misses_main`]:
  - P4 twice
  - P2 at 100 files: it found Finance's three-day approval target on another page
  - P10 at 1,000 files: "treat it as a secret", from the password pages
- **Wrong, not "couldn't find it":** every agent miss is a plausible answer from a related page. None says it couldn't
  find the answer.
- **Searching is short:** a median of 1 tool call at 10 and 100 files, 2 at 1,000. At most 9 [`cost_main.agent`]. That
  leaves room to try other words.

## 4. Size and cost

**Size** [`sets`, `cost_main.paste`]:

| Set | Files | Words | Tokens (chars ÷ 4 estimate) | Real paste tokens per answer |
| :-- | --: | --: | --: | --: |
| 10 files | 10 | 58,813 | 100,558 | 137,092 |
| 100 files | 100 | 187,732 | 343,128 | 478,819 |
| 1,000 files | 1,000 | 1,586,225 | 3,011,870 | did not fit |

**The usual estimate is low.** Real tokens were 1.36× (10 files) and 1.39× (100 files) the characters ÷ 4 estimate of
the whole prompt [`real_over_est_tokens`]. For a quick size check (`demos/out/D2_size.json`), multiply the estimate by
about 1.4.

**At 1,000 files, paste was not run.** The full prompt was about 3.0 million tokens by the estimate (3,035,277 including
the instruction and document tags), over three times the 900,000 limit set before the runs [`cost_main.paste.large`].
With the 1.4× correction, it is about 4 million real tokens.

**Tokens per answer** (median, input including cache) [`cost_main`]:

| Method | 10 files | 100 files | 1,000 files |
| :-- | --: | --: | --: |
| Paste | 137,092 | 478,819 | – |
| Agent search | 13,665 | 14,494 | 17,958 |
| RAG | 15,974 | 15,880 | 16,128 |

- At 100 files, paste sends 30 to 33 times what agent search or RAG sends.
- RAG stays flat as the set grows; agent search grows slowly (+31% from 10 to 1,000 files).

**Subscription quota, approximate** [`quota_approx`]. This is the median rise of the five-hour meter per answer. Meter
steps are 1%, and the meter is shared with other use of the account.

| Method | Rise per answer |
| :-- | :-- |
| Paste, 10 files | 5% |
| Paste, 100 files | 12% |
| Agent search, any size | under 1% |
| RAG, any size | about 1% |

**Hidden extra calls.** In 169 of 192 sessions Claude Code also made a short internal call to `claude-haiku-4-5` (median 13 output tokens) [`internal_model_calls`]. Median input: 955 tokens for agent search, 10,410 for
RAG and about 97,500 for paste (18 of 40 paste sessions). They are not in the token tables above; the subscription meter
counts all use of the account, so the quota figures already include them.

Paste does not cache between different questions, because the question changes the prompt. Each paste call writes the
whole set to cache again.

**Time per answer** (median seconds, wall clock including start-up) [`cost_main`]:

| Method | 10 files | 100 files | 1,000 files |
| :-- | --: | --: | --: |
| Paste | 7.45 | 4.2 | – |
| Agent search | 8.95 | 7.95 | 6.3 |
| RAG | 5.2 | 3.95 | 4.2 |

The differences are seconds, and the medians don't follow set size (agent search is fastest at 1,000 files). Treat time
as "all a few seconds", not a ranking.

## 5. The vector database

The same embeddings were searched with three engines; the median of 5 runs × 20 queries is shown [`vector_search`].

| Engine | 241 chunks | 785 chunks | 6,644 chunks |
| :-- | --: | --: | --: |
| NumPy, brute force | 0.024 ms | 0.045 ms | 0.371 ms |
| sqlite-vec | 1.618 ms | 1.713 ms | 11.739 ms |
| Qdrant, server-reported | 0.572 ms | 0.691 ms | 0.95 ms |
| Qdrant, round trip over HTTP | 44.217 ms | 44.515 ms | 44.413 ms |

- **Same results:** every engine returned the exact same top 20 as brute force, in every run [`min_overlap_with_exact` =
  1.0].
- **Qdrant built no index at these sizes:** on default settings, `indexed_vectors` was 0, so it also searched
  exhaustively. What it adds here is a server, not a faster search.
- **Qdrant ran in WSL2:** its round trip includes the hop from Windows into WSL2, so quote the server-reported time.
- **Compared with the model, all of these are tiny:** the slowest search median (sqlite-vec, 11.7 ms) is under 0.3% of
  RAG's fastest median answer (3.95 s). Even Qdrant's HTTP round trip (44 ms) is about 1%.

## 6. Prediction check

Predictions were written 2026-11-01, before any run (`prediction.md`).

| # | Prediction | Result | Verdict |
| :-- | :-- | :-- | :-- |
| P1 | At 10 files all three do about equally well (18–20) | paste 20, agent search 19, RAG 18 | right |
| P2 | Paste at 100 files sends over 10× retrieval's tokens | 30–33× (478,819 against 15,880 and 14,494) | right |
| P3 | At 1,000 files paste stops being an option | about 3.0 million tokens by the estimate | right (by estimate; not run) |
| P4 | Agent search: literal beats reworded by 2–4 at 1,000 files | 10 against 8, a gap of 2 | right, at the low edge |
| P5 | Agent search scores 7+ of 10 on reworded questions | 9, 9, 8 | right |
| P6 | RAG beats agent search on reworded questions at 1,000 files, by 1–2 | **RAG 6, agent search 8** | **wrong** |
| P7 | Agent search takes over 2× RAG's time at 1,000 files | 6.3 s against 4.2 s, 1.5× | not confirmed: below 2×, on the 1.5× falsification line |
| P8 | Vector database makes no noticeable difference at these sizes | under 12 ms server-side (brute force 0.37 ms); Qdrant's HTTP round trip about 44 ms | right |
| P9 | Same results with and without a vector database | identical top 20 everywhere | right, but no approximate index was built, so it could not differ |

**P6 was the least certain prediction, and it was wrong.** The likely reason, from section 2: baseline RAG with a small
embedding model and fixed 300-word chunks lost the answer passage on the reworded questions. Agent search could try
several wordings (not tested directly; its median was 1–2 tool calls).

This tests baseline RAG with no reranking, no hybrid keyword search and no tuning. A tuned RAG could do better. That is
stated, not measured.

## 7. Limits

- **The data:**
  - One set of English prose documents, from one company handbook.
  - Up to 1,000 files.
  - One answering model, inside Claude Code, a harness built for agent search. Claude Code also made a short internal call to `claude-haiku-4-5` (median 13 output tokens) in 169 of 192 sessions; those tokens are not
    in the token tables (section 4).
  - Code, or much larger sets, may behave differently.
- **The sample:**
  - 10 questions per group, one main answer each.
  - Within a method, differences of 1–2 answers are within noise.
  - Repeats exist only at 100 files, for agent search and RAG.
- **Grading:**
  - An AI grader (Gemini 3.8 Flash) graded every answer.
  - A second AI grader (Claude Opus, the same blind sheet) re-graded 51 of 192 and changed 11 [`grading`].
  - No person graded; the 11 changes and their reasons are listed in `scoring/README.md`.
  - Blinding was partial: agent search answers often name sections.
  - The script check alone overstated RAG: 9 items matched the answer key but are not correct, 5 of them RAG's five
    answers to P8 at 100 files [`grading.script_match_but_final_not_correct`].
- **The search timing:**
  - Ran on one machine with default settings.
  - Qdrant ran as the official Linux build in WSL2, not Docker.
