"""Chunk the large set and embed every chunk locally on CPU. Smaller sets use the subset of these vectors from their own files.

Usage: .venv/Scripts/python bench/index.py internal/index
"""
import json, pathlib, sys, time
import numpy as np
from fastembed import TextEmbedding

CFG = json.load(open(pathlib.Path(__file__).with_name("config.json"), encoding="utf-8"))
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
size, step = CFG["chunk_words"], CFG["chunk_words"] - CFG["chunk_overlap"]
chunks = []
for f in sorted(pathlib.Path(CFG["sets_dir"], "large").iterdir()):
    w = f.read_text(encoding="utf-8").split()
    for i in range(0, max(len(w) - CFG["chunk_overlap"], 1), step):
        chunks.append({"file": f.name, "text": " ".join(w[i:i + size])})
t0 = time.time()
model = TextEmbedding(CFG["embedding_model"])
vec = np.array(list(model.embed([c["text"] for c in chunks], batch_size=32)), dtype=np.float32)
vec /= np.linalg.norm(vec, axis=1, keepdims=True)
np.save(out / "vectors.npy", vec)
(out / "chunks.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in chunks), encoding="utf-8")
json.dump({"chunks": len(chunks), "dim": vec.shape[1], "seconds": round(time.time() - t0, 1)}, open(out / "index.json", "w"))
print(len(chunks), vec.shape, round(time.time() - t0, 1), "s")
