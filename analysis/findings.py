"""Build findings.json from the scored runs and the search timings. Standard library only.

Usage: python analysis/findings.py   (from anywhere)
Inputs: results/2026-11-02_x86-laptop_main/raw.jsonl, scoring/scores.json, results/2026-11-01_x86-laptop_dry/raw.jsonl
(paste at 1,000 files: its only record), results/2026-11-05_x86-laptop_search/search.json, bench/questions.json, the sets folder.
"""
import hashlib, json, pathlib, statistics as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAIN = ROOT / "results/2026-11-02_x86-laptop_main"
DRY = ROOT / "results/2026-11-01_x86-laptop_dry"
SEARCH = ROOT / "results/2026-11-05_x86-laptop_search/search.json"
CFG = json.load(open(ROOT / "bench/config.json", encoding="utf-8"))
SETS = {"small": 10, "medium": 100, "large": 1000}
METHODS = ["paste", "agent", "rag"]
REPEAT_QS = ("L4", "L8", "P3", "P8")


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def tokens_in(r):
    u = r.get("usage") or {}
    return sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 3) if xs else None


def tally(rows):
    out = {"correct": 0, "wrong": 0, "not_found": 0, "n": len(rows)}
    for r in rows:
        out[r["final"]] += 1
    return out


raw = jl(MAIN / "raw.jsonl")
dry = jl(DRY / "raw.jsonl")
scores = json.load(open(ROOT / "scoring/scores.json", encoding="utf-8"))
rawkey = {(r["method"], r["set"], r["q"], r["rep"]): r for r in raw}
nofit = [r for r in dry if r.get("does_not_fit")]

f = {"study": "009-do-you-need-rag", "machine": "x86-laptop", "model": CFG["model"], "claude_code": CFG["claude_version"],
     "questions_sha256": hashlib.sha256((ROOT / "bench/questions.json").read_bytes()).hexdigest(),
     "sources": {"answers": "results/2026-11-02_x86-laptop_main/raw.jsonl", "paste_large": "results/2026-11-01_x86-laptop_dry/raw.jsonl",
                 "grades": "scoring/scores.json", "search": "results/2026-11-05_x86-laptop_search/search.json"},
     "run_dates": [min(r["ts"] for r in raw)[:10], max(r["ts"] for r in raw)[:10]],
     "config": {k: CFG[k] for k in ("embedding_model", "chunk_words", "chunk_overlap", "top_k", "agent_tools", "agent_max_turns", "paste_max_est_tokens")}}

# corpus sizes
sets = {}
for s in SETS:
    files = sorted((pathlib.Path(CFG["sets_dir"]) / s).iterdir())
    texts = [p.read_text(encoding="utf-8") for p in files]
    sets[s] = {"files": len(files), "words": sum(len(t.split()) for t in texts), "est_tokens_chars_div_4": sum(len(t) for t in texts) // 4}
f["sets"] = sets

# scores, main run only (rep 0)
main = [x for x in scores if x["rep"] == 0]
sc = {}
for m in METHODS:
    sc[m] = {}
    for s in SETS:
        rows = [x for x in main if x["method"] == m and x["set"] == s]
        if not rows:
            sc[m][s] = {"does_not_fit": True}
            continue
        sc[m][s] = {g: tally([x for x in rows if x["group"] == g]) for g in ("literal", "paraphrased")}
        sc[m][s]["all"] = tally(rows)
        sc[m][s]["all_without_P4"] = tally([x for x in rows if x["q"] != "P4"])
    ran = [x for x in main if x["method"] == m]
    sc[m]["total"] = tally(ran)
    sc[m]["total_literal"] = tally([x for x in ran if x["group"] == "literal"])
    sc[m]["total_paraphrased"] = tally([x for x in ran if x["group"] == "paraphrased"])
    sc[m]["total_without_P4"] = tally([x for x in ran if x["q"] != "P4"])
f["scores_main"] = sc
f["misses_main"] = sorted([x["q"], x["method"], x["set"], x["final"]] for x in main if x["final"] != "correct")

# repeats at 100 files: rep 0 from the main run plus reps 1-4
rep = {}
for m in ("agent", "rag"):
    rows = [x for x in scores if x["method"] == m and x["set"] == "medium" and x["q"] in REPEAT_QS]
    rep[m] = {"all": tally(rows), "by_question": {q: tally([x for x in rows if x["q"] == q]) for q in REPEAT_QS}}
f["repeats_100_files"] = rep

# script vs final grade
f["grading"] = {"items": len(scores), "hand_graded": sum(1 for x in scores if x["hand"]),
                "hand_changed": sum(1 for x in scores if x["hand"] and x["hand"] != x["grader"]),
                "grader_counts": {g: sum(1 for x in scores if x["grader"] == g) for g in ("correct", "wrong", "not_found")},
                "final_counts": {g: sum(1 for x in scores if x["final"] == g) for g in ("correct", "wrong", "not_found")},
                "script_match_but_final_not_correct": sorted([x["item"], x["method"], x["set"], x["q"], x["rep"]] for x in scores if x["script_match"] and x["final"] != "correct"),
                "script_miss_but_final_correct": sum(1 for x in scores if not x["script_match"] and x["final"] == "correct")}

# cost and time per answer, main run
cost = {}
for m in METHODS:
    cost[m] = {}
    for s in SETS:
        rows = [r for r in raw if r["method"] == m and r["set"] == s and r["rep"] == 0]
        if not rows:
            r = next(x for x in nofit if x["method"] == m and x["set"] == s)
            cost[m][s] = {"does_not_fit": True, "est_tokens_chars_div_4": r["est_tokens"], "limit_est_tokens": CFG["paste_max_est_tokens"]}
            continue
        c = {"median_input_tokens": med([tokens_in(r) for r in rows]), "max_input_tokens": max(tokens_in(r) for r in rows),
             "median_output_tokens": med([(r.get("usage") or {}).get("output_tokens") for r in rows]),
             "median_seconds": med([r["seconds"] for r in rows]), "max_seconds": max(r["seconds"] for r in rows)}
        if m == "agent":
            c.update(median_tool_calls=med([r["tool_calls"] for r in rows]), max_tool_calls=max(r["tool_calls"] for r in rows),
                     median_turns=med([r["turns"] for r in rows]))
        if m == "paste":
            c["real_over_est_tokens"] = med([tokens_in(r) / r["est_tokens"] for r in rows])
        if m == "rag":
            c.update(median_search_ms_numpy=med([r["search_ms"] for r in rows]), source_file_retrieved=sum(1 for r in rows if r["source_found"]))
        cost[m][s] = c
f["cost_main"] = cost

# where RAG missed: was the source file among the 20 chunks? [question, set, grade, source file retrieved]
f["rag_misses_source_retrieved"] = sorted([x["q"], x["set"], x["final"], rawkey[(x["method"], x["set"], x["q"], x["rep"])]["source_found"]]
                                          for x in main if x["method"] == "rag" and x["final"] != "correct")

# passage level (from analysis/rag_passages.py): was the chunk holding the answer sentence in the top 20, and RAG's grade
psg = json.load(open(MAIN / "rag_passages.json", encoding="utf-8"))
grade = {(x["set"], x["q"]): x["final"] for x in main if x["method"] == "rag"}
both = [(p, grade[(p["set"], p["q"])]) for p in psg]
f["rag_passage"] = {
    "retrieval_matches_logged_files": sum(p["matches_log"] for p in psg), "of": len(psg),
    "passage_in_top_k_and_correct": sum(1 for p, g in both if p["in_top_k"] and g == "correct"),
    "passage_in_top_k_and_not_correct": sum(1 for p, g in both if p["in_top_k"] and g != "correct"),
    "passage_missing_and_correct": sum(1 for p, g in both if not p["in_top_k"] and g == "correct"),
    "passage_missing_and_not_correct": sum(1 for p, g in both if not p["in_top_k"] and g != "correct"),
    "passage_in_top_k_by_set": {s: {g: sum(1 for p in psg if p["set"] == s and p["group"] == g and p["in_top_k"]) for g in ("literal", "paraphrased")} for s in SETS},
    "best_rank_when_missing": {"%s_%s" % (p["q"], p["set"]): p["best_rank"] for p in psg if not p["in_top_k"]},
    "best_rank_by_set": {q: {s: next(p["best_rank"] for p in psg if p["q"] == q and p["set"] == s) for s in SETS} for q in ("P5", "P8", "P10", "L3", "P4")}}

# quota, approximate: rise of the shared five-hour and seven-day meters between consecutive answers of one setup (meter steps are 1%)
quota = {}
for m in METHODS:
    for s in SETS:
        rows = sorted((r for r in raw if r["method"] == m and r["set"] == s), key=lambda r: r["ts"])
        d5 = [b["five_hour"] - a["five_hour"] for a, b in zip(rows, rows[1:]) if a["five_hour"] is not None and b["five_hour"] is not None and b["five_hour"] >= a["five_hour"]]
        if d5:
            quota["%s_%s" % (m, s)] = {"median_five_hour_rise_per_answer": med(d5), "answer_pairs": len(d5)}
f["quota_approx"] = quota
f["quota_note"] = ("Meter steps are 1%, so 0 means under 1% per answer. The meter is shared with every other use of the account, "
                   "and blocks that cross a five-hour reset are skipped (negative steps). Seven-day rises cross weekly resets and are not given.")

# internal calls Claude Code made to other models (not in the answering model's usage above)
inner = {}
for r in raw:
    sp = MAIN / "streams" / ("%s_%s_%s_%s.jsonl" % (r["method"], r["set"], r["q"], r["rep"]))
    res = [json.loads(l) for l in open(sp, encoding="utf-8") if '"type":"result"' in l]
    for m, u in ((res[-1].get("modelUsage") or {}) if res else {}).items():
        if m != CFG["model"]:
            inner.setdefault(m, {}).setdefault(r["method"], []).append(
                (u.get("inputTokens", 0) + u.get("cacheReadInputTokens", 0) + u.get("cacheCreationInputTokens", 0), u.get("outputTokens", 0)))
f["internal_model_calls"] = {m: {k: {"sessions": len(v), "of": sum(1 for r in raw if r["method"] == k),
                                     "median_input_tokens": med([x[0] for x in v]), "max_input_tokens": max(x[0] for x in v),
                                     "median_output_tokens": med([x[1] for x in v])} for k, v in by.items()} for m, by in inner.items()}

# vector search timings
srch = json.load(open(SEARCH, encoding="utf-8"))
vs = {}
for e in ("numpy", "sqlite-vec", "qdrant"):
    vs[e] = {}
    for s in SETS:
        rows = [r for r in srch if r["engine"] == e and r["set"] == s]
        v = {"chunks": rows[0]["chunks"], "runs": len(rows), "median_of_run_medians_ms": med([r["median_ms"] for r in rows]),
             "max_ms": max(r["max_ms"] for r in rows), "min_overlap_with_exact": min(r["overlap"] for r in rows)}
        if e == "qdrant":
            v.update(server_median_ms=med([r["server_median_ms"] for r in rows]), indexed_vectors=rows[0].get("indexed_vectors"))
        if "build_ms" in rows[0]:
            v["build_ms"] = rows[0]["build_ms"]
        vs[e][s] = v
f["vector_search"] = vs

# demos (demos/demos.py; takes in demos/takes.json)
D = ROOT / "demos/out"
d2 = json.load(open(D / "D2_size.json", encoding="utf-8"))
f["demos"] = {
    "D1": {k: json.load(open(D / "D1_no_documents.json", encoding="utf-8"))[k] for k in ("question_id", "question", "answer", "expected_from_handbook")},
    "D2_size_check": {"command_powershell": d2["command_powershell"],
                      "rows": [dict(set=r["set"], printed=int(r["powershell_prints"]), real=r["real_paste_tokens"],
                                    over_real_pct=round((int(r["powershell_prints"]) / r["real_paste_tokens"] - 1) * 100, 1) if r["real_paste_tokens"] else None) for r in d2["rows"]]},
    "D5_pairs": json.load(open(D / "D5_embed.json", encoding="utf-8"))["pairs"],
    "D6_P5_large": {k: json.load(open(D / "D6_rag_miss_P5_large.json", encoding="utf-8"))[k] for k in ("answer_chunk", "twentieth_score", "top_5")},
    "D7_one_search": json.load(open(D / "D7_vector.json", encoding="utf-8"))["engines"]}

(ROOT / "findings.json").write_text(json.dumps(f, indent=1), encoding="utf-8")
print(json.dumps(f, indent=1))
