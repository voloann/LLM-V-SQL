import sys
import json
import collections
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import sqlglot
from sqlglot import exp

def analyze_dataset(data_path="data/mini_dev_sqlite.json"):
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Thống kê theo độ khó (Tái hiện Bảng 2 paper)
    diff_stats = collections.defaultdict(lambda: {"n": 0, "joins": 0, "tables": 0, "combos": set()})
    db_stats = collections.defaultdict(lambda: {"n": 0, "combos": collections.defaultdict(int)})

    total_n = len(data)
    total_joins = 0
    total_tables = 0
    all_combos = set()

    for d in data:
        difficulty = d.get("difficulty", "unknown").lower()
        db_id = d.get("db_id", "unknown")
        sql = d.get("SQL", "")

        try:
            tree = sqlglot.parse_one(sql, read="sqlite")
            joins = len(list(tree.find_all(exp.Join)))
            tabs = tuple(sorted({t.name.lower() for t in tree.find_all(exp.Table) if t.name}))
        except Exception:
            # Fallback nếu sqlglot parse lỗi cú pháp riêng
            joins = sql.lower().count(" join ")
            tabs = ("unknown",)

        diff_stats[difficulty]["n"] += 1
        diff_stats[difficulty]["joins"] += joins
        diff_stats[difficulty]["tables"] += len(tabs)
        diff_stats[difficulty]["combos"].add((db_id,) + tabs)

        total_joins += joins
        total_tables += len(tabs)
        all_combos.add((db_id,) + tabs)

        db_stats[db_id]["n"] += 1
        db_stats[db_id]["combos"][tabs] += 1

    print("=" * 65)
    print("BANG 2 REPRODUCTION: THONG KE DATASET BIRD MINI-DEV")
    print("=" * 65)
    print(f"{'Difficulty':<12} | {'Count':<6} | {'Avg JOINs':<10} | {'Avg Tables':<10} | {'Combos':<6}")
    print("-" * 65)
    for diff in ["simple", "moderate", "challenging"]:
        s = diff_stats[diff]
        avg_j = s["joins"] / s["n"] if s["n"] else 0
        avg_t = s["tables"] / s["n"] if s["n"] else 0
        print(f"{diff:<12} | {s['n']:<6} | {avg_j:<10.2f} | {avg_t:<10.2f} | {len(s['combos']):<6}")
    print("-" * 65)
    print(f"{'TOTAL':<12} | {total_n:<6} | {total_joins/total_n:<10.2f} | {total_tables/total_n:<10.2f} | {len(all_combos):<6}")
    print("=" * 65)

    print("\n📁 PHÂN BỐ CÂU HỎI & TỔ HỢP BẢNG THEO DATABASE:")
    for db_id, s in sorted(db_stats.items(), key=lambda x: -x[1]["n"]):
        print(f"\n  • DB: {db_id} ({s['n']} câu hỏi, {len(s['combos'])} tổ hợp bảng):")
        # In các tổ hợp bảng phổ biến nhất
        sorted_combos = sorted(s["combos"].items(), key=lambda x: -x[1])
        for combo, count in sorted_combos[:5]:
            tables_str = ", ".join(combo)
            print(f"      - [{count}x]: {tables_str}")

if __name__ == "__main__":
    analyze_dataset()
