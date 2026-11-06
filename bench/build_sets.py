"""Build the nested document sets: small (10) is chosen by hand, medium and large add pages in a fixed hashed order.

Usage: python -I bench/build_sets.py internal/corpus/all internal/corpus/sets
"""
import hashlib, json, pathlib, shutil, sys

SMALL = ["finance__expenses.md", "finance__procurement___index.md", "security__policies_and_standards__password-standard.md",
         "security__policies_and_standards__data-classification-standard.md", "support__on-call.md",
         "support__support-time-off.md", "support__workflows__sla_and_views.md", "communication___index.md",
         "company__culture__all-remote__meetings.md", "legal__anti-corruption-policy.md"]
SIZES = {"small": 10, "medium": 100, "large": 1000}
SEED = "009-do-you-need-rag"

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
rest = sorted((p.name for p in src.iterdir() if p.name not in SMALL),
              key=lambda n: hashlib.sha256((SEED + n).encode()).hexdigest())
order = SMALL + rest
report = {}
for name, n in SIZES.items():
    d = out / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    words = 0
    for f in order[:n]:
        short = f if len(f) <= 80 else f[:68] + "_" + hashlib.sha256(f.encode()).hexdigest()[:8] + ".md"   # Windows path limit
        shutil.copyfile(src / f, d / short)
        words += len((src / f).read_text(encoding="utf-8").split())
    report[name] = {"files": n, "words": words}
(out / "sets.json").write_text(json.dumps({"seed": SEED, "sets": report, "order": order[:1000]}, indent=1), encoding="utf-8")
print(report)
