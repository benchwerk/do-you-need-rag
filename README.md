# do-you-need-rag

Three ways to let an AI model answer questions from your own documents, tested with the same model, the same 20
questions and the same instruction on 10, 100 and 1,000 pages of GitLab's public handbook:

- **Paste:** put every document in the prompt.
- **Agent search:** let the model search the folder itself (Read, Grep and Glob only).
- **Baseline RAG:** embed 300-word chunks locally and put the 20 most similar chunks in the prompt.

This repository holds the harness, every answer and transcript, the grades, the vector search timings and the scripts
that compute every number in `findings.json`.

**Scope, stated first.** One set of English prose documents, up to 1,000 files; one model (Sonnet 5.5) in one harness
(Claude Code 2.1.286, which is built for agent search); baseline RAG with no reranking, hybrid search or tuning; one
answer per question per setup; AI graders. Details: `methodology.md`.

## Results

Correct answers out of 10 per group, at 10 / 100 / 1,000 files; the last two columns count answers out of all 20
(`findings.json` `scores_main`):

| Method | Literal questions | Paraphrased questions | Said it couldn't find it | Wrong |
| :-- | :-- | :-- | :-- | :-- |
| Paste | 10 / 10 / did not fit | 10 / 9 / – | 0 / 0 / – | 0 / 1 / – |
| Agent search | 10 / 10 / 10 | 9 / 9 / 8 | 0 / 0 / 0 | 1 / 1 / 2 |
| Baseline RAG | 10 / 10 / 9 | 8 / 7 / 6 | 2 / 2 / 2 | 0 / 1 / 3 |

- **At 10 files the three methods are close:** paste 20, agent search 19, RAG 18 of 20.
- **Paste stops fitting.** At 100 files it sends 478,819 tokens per answer, 30 to 33 times what agent search or RAG
  sends; the 1,000-file prompt would be about 3.0 million tokens by the characters ÷ 4 estimate and was not run.
- **Every RAG miss is a search miss.** In all 10 misses the chunk holding the answer was not among the 20 retrieved; in
  all 50 cases where it was, RAG answered correctly. As the set grows, the answer chunk falls down the ranking (for one
  question: 15th, 75th, 641st). Four of the 10 misses are confident wrong answers, not "couldn't find it".
- **Paraphrased questions went against the prediction.** Before the runs, RAG was predicted to beat agent search on
  paraphrased questions at 1,000 files. Agent search scored 8 and RAG 6.
- **A vector database made no difference at these sizes.** NumPy, sqlite-vec and Qdrant returned the same top 20 for
  every query; median search times were 0.37 ms, 11.7 ms and 0.95 ms (server-reported) at 6,644 chunks. Qdrant built no
  index on its default settings, so it also searched every vector.
- **The usual token estimate is low.** Real tokens were 1.36 to 1.39 times the characters ÷ 4 estimate.

Every finding, with its source field, the prediction check and the limits: `NUANCES.md`.

## Layout

| Path | Contents |
| :-- | :-- |
| `methodology.md` | documents, questions, methods, setup, runs, scoring, search timing |
| `prediction.md` | the predictions, written before any run |
| `NUANCES.md` | every finding with its source field in `findings.json`; prediction check; limits |
| `findings.json` | every reported number, computed by `analysis/findings.py` |
| `bench/` | the harness exactly as it ran: set building, indexing, answering, scoring, search timing; the frozen questions |
| `corpus/` | the handbook commit and licence; the file list of each set |
| `results/2026-11-01_x86-laptop_dry/` | dry run: one question through every setup (cost check) |
| `results/2026-11-02_x86-laptop_main/` | main run and repeats: `raw.jsonl` (192 answers), `streams/` (transcripts), `rag_passages.json` |
| `results/2026-11-05_x86-laptop_search/` | vector search timings |
| `scoring/` | blind sheet, key, both graders' grades, final grades; how grading worked |
| `demos/` | short demonstrations built from the data (`takes.json` lists them) and the three extra sessions for D1 (takes 1 and 2 were not used; `takes.json` says why) |
| `analysis/` | `findings.py` and `rag_passages.py` |
| `editorial_log.md` | the independent reviews of this work |

## Reproduce the numbers

From the published data (standard library only, except the passage check):

```
python analysis/findings.py
```

`findings.py` also counts the words in the three sets and reads the demo outputs, so it needs the sets folder named in
`bench/config.json` (`sets_dir`). `analysis/rag_passages.py` needs the embedding index (step 4 below).

## Reproduce the runs

Windows, Python 3.12+, a Claude Code login (subscription); the commands are as they ran.

1. Download the handbook at the commit in `corpus/SOURCE.txt` as a `.tar.gz`
   (`https://gitlab.com/gitlab-com/content-sites/handbook/-/archive/<commit>/handbook-<commit>.tar.gz`) and check its
   SHA-256.
2. `python -I bench/extract_handbook.py <archive> internal/corpus/all`
3. `python -I bench/build_sets.py internal/corpus/all internal/corpus/sets`, then copy the three set folders to the
   `sets_dir` in `bench/config.json` (`C:/ragdemo/sets`). Compare the file lists with `corpus/sets.json`.
4. `python -m venv .venv`, `.venv/Scripts/pip install -r bench/requirements.txt`, then `.venv/Scripts/python
   bench/index.py internal/index` (downloads the embedding model on first use).
5. Answer: set `CLAUDE_BIN` to the Claude Code 2.1.286 executable and `CLAUDE_CONFIG_DIR` to a separate, logged-in
   configuration, then `.venv/Scripts/python bench/run.py <results dir> --plan main` (and `--plan repeats --methods
   agent,rag`, `--plan dry`; paste had no repeats). Runs resume where they stopped; see the usage line in `bench/run.py`
   for the quota options.
6. Grade: `python bench/score.py sheet <results dir> <scoring dir>`, grade `sheet.json` into `grades_agy.json` (and a
   second pass into `grades_hand.json`, one grade per item), then `python bench/score.py merge <results dir> <scoring
   dir>`.
7. Search timing: start Qdrant 1.20.0 on `localhost:6333`, then `.venv/Scripts/python bench/search_timing.py <results
   dir>`.

New answers will differ in wording from the ones here; grades and timings may differ too.

## Licence

Code (`bench/*.py`, `analysis/`, `demos/demos.py`): MIT (`LICENSE`). Data and documents: CC BY-SA 4.0 (`LICENSE-DATA`),
because they contain text from the GitLab Handbook, © GitLab, CC BY-SA 4.0 (`corpus/SOURCE.txt`).
