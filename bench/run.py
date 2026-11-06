"""Answer the frozen questions with each method and log everything. One fresh Claude Code session per answer.

Usage: CLAUDE_BIN=... CLAUDE_CONFIG_DIR=C:/... .venv/Scripts/python bench/run.py <results dir> --plan dry|main|repeats [--stop-at 0.8]
Resumes: answers already in raw.jsonl are skipped.
"""
import argparse, hashlib, json, os, pathlib, re, subprocess, sys, time
import numpy as np
from fastembed import TextEmbedding

HERE = pathlib.Path(__file__).parent
CFG = json.load(open(HERE / "config.json", encoding="utf-8"))
QS = json.load(open(HERE / "questions.json", encoding="utf-8"))
SETS = ["small", "medium", "large"]
METHODS = ["paste", "agent", "rag"]
INDEX = HERE.parent / "internal" / "index"


def plan(name):
    if name == "dry":                      # one question through every setup
        return [(m, s, "L4", 0) for s in SETS for m in METHODS]
    if name == "main":
        return [(m, s, q["id"], 0) for s in SETS for m in METHODS for q in QS]
    if name == "repeats":
        return [(m, "medium", q, r) for m in METHODS for q in ("L4", "L8", "P3", "P8") for r in range(1, 5)]
    sys.exit("unknown plan")


def scrub(text):
    home = os.path.expanduser("~")
    for p in sorted({home, home.replace("\\", "/"), os.path.basename(home)}, key=len, reverse=True):
        text = re.sub(re.escape(p), "<scrubbed>", text, flags=re.I)
    return text


def set_dir(s):
    return pathlib.Path(CFG["sets_dir"]) / s


def paste_prompt(s, q):
    parts = []
    for f in sorted(set_dir(s).iterdir()):
        parts.append('<document name="%s">\n%s\n</document>' % (f.name, f.read_text(encoding="utf-8")))
    return "%s\n\n%s\n\nQuestion: %s" % (CFG["instruction"], "\n\n".join(parts), q)


class Rag:
    def __init__(self):
        self.vec = np.load(INDEX / "vectors.npy")
        self.chunks = [json.loads(l) for l in open(INDEX / "chunks.jsonl", encoding="utf-8")]
        self.model = TextEmbedding(CFG["embedding_model"])

    def prompt(self, s, q):
        names = {f.name for f in set_dir(s).iterdir()}
        keep = np.array([i for i, c in enumerate(self.chunks) if c["file"] in names])
        qv = np.array(list(self.model.query_embed([q]))[0], dtype=np.float32)
        t0 = time.perf_counter()
        order = keep[np.argsort(-(self.vec[keep] @ (qv / np.linalg.norm(qv))))[:CFG["top_k"]]]
        ms = (time.perf_counter() - t0) * 1000
        parts = ['<excerpt from="%s">\n%s\n</excerpt>' % (self.chunks[i]["file"], self.chunks[i]["text"]) for i in order]
        return "%s\n\n%s\n\nQuestion: %s" % (CFG["instruction"], "\n\n".join(parts), q), [self.chunks[i]["file"] for i in order], round(ms, 2)


def call(env, cwd, tools, prompt, stream_path):
    args = [os.environ["CLAUDE_BIN"], "-p", "--output-format", "stream-json", "--verbose", "--model", CFG["model"], "--strict-mcp-config",
            "--no-session-persistence", "--disable-slash-commands", "--setting-sources", "", "--tools", tools,
            "--max-turns", str(CFG["agent_max_turns"] if tools else 1)]
    if tools:
        args += ["--allowedTools", tools]
    t0 = time.time()
    cp = subprocess.run(args, cwd=cwd, env=env, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    o = dict(answer=None, usage=None, subtype=None, turns=None, tool_calls=0, tools_used=[], five_hour=None, seven_day=None, rc=cp.returncode,
             seconds=round(time.time() - t0, 1), stderr=scrub(cp.stderr)[:300])
    lines = []
    for l in cp.stdout.splitlines():
        if not l.startswith("{"):
            continue
        lines.append(scrub(l))
        e = json.loads(l)
        if e.get("type") == "rate_limit_event":
            w = e.get("rate_limit_info", {}).get("unifiedWindows", {})
            o["five_hour"], o["seven_day"] = w.get("five_hour", {}).get("utilization"), w.get("seven_day", {}).get("utilization")
        elif e.get("type") == "assistant":
            for b in e.get("message", {}).get("content", []):
                if b.get("type") == "tool_use":
                    o["tool_calls"] += 1
                    o["tools_used"].append(b.get("name"))
        elif e.get("type") == "result":
            o["answer"], o["usage"], o["subtype"], o["turns"], o["is_error"] = scrub(e.get("result") or ""), e.get("usage"), e.get("subtype"), e.get("num_turns"), e.get("is_error")
    stream_path.parent.mkdir(parents=True, exist_ok=True)
    stream_path.write_text("\n".join(lines), encoding="utf-8")
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--plan", required=True); ap.add_argument("--stop-at", type=float, default=0.8)
    ap.add_argument("--stop-7d", type=float, default=0.8); ap.add_argument("--methods", default=",".join(METHODS)); ap.add_argument("--sets", default=",".join(SETS))
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    raw = out / "raw.jsonl"
    done = {(r["method"], r["set"], r["q"], r["rep"]) for r in map(json.loads, open(raw, encoding="utf-8"))} if raw.exists() else set()
    env = {k: v for k, v in os.environ.items() if not (k.upper().startswith(("ANTHROPIC_", "CLAUDE_CODE_")) or k.upper() == "CLAUDECODE")}
    qmap = {q["id"]: q for q in QS}
    rag = Rag()
    sha = hashlib.sha256((HERE / "questions.json").read_bytes()).hexdigest()
    neutral = str(set_dir("small").parent)
    for m, s, q, rep in plan(a.plan):
        if (m, s, q, rep) in done or m not in a.methods.split(",") or s not in a.sets.split(","):
            continue
        text = qmap[q]["question"]
        rec = dict(method=m, set=s, q=q, rep=rep, group=qmap[q]["group"], questions_sha=sha, ts=time.strftime("%Y-%m-%dT%H:%M:%S"), model=CFG["model"], claude=CFG["claude_version"])
        stream = out / "streams" / ("%s_%s_%s_%s.jsonl" % (m, s, q, rep))
        if m == "paste":
            p = paste_prompt(s, text)
            rec["est_tokens"] = len(p) // 4
            if rec["est_tokens"] > CFG["paste_max_est_tokens"]:
                rec.update(does_not_fit=True, answer=None)
            else:
                rec.update(call(env, neutral, "", p, stream))
        elif m == "agent":
            rec.update(call(env, str(set_dir(s)), CFG["agent_tools"], "%s The documents are the files in this folder.\n\nQuestion: %s" % (CFG["instruction"], text), stream))
        else:
            p, files, ms = rag.prompt(s, text)
            rec.update(retrieved=files, source_found=qmap[q]["source"] in files, search_ms=ms, est_tokens=len(p) // 4)
            rec.update(call(env, neutral, "", p, stream))
        if rec.get("rc") or rec.get("is_error"):  # a failed call (login, limit) is not an answer: stop, and keep it out of the data
            print("stopping: claude failed:", rec.get("answer"), rec.get("stderr"))
            return
        rec["key_match"] = bool(rec.get("answer") and re.search(qmap[q]["key_regex"], rec["answer"], re.I))
        with open(raw, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        u = rec.get("usage") or {}
        print(m, s, q, rep, "NOFIT" if rec.get("does_not_fit") else "ran", rec.get("seconds"), "in", u.get("input_tokens"), "cc", u.get("cache_creation_input_tokens"),
              "cr", u.get("cache_read_input_tokens"), "tools", rec.get("tool_calls"), "5h", rec.get("five_hour"), "7d", rec.get("seven_day"), "match", rec["key_match"], flush=True)
        if rec.get("five_hour") is not None and rec["five_hour"] >= a.stop_at:
            print("stopping: five-hour meter at", rec["five_hour"])
            return
        if rec.get("seven_day") is not None and rec["seven_day"] >= a.stop_7d:
            print("stopping: seven-day meter at", rec["seven_day"])
            return


if __name__ == "__main__":
    main()
