"""Short demonstrations built from the study's data. Each writes demos/out/<id>.json (and D1 a transcript).

Usage (from the study folder):
  .venv/Scripts/python demos/demos.py size        D2: a quick size check, tested against measured tokens
  .venv/Scripts/python demos/demos.py embed       D5: real similarities and a 2-D map of the 10-file set
  .venv/Scripts/python demos/demos.py rag-miss    D6: what RAG put in the prompt for P5 instead of the answer
  .venv/Scripts/python demos/demos.py vector [--qdrant URL]   D7: one search with and without a vector database
  CLAUDE_BIN=... CLAUDE_CONFIG_DIR=C:/... .venv/Scripts/python demos/demos.py d1   D1: a wiki question with no documents
D3, D4 and D6 replay main-run transcripts (demos/takes.json); no new runs.
"""
import json, os, pathlib, re, statistics, subprocess, sys, time
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bench"))
CFG = json.load(open(ROOT / "bench/config.json", encoding="utf-8"))
QS = {q["id"]: q for q in json.load(open(ROOT / "bench/questions.json", encoding="utf-8"))}
OUT = ROOT / "demos/out"
INDEX = ROOT / "internal/index"
SETS = pathlib.Path(CFG["sets_dir"])


def save(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(obj, indent=1, ensure_ascii=False)[:3000])


def scrub(text):
    home = os.path.expanduser("~")
    for p in sorted({home, home.replace("\\", "/"), home.replace("\\", "\\\\"), os.path.basename(home)}, key=len, reverse=True):
        text = re.sub(re.escape(p), "<home>", text, flags=re.I)
    return text


def load_index():
    vec = np.load(INDEX / "vectors.npy")
    chunks = [json.loads(l) for l in open(INDEX / "chunks.jsonl", encoding="utf-8")]
    return vec, chunks


def size():
    """A quick size check: characters / 4, times 1.4. Real tokens come from the main run's paste answers."""
    raw = [json.loads(l) for l in open(ROOT / "results/2026-11-02_x86-laptop_main/raw.jsonl", encoding="utf-8")]
    real = {}
    for s in ("small", "medium"):
        u = [r["usage"] for r in raw if r["method"] == "paste" and r["set"] == s and r["rep"] == 0]
        real[s] = statistics.median(sum(x.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) for x in u)
    rows = []
    for s in ("small", "medium", "large"):
        files = sorted((SETS / s).iterdir())
        chars = sum(len(p.read_text(encoding="utf-8")) for p in files)
        # what the PowerShell and bash commands below print, run in that folder
        ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                             "[int]((Get-ChildItem -File -Recurse | Get-Content -Raw -Encoding UTF8 | Measure-Object -Character).Characters / 4 * 1.4)"],
                            cwd=SETS / s, capture_output=True, text=True).stdout.strip()
        rows.append(dict(set=s, files=len(files), characters=chars, estimate_x1_4=round(chars / 4 * 1.4), powershell_prints=ps,
                         real_paste_tokens=real.get(s), note=None if s in real else "too large to paste; not run"))
    save("D2_size.json", {"command_powershell": "[int]((Get-ChildItem -File -Recurse | Get-Content -Raw -Encoding UTF8 | Measure-Object -Character).Characters / 4 * 1.4)",
                          "command_bash": "echo $(( $(cat $(find . -type f) | wc -m) * 14 / 40 ))",
                          "real_tokens_include": "the instruction, document tags and the question (median of 20 paste answers)", "rows": rows})


def embed():
    from fastembed import TextEmbedding
    m = TextEmbedding(CFG["embedding_model"])
    pairs = [("a call that got taped", "the meeting recording"), ("a call that got taped", "the expense report"),
             ("too many of us are already away", "PTO capacity has been reached"), ("too many of us are already away", "the renewal date"),
             ("the secret used to log in", "credentials such as passwords"), ("the secret used to log in", "meeting invites")]
    texts = sorted({t for p in pairs for t in p})
    v = {t: e / np.linalg.norm(e) for t, e in zip(texts, m.embed(texts))}
    sims = [dict(a=a, b=b, cosine=round(float(v[a] @ v[b]), 3)) for a, b in pairs]
    vec, chunks = load_index()
    names = {f.name for f in (SETS / "small").iterdir()}
    keep = [i for i, c in enumerate(chunks) if c["file"] in names]
    qv = [e / np.linalg.norm(e) for e in m.query_embed([QS[q]["question"] for q in QS])]
    X = np.vstack([vec[keep], np.array(qv)])
    X = X - X.mean(0)
    _, _, vt = np.linalg.svd(X, full_matrices=False)
    xy = X @ vt[:2].T
    pts = [dict(kind="chunk", file=chunks[i]["file"], x=round(float(xy[n, 0]), 4), y=round(float(xy[n, 1]), 4)) for n, i in enumerate(keep)]
    pts += [dict(kind="question", q=q, x=round(float(xy[len(keep) + n, 0]), 4), y=round(float(xy[len(keep) + n, 1]), 4)) for n, q in enumerate(QS)]
    save("D5_embed.json", {"model": CFG["embedding_model"], "pairs": pairs and sims, "map_2d": {"method": "PCA of chunk and question vectors, 10-file set", "points": pts}})


def rag_miss(q="P5", s="large"):
    from fastembed import TextEmbedding
    from run import Rag
    rag = Rag()
    prompt, files, ms = rag.prompt(s, QS[q]["question"])
    vec, chunks = rag.vec, rag.chunks
    names = {f.name for f in (SETS / s).iterdir()}
    keep = np.array([i for i, c in enumerate(chunks) if c["file"] in names])
    qv = np.array(list(rag.model.query_embed([QS[q]["question"]]))[0], dtype=np.float32)
    sc = vec[keep] @ (qv / np.linalg.norm(qv))
    order = np.argsort(-sc)
    quote = re.sub(r"\s+", " ", QS[q]["quote"]).lower()
    norm = lambda t: re.sub(r"\s+", " ", re.sub(r"[*_`#>\[\]]", "", t)).lower()
    rank = next(n + 1 for n, j in enumerate(order) if quote in norm(chunks[keep[j]]["text"]) or " ".join(quote.split()[:8]) in norm(chunks[keep[j]]["text"]))
    top = [dict(rank=n + 1, file=chunks[keep[j]]["file"], score=round(float(sc[j]), 3), start=chunks[keep[j]]["text"][:160]) for n, j in enumerate(order[:5])]
    ans = keep[order[rank - 1]]
    save("D6_rag_miss_%s_%s.json" % (q, s), {"question": QS[q]["question"], "set": s, "top_k": CFG["top_k"], "top_5": top,
                                              "answer_chunk": dict(rank=rank, file=chunks[ans]["file"], score=round(float(sc[order[rank - 1]]), 3)),
                                              "twentieth_score": round(float(sc[order[CFG["top_k"] - 1]]), 3), "prompt_est_tokens": len(prompt) // 4})


def vector(url):
    import sqlite3, sqlite_vec, tempfile, httpx
    from fastembed import TextEmbedding
    vec, chunks = load_index()
    q = QS["L4"]["question"]
    qv = np.array(list(TextEmbedding(CFG["embedding_model"]).query_embed([q]))[0], dtype=np.float32)
    qv /= np.linalg.norm(qv)
    res = {}
    t0 = time.perf_counter(); top = np.argsort(-(vec @ qv))[:5]; res["numpy"] = dict(ms=round((time.perf_counter() - t0) * 1000, 3), top5=[int(i) for i in top])
    tmp = tempfile.mkdtemp(); db = sqlite3.connect(os.path.join(tmp, "v.db"))
    db.enable_load_extension(True); sqlite_vec.load(db)
    db.execute("create virtual table v using vec0(embedding float[%d] distance_metric=cosine)" % vec.shape[1])
    db.executemany("insert into v(rowid, embedding) values (?, ?)", ((i, x.tobytes()) for i, x in enumerate(vec))); db.commit()
    t0 = time.perf_counter(); rows = db.execute("select rowid from v where embedding match ? and k = 5 order by distance", (qv.tobytes(),)).fetchall()
    res["sqlite-vec"] = dict(ms=round((time.perf_counter() - t0) * 1000, 3), top5=[r[0] for r in rows]); db.close()
    try:
        c = httpx.Client(base_url=url, timeout=60); name = "demo_large"
        c.delete("/collections/" + name); c.put("/collections/" + name, json={"vectors": {"size": vec.shape[1], "distance": "Cosine"}}).raise_for_status()
        for i in range(0, len(vec), 256):
            c.put("/collections/%s/points?wait=true" % name, json={"points": [{"id": j, "vector": vec[j].tolist()} for j in range(i, min(i + 256, len(vec)))]}).raise_for_status()
        t0 = time.perf_counter(); j = c.post("/collections/%s/points/query" % name, json={"query": qv.tolist(), "limit": 5}).json()
        res["qdrant"] = dict(round_trip_ms=round((time.perf_counter() - t0) * 1000, 3), server_ms=round(j["time"] * 1000, 3), top5=[p["id"] for p in j["result"]["points"]])
        c.delete("/collections/" + name)
    except Exception as e:
        res["qdrant"] = dict(error=type(e).__name__)
    save("D7_vector.json", {"question": q, "chunks": len(vec), "files": [chunks[i]["file"] for i in res["numpy"]["top5"]], "engines": res,
                            "note": "one search, for the screen; the measured timings are in results/2026-11-05_x86-laptop_search"})


CHAT = "You are in a plain chat. You cannot open files or run anything; answer from what the user writes."  # as 007 D1


def d1():
    q = QS["L7"]["question"]
    env = {k: v for k, v in os.environ.items() if not (k.upper().startswith(("ANTHROPIC_", "CLAUDE_CODE_")) or k.upper() == "CLAUDECODE")}
    args = [os.environ["CLAUDE_BIN"], "-p", "--output-format", "stream-json", "--verbose", "--model", CFG["model"], "--strict-mcp-config",
            "--no-session-persistence", "--disable-slash-commands", "--setting-sources", "", "--tools", "", "--max-turns", "1",
            "--append-system-prompt", CHAT]
    empty = SETS.parent / "empty"  # take 1 ran in the sets folder: Claude saw it and wrote tool calls as text
    empty.mkdir(exist_ok=True)
    cp = subprocess.run(args, cwd=str(empty), env=env, input=q, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    t = OUT / "transcripts" / ("D1-no-documents_%s.jsonl" % stamp)
    t.parent.mkdir(parents=True, exist_ok=True)
    t.write_text(scrub(cp.stdout), encoding="utf-8")
    res = [json.loads(l) for l in cp.stdout.splitlines() if l.startswith("{") and json.loads(l).get("type") == "result"]
    save("D1_no_documents.json", {"question": q, "prompt": "the question alone, no documents, no tools, plain-chat note", "system_append": CHAT, "transcript": t.name, "rc": cp.returncode,
                                  "answer": scrub(res[0].get("result", "")) if res else None, "is_error": res[0].get("is_error") if res else None,
                                  "expected_from_handbook": QS["L7"]["answer"]})


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "vector":
        vector(sys.argv[3] if len(sys.argv) > 3 else "http://localhost:6333")
    else:
        {"size": size, "embed": embed, "rag-miss": rag_miss, "d1": d1}[cmd]()
