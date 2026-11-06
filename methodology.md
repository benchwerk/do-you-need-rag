# Methodology

Three ways of answering questions from a set of documents, with the same model, the same instruction and the same
questions, at three set sizes. Only the method changes.

## The documents

GitLab's public handbook at commit `52419353ea755a1ac823553385f8636ff2fcde17` (2026-10-30), CC BY-SA 4.0
(`corpus/SOURCE.txt`). `bench/extract_handbook.py` keeps the markdown pages of `content/handbook/` with at least 150
words, leaving out the sections about individual people and employment: 3,153 pages.

`bench/build_sets.py` builds three nested sets. The 10-file set holds every page needed to answer the questions; the
100- and 1,000-file sets add pages in a fixed hashed order (seed `009-do-you-need-rag`). The file list of each set is in
`corpus/sets.json`.

| Set | Files | Words |
| :-- | --: | --: |
| small | 10 | 58,813 |
| medium | 100 | 187,732 |
| large | 1,000 | 1,586,225 |

## The questions

20 questions in `bench/questions.json`, each with an answer key, the source file, the source sentence and a pattern for
an automatic first check. 10 are **literal** (they use the document's words) and 10 **paraphrased** (same meaning,
different words). Candidates were drafted with AI help, then chosen and edited by hand; every source sentence was
checked against its file, and a separate AI review checked the list for leaked answers and bias. The list was frozen
before any run: sha256 `adb22f0b44168d8078fffe9277fcf4c14ef1168a8438ccaecedbbc68ea3e6a73`, recorded in every raw record.

Literal questions favour keyword search and paraphrased questions favour embeddings; the equal split is a choice, so
every result is reported per group.

## The three methods

Every answer is a fresh, headless Claude Code session (`claude -p`, stream-json output) with this instruction:

> Answer the question using only the company documents. Reply in one or two short sentences. If the documents do not
> contain the answer, say you could not find it.

| Method | What the model gets | Tools |
| :-- | :-- | :-- |
| **Paste** | the whole set's text in the prompt, one `<document>` block per file | none |
| **Agent search** | starts in the set's folder: "The documents are the files in this folder." | Read, Grep, Glob; at most 25 turns |
| **Baseline RAG** | the 20 chunks most similar to the question, one `<excerpt>` block each | none |

Baseline RAG: 300-word chunks with 50 words of overlap (6,644 chunks for the 1,000-file set), embedded locally on CPU
with `BAAI/bge-small-en-v1.5` (384 dimensions) through fastembed; exact cosine search in NumPy; the 20 best chunks go
into the prompt. No reranking, no hybrid keyword search, no tuning (`bench/index.py`, `bench/run.py`).

Paste at 1,000 files was not run: its prompt is about 3.0 million tokens by the characters ÷ 4 estimate, over the
900,000 limit set in `bench/config.json` before any run.

## Setup

| | |
| :-- | :-- |
| Machine | `x86-laptop`, Windows 11 Pro; every comparison on this one machine |
| Model | `claude-sonnet-5-5` through Claude Code 2.1.286 (SHA-256 in `demos/env.json`), Claude Pro subscription, no API key |
| Isolation | a separate Claude Code configuration; `--setting-sources ""`, `--strict-mcp-config`, `--no-session-persistence`, `--disable-slash-commands`; no MCP servers, skills or project files; built-in plugins only |
| Internal calls | Claude Code also made a short internal call to `claude-haiku-4-5` in 169 of 192 sessions (`findings.json` `internal_model_calls`); the token counts in the findings are the answering model's only |
| Python packages | `bench/requirements.txt` |

## Runs

| Part | Answers | Folder |
| :-- | --: | :-- |
| Dry run: one literal question through every setup | 8 (+1 not run: paste at 1,000 files) | `results/2026-11-01_x86-laptop_dry/` |
| Main: 20 questions × 3 methods × 3 sizes, one answer each, 2026-11-02 to 2026-11-05 | 160 (paste at 1,000 files not run) | `results/2026-11-02_x86-laptop_main/` |
| Repeats: 4 questions (L4, L8, P3, P8) × 4 more answers at 100 files, agent search and RAG, 2026-11-05 | 32 | same folder, `rep` 1–4 |

The dry run measured cost before the main run and is not part of the findings, except for its record of paste at 1,000
files. Paste has no repeats: at 100 files each paste answer used about 12% of the subscription's five-hour limit. The 20
questions are the sample; the repeats show how much answers vary. `bench/run.py` stops when the shared usage meter
passes a threshold or a call fails, and keeps a failed call out of the data; no call failed.

Each raw record (`raw.jsonl`) holds the answer, token usage, wall time, tool calls, the usage meters and, for RAG, the
retrieved files and the search time. `streams/` holds every session's stream-json transcript. `bench/run.py` replaces
the home folder and user name anywhere in the output with `<scrubbed>`; in practice only one start-up field
(`memory_paths`) contained them. The D1 demo session uses `<home>` the same way. Nothing else is changed. Timestamps in
`raw.jsonl` are the machine's local time (UTC+1); the transcripts' own timestamps are UTC.

## Scoring

`scoring/README.md`: a blind sheet, an AI grader for every answer, a second AI pass on 51 answers, and three grades:
correct, wrong (including anything invented) and not_found.

## Search timing

`bench/search_timing.py` searches the same embeddings with three engines, for the 20 questions, 5 runs each, at every
set size: NumPy (exact, in memory), sqlite-vec 0.1.9 (`vec0` table, cosine) and Qdrant 1.20.0 (the official Linux build
in WSL2 on the same laptop, default settings, telemetry off, reached over HTTP). For each it logs the median and maximum
time, Qdrant's own reported server time, and the overlap of the top 20 with exact search
(`results/2026-11-05_x86-laptop_search/search.json`).

## Analysis

- `analysis/findings.py` computes `findings.json` from the raw records, the grades, the search timings and the demo
  outputs.
- `analysis/rag_passages.py` recomputes RAG's search for every question and set, checks that it matches the logged
  files, and finds the rank of the chunk holding the answer sentence
  (`results/2026-11-02_x86-laptop_main/rag_passages.json`).
- `demos/demos.py` produces the demonstrations listed in `demos/takes.json`.

## Limits

One set of English prose documents from one handbook, up to 1,000 files; one answering model in one harness, Claude
Code, which is built for agent search; baseline RAG without tuning; one answer per question per setup; AI graders, no
person. Results for code, other document types or much larger sets may differ.
