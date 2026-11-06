"""Search the same embeddings with NumPy, sqlite-vec and Qdrant: time per search and overlap with exact search. Uses no model quota.

Usage: .venv/Scripts/python bench/search_timing.py <results dir> [--qdrant http://localhost:6333]
Qdrant runs as its own server on default settings and is reached over HTTP, so round_trip_ms includes the network hop; server_ms is its own reported time.
"""
import argparse, json, os, pathlib, sqlite3, statistics, tempfile, time
import httpx, numpy as np, sqlite_vec
from fastembed import TextEmbedding

HERE = pathlib.Path(__file__).parent
CFG = json.load(open(HERE / "config.json", encoding="utf-8"))
QS = json.load(open(HERE / "questions.json", encoding="utf-8"))
SETS = ["small", "medium", "large"]
RUNS = 5
K = CFG["top_k"]
INDEX = HERE.parent / "internal" / "index"


def numpy_engine(vec):
    def search(q):
        t0 = time.perf_counter()
        top = np.argsort(-(vec @ q))[:K]
        return [int(i) for i in top], (time.perf_counter() - t0) * 1000, None
    return search, {}, lambda: None


def sqlite_engine(vec):
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "v.db")
    db = sqlite3.connect(path)
    db.enable_load_extension(True); sqlite_vec.load(db); db.enable_load_extension(False)
    t0 = time.perf_counter()
    db.execute("create virtual table v using vec0(embedding float[%d] distance_metric=cosine)" % vec.shape[1])
    db.executemany("insert into v(rowid, embedding) values (?, ?)", ((i, v.tobytes()) for i, v in enumerate(vec)))
    db.commit()
    build = (time.perf_counter() - t0) * 1000

    def search(q):
        t0 = time.perf_counter()
        rows = db.execute("select rowid from v where embedding match ? and k = ? order by distance", (q.tobytes(), K)).fetchall()
        return [r[0] for r in rows], (time.perf_counter() - t0) * 1000, None

    def close():
        db.close()
        os.remove(path); os.rmdir(tmp)
    return search, {"build_ms": round(build, 1), "file_bytes": os.path.getsize(path)}, close


def qdrant_engine(vec, url, name):
    c = httpx.Client(base_url=url, timeout=120)
    c.delete("/collections/" + name)
    t0 = time.perf_counter()
    c.put("/collections/" + name, json={"vectors": {"size": vec.shape[1], "distance": "Cosine"}}).raise_for_status()
    for i in range(0, len(vec), 256):
        pts = [{"id": j, "vector": vec[j].tolist()} for j in range(i, min(i + 256, len(vec)))]
        c.put("/collections/%s/points?wait=true" % name, json={"points": pts}).raise_for_status()
    while True:
        info = c.get("/collections/" + name).json()["result"]
        if info["status"] == "green":
            break
        time.sleep(0.2)
    build = (time.perf_counter() - t0) * 1000

    def search(q):
        body = {"query": q.tolist(), "limit": K}
        t0 = time.perf_counter()
        r = c.post("/collections/%s/points/query" % name, json=body)
        ms = (time.perf_counter() - t0) * 1000
        r.raise_for_status()
        j = r.json()
        return [p["id"] for p in j["result"]["points"]], ms, j["time"] * 1000

    def close():
        c.delete("/collections/" + name)
        c.close()
    return search, {"build_ms": round(build, 1), "indexed_vectors": info.get("indexed_vectors_count"), "points": info.get("points_count")}, close


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--qdrant", default="http://localhost:6333")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    vec = np.load(INDEX / "vectors.npy")
    chunks = [json.loads(l) for l in open(INDEX / "chunks.jsonl", encoding="utf-8")]
    model = TextEmbedding(CFG["embedding_model"])
    qv = [np.array(v, dtype=np.float32) for v in model.query_embed([q["question"] for q in QS])]
    qv = [v / np.linalg.norm(v) for v in qv]
    rows = []
    for s in SETS:
        names = {f.name for f in (pathlib.Path(CFG["sets_dir"]) / s).iterdir()}
        keep = np.array([i for i, c in enumerate(chunks) if c["file"] in names])
        sub = vec[keep]
        exact = [np.argsort(-(sub @ q))[:K].tolist() for q in qv]
        engines = {"numpy": lambda: numpy_engine(sub), "sqlite-vec": lambda: sqlite_engine(sub), "qdrant": lambda: qdrant_engine(sub, a.qdrant, "bench_" + s)}
        for name, make in engines.items():
            search, meta, close = make()
            for run in range(RUNS):
                ms, server, overlap = [], [], []
                for q, ex in zip(qv, exact):
                    ids, t, srv = search(q)
                    ms.append(t)
                    if srv is not None:
                        server.append(srv)
                    overlap.append(len(set(ids) & set(ex)) / K)
                row = dict(engine=name, set=s, run=run, chunks=len(sub), median_ms=round(statistics.median(ms), 3), max_ms=round(max(ms), 3),
                           server_median_ms=round(statistics.median(server), 3) if server else None, overlap=round(statistics.mean(overlap), 4), **meta)
                rows.append(row)
                print(name, s, run, row["median_ms"], row["server_median_ms"], row["overlap"], meta, flush=True)
            close()
    (out / "search.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
