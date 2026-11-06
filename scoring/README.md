# Scoring

All 192 answers from `results/2026-11-02_x86-laptop_main/raw.jsonl` were graded on 2026-11-06 with `bench/score.py` (it
was run with these files in a working folder; they are published here unchanged). The final grade of every answer is in
`scores.json`.

## Grades

- **correct:** the answer gives the answer key's fact.
- **wrong:** a different answer, including anything invented.
- **not_found:** the answer says the documents do not contain it and does not commit to a different answer, even if it
  adds related guidance. This rule was settled during the second pass; the first grader had graded 8 such answers as
  wrong.

## How

1. **Blind sheet** (`sheet.json`): every answer with its question, answer key and source sentence; method, set size and
   file names hidden (file names and backtick spans replaced by `[file]`); order shuffled with seed 9. `key.json` maps
   each item back to its run.
2. **First grader** (`grades_agy.json`): Gemini 3.8 Flash (in the Antigravity CLI), read-only, no tools, in six parts of
   32 items, graded every item.
3. **Second pass** (`grades_hand.json`): Claude Opus, reading the same blind sheet, re-graded every item where the first
   grader said not correct, every item where the answer key's pattern did not match (`key_match` in the raw records),
   and each remaining item with probability 0.2 (seed 2026; 27 items drawn): 51 items in all. Where the two differ, the
   second pass is final. 11 of 51 changed. `hand_todo.json` is the list of items still waiting for a second-pass grade:
   empty.

No person graded: "hand" in `grades_hand.json`, `hand_todo.json` and the `hand` fields of `scores.json` and
`findings.json` names the second AI pass, as does "by hand" in the docstring of `bench/score.py`. Blinding is partial: agent search answers often name the section they came
from, which hints at the method.

## The 11 changed grades

| Item | First grader | Final | Why |
| :-- | :-- | :-- | :-- |
| A058, A102, A111, A155, A182 | wrong | not_found | say the rule isn't in the documents; a manager is mentioned only as an optional suggestion |
| A081 | wrong | not_found | says nothing in the documents addresses it |
| A131, A160 | wrong | not_found | say there is no turnaround target |
| A113 | wrong | correct | gives the token-value rule and notes the real conflict between two pages |
| A127, A166 | wrong | correct | state the rule (all written communication in English); "probably not" hedges the wording only |

## Two questions where the documents disagree

- **P4 (Spanish):** the handbook says all written communication is in English, and also allows a few phrases in another
  language in one-to-one messages. Answers that hedge reflect a real conflict, so results are also reported without P4.
- **P9 (gift to a government official):** two pages disagree (token value against nothing of value). Answers that give
  the token-value rule and note the conflict were graded correct.

## The answer-key pattern alone overstates RAG

9 answers match the answer key's pattern but are not correct. Five of them are RAG's five answers to P8 at 100 files
(the main run and four repeats): each mentions a manager only in a hedge, and says the documents do not cover the
question (`findings.json` `grading.script_match_but_final_not_correct`).

Scores per method and size: `NUANCES.md`, section 1.
