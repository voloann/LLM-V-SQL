"""Build a reproducible 100-question sample, proportional to (db, difficulty). usage: make_sample.py <root> <out.json>"""
import collections, json, math, random, sys

ROOT, OUT = sys.argv[1], sys.argv[2]
SIZE, SEED = 100, 42
data = json.load(open(f"{ROOT}/data/mini_dev_sqlite.json", encoding="utf-8"))
cells = collections.defaultdict(list)
for d in data:
    cells[(d["db_id"], d["difficulty"])].append(d)

quota = {k: len(v) * SIZE / len(data) for k, v in cells.items()}
take = {k: math.floor(q) for k, q in quota.items()}
for k in sorted(quota, key=lambda c: (-(quota[c] - take[c]), c))[: SIZE - sum(take.values())]:
    take[k] += 1

rng = random.Random(SEED)
sample = []
for k in sorted(cells):
    pool = sorted(cells[k], key=lambda d: d["question_id"])
    sample += rng.sample(pool, take[k])
sample.sort(key=lambda d: d["question_id"])
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(sample, fh, ensure_ascii=False, indent=1)

ids = {d["question_id"] for d in sample}
rows = [json.loads(l) for l in open(f"{ROOT}/outputs/rescored_physical/per_question.jsonl")]
sub = [r for r in rows if r["question_id"] in ids]
ex = lambda xs, k: round(sum(x[k] for x in xs) / len(xs) * 100, 1)
print("sample size", len(sample), "unique", len(ids))
print("by difficulty", dict(collections.Counter(d["difficulty"] for d in sample)))
print("by db", dict(sorted(collections.Counter(d["db_id"] for d in sample).items())))
print("coverage gap in sample", sum(r["coverage_gap"] for r in sub), "| full set 29.6%")
print("7B on sample : direct", ex(sub, "direct_ok"), "stage1", ex(sub, "stage1_ok"), "vsql", ex(sub, "vsql_ok"))
print("7B on all 500: direct", ex(rows, "direct_ok"), "stage1", ex(rows, "stage1_ok"), "vsql", ex(rows, "vsql_ok"))
