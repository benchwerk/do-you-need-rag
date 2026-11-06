"""For every question and set: did baseline RAG's top 20 chunks contain the sentence that answers it, and at what rank?
Recomputes the retrieval exactly as bench/run.py does and checks it matches the files logged in raw.jsonl. No model quota.

Usage: .venv/Scripts/python analysis/rag_passages.py
Output: results/2026-11-02_x86-laptop_main/rag_passages.json
"""
import json, pathlib, re, sys
import numpy as np
from fastembed import TextEmbedding

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bench"))
CFG = json.load(open(ROOT / "bench/config.json", encoding="utf-8"))
QS = json.load(open(ROOT / "bench/questions.json", encoding="utf-8"))
MAIN = ROOT / "results/2026-11-02_x86-laptop_main"
INDEX = ROOT / "internal/index"


def norm(t):
    t = re.sub(r"[*_`#>\[\]]", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


vec = np.load(INDEX / "vectors.npy")
chunks = [json.loads(l) for l in open(INDEX / "chunks.jsonl", encoding="utf-8")]
ntext = [norm(c["text"]) for c in chunks]
model = TextEmbedding(CFG["embedding_model"])
logged = {(r["set"], r["q"]): r["retrieved"] for r in map(json.loads, open(MAIN / "raw.jsonl", encoding="utf-8")) if r["method"] == "rag" and r["rep"] == 0}

out = []
for s in ("small", "medium", "large"):
    names = {f.name for f in (pathlib.Path(CFG["sets_dir"]) / s).iterdir()}
    keep = np.array([i for i, c in enumerate(chunks) if c["file"] in names])
    for q in QS:
        qv = np.array(list(model.query_embed([q["question"]]))[0], dtype=np.float32)
        scores = vec[keep] @ (qv / np.linalg.norm(qv))
        order = keep[np.argsort(-scores)]
        top = order[:CFG["top_k"]]
        quote = norm(q["quote"])
        probe = " ".join(quote.split()[:8])
        answer = [i for i in keep if quote in ntext[i]] or [i for i in keep if probe in ntext[i]]
        ranks = sorted(int(np.where(order == i)[0][0]) + 1 for i in answer)
        out.append(dict(set=s, q=q["id"], group=q["group"], answer_chunks=len(answer), best_rank=ranks[0] if ranks else None,
                        in_top_k=bool(ranks and ranks[0] <= CFG["top_k"]), matches_log=[chunks[i]["file"] for i in top] == logged[(s, q["id"])]))
        print(out[-1], flush=True)

(MAIN / "rag_passages.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
