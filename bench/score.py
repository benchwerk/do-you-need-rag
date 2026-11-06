"""Score the answers. Step 1 builds a blind sheet (method, size and file names hidden, order shuffled); graders return one
grade per item: correct, wrong (including anything invented) or not_found. Step 2 merges the grades.

Usage: python bench/score.py sheet <results dir> <scoring dir>
       python bench/score.py merge <results dir> <scoring dir>
Rules: an item is final when the grader and the script agree; every disagreement, every script miss and a 20% random
sample of the rest are graded again by hand (grades_hand.json). The hand grade wins.
"""
import json, pathlib, random, re, sys

HERE = pathlib.Path(__file__).parent
QS = {q["id"]: q for q in json.load(open(HERE / "questions.json", encoding="utf-8"))}
GRADES = ("correct", "wrong", "not_found")


def blind(text):
    text = re.sub(r"`[^`]*`", "[file]", text or "")
    return re.sub(r"[\w.-]+\.md\b", "[file]", text)


def load(res):
    return [json.loads(l) for l in open(pathlib.Path(res) / "raw.jsonl", encoding="utf-8")]


def sheet(res, out):
    out.mkdir(parents=True, exist_ok=True)
    rows = [r for r in load(res) if not r.get("does_not_fit")]
    random.Random(9).shuffle(rows)
    items, key = [], {}
    for n, r in enumerate(rows, 1):
        i = "A%03d" % n
        q = QS[r["q"]]
        items.append(dict(item=i, question=q["question"], expected=q["answer"], source_quote=q["quote"], answer=blind(r["answer"])))
        key[i] = dict(method=r["method"], set=r["set"], q=r["q"], rep=r["rep"])
    (out / "sheet.json").write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    print(len(items), "items")


def merge(res, out):
    rows = {(r["method"], r["set"], r["q"], r["rep"]): r for r in load(res)}
    key = json.load(open(out / "key.json", encoding="utf-8"))
    grader = json.load(open(out / "grades_agy.json", encoding="utf-8"))
    hand_path = out / "grades_hand.json"
    hand = json.load(open(hand_path, encoding="utf-8")) if hand_path.exists() else {}
    todo, scored = [], []
    rnd = random.Random(2026)
    for i, k in sorted(key.items()):
        r = rows[(k["method"], k["set"], k["q"], k["rep"])]
        g = grader.get(i)
        assert g in GRADES, (i, g)
        script = "correct" if r["key_match"] else None
        need = script is None or g != "correct" or rnd.random() < 0.2
        if need and i not in hand:
            todo.append(i)
        final = hand.get(i, g)
        scored.append(dict(k, item=i, group=r["group"], script_match=r["key_match"], grader=g, hand=hand.get(i), final=final))
    (out / "hand_todo.json").write_text(json.dumps(todo), encoding="utf-8")
    (out / "scores.json").write_text(json.dumps(scored, indent=1), encoding="utf-8")
    print(len(scored), "scored;", len(todo), "still need a hand grade")


if __name__ == "__main__":
    {"sheet": sheet, "merge": merge}[sys.argv[1]](sys.argv[2], pathlib.Path(sys.argv[3]))
