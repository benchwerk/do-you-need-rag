# Editorial log

Reviews of this work, in order. Each independent review is a separate AI review session given only the files, with no
prior context.

| Date | Review | Outcome |
| :-- | :-- | :-- |
| 2026-11-01 | Question list: a separate AI session checked the 20 draft questions for leaked answers and bias | 8 findings; 7 applied, then the list was frozen (sha256 `adb22f0b…`) |
| 2026-11-06 | Grading: a first AI grader on every answer, a second AI pass on 51 | 11 grades changed (`scoring/README.md`) |
| 2026-11-06 | Independent review 1 of the findings: recomputed the score tables, repeats, token and time medians, search medians and the passage table from the raw data | numbers matched; 10 text issues (an unclear search-time comparison, two token figures for the same estimate, overstated wording); all fixed; a second pass found no remaining issues |
| 2026-11-06 | Independent review 2 of this repository, before publication: numbers, consistency, tone, paths, privacy, reproduction of both analysis scripts on a clean copy, licences | both analysis scripts reproduced their outputs byte for byte; no wrong number and no leak; 6 major and 12 minor issues (wording written for another audience, an undisclosed internal model, the repeat command, grader naming, sampling wording); all fixed |

## Corrections

- 2026-11-06: the scoring notes named the gift question P7; it is P9.
