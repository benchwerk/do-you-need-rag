"""Extract the handbook's markdown pages from the pinned archive into internal/corpus/all/. Reads text only; runs nothing from it.

Left out: sections about individual people and employment, because they name real people.
Usage: python -I bench/extract_handbook.py internal/corpus/dl/handbook.tar.gz internal/corpus/all
"""
import pathlib, re, sys, tarfile

EXCLUDE = {"people-group", "people-policies", "total-rewards", "hiring", "leadership", "ceo", "eba", "eta", "board-meetings",
           "job-description-library", "labor-and-employment-notices", "entity", "acquisitions", "upstream-studios"}
MIN_WORDS = 150

archive, out = sys.argv[1], pathlib.Path(sys.argv[2])
kept = 0
with tarfile.open(archive) as t:
    for m in t:
        if not m.isfile() or not m.name.endswith(".md"):
            continue
        p = m.name.split("/", 1)[1]
        if not p.startswith("content/handbook/"):
            continue
        rel = p[len("content/handbook/"):]
        if rel.split("/")[0] in EXCLUDE:
            continue
        text = t.extractfile(m).read().decode("utf-8", "replace")
        body = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)                 # front matter
        title = re.search(r'^title:\s*"?(.*?)"?\s*$', text, flags=re.M)
        if len(body.split()) < MIN_WORDS:
            continue
        name = rel.replace("/", "__")
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text((f"# {title.group(1)}\n\n" if title else "") + body, encoding="utf-8")
        kept += 1
print(kept, "pages")
