import os
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PAPER_RESULTS = {
    "GPT-3.5-turbo": {"DIN-SQL": 39.20, "DAIL-SQL": 42.00, "TA-SQL": 43.80, "V-SQL": 45.40, "SIM": 58.11, "MOD": 43.60, "CHALL": 31.37},
    "GPT-4-turbo": {"DIN-SQL": 47.80, "DAIL-SQL": 48.80, "TA-SQL": 50.16, "V-SQL": 52.80, "SIM": 62.16, "MOD": 51.60, "CHALL": 40.19},
    "GPT-4": {"DIN-SQL": 47.20, "DAIL-SQL": 49.00, "TA-SQL": 56.17, "V-SQL": 56.00, "SIM": 62.84, "MOD": 59.60, "CHALL": 37.25}
}

def generate_summary_markdown(run_dir: str):
    trace_file = os.path.join(run_dir, "trace.jsonl")
    metrics_file = os.path.join(run_dir, "metrics.json")
    summary_file = os.path.join(run_dir, "summary.md")
    
    if not os.path.exists(trace_file):
        print(f"Error: {trace_file} not found.")
        return

    metrics = {}
    if os.path.exists(metrics_file):
        with open(metrics_file, "r", encoding="utf-8") as f:
            metrics = json.load(f)

    records = []
    with open(trace_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    # Thống kê trước / sau JOIN và tokens
    diff_stats = defaultdict(lambda: {
        "n": 0, "gold_joins": 0, "dummy_joins": 0, "final_joins": 0,
        "dummy_tokens": 0, "final_tokens": 0, "view_leaks": 0
    })
    
    db_stats = defaultdict(lambda: {"n": 0, "final_joins": 0})

    for r in records:
        diff = r.get("difficulty", "simple").lower()
        t = r.get("trace", {})
        s1 = t.get("stage1", {})
        s2 = t.get("stage2", {})
        
        diff_stats[diff]["n"] += 1
        diff_stats[diff]["gold_joins"] += r.get("gold_joins", 0)
        diff_stats[diff]["dummy_joins"] += s1.get("joins", 0)
        diff_stats[diff]["final_joins"] += s2.get("joins", t.get("joins", 0))
        diff_stats[diff]["dummy_tokens"] += s1.get("tokens", 0)
        diff_stats[diff]["final_tokens"] += s2.get("tokens", t.get("tokens", 0))
        if s2.get("view_leak"):
            diff_stats[diff]["view_leaks"] += 1
            
        db_id = r.get("db_id", "unknown")
        db_stats[db_id]["n"] += 1

    md = []
    md.append(f"# 📊 BÁO CÁO THỰC NGHIỆM CHI TIẾT: `{metrics.get('run_id', os.path.basename(run_dir))}`\n")
    md.append(f"- **Mô hình sử dụng:** `{metrics.get('model', 'Unknown')}`")
    md.append(f"- **Phương pháp:** `{metrics.get('method', 'Unknown').upper()}` (View mode: `{metrics.get('view_mode', 'N/A')}`)")
    md.append(f"- **Phạm vi:** `{metrics.get('scope', 'all')}` ({metrics.get('num_queries', len(records))} câu hỏi)\n")

    # Bảng A: EX so với Paper
    md.append("## Bảng A — So sánh Execution Accuracy (EX %) với Paper V-SQL\n")
    md.append("| Nguồn | Mô hình | Phương pháp | SIM | MOD | CHALL | **TOTAL** |")
    md.append("|---|---|---|---|---|---|---|")
    for m_name, vals in PAPER_RESULTS.items():
        md.append(f"| Paper | {m_name} | V-SQL | {vals['SIM']:.2f}% | {vals['MOD']:.2f}% | {vals['CHALL']:.2f}% | **{vals['V-SQL']:.2f}%** |")
    
    our_ex = metrics.get("EX", {})
    md.append(f"| **Ours** | **{metrics.get('model', 'Local')}** | **{metrics.get('method', '').upper()}** | **{our_ex.get('simple', 0.0):.2f}%** | **{our_ex.get('moderate', 0.0):.2f}%** | **{our_ex.get('challenging', 0.0):.2f}%** | **{our_ex.get('total', 0.0):.2f}%** |\n")

    # Bảng B: EM
    em_st = metrics.get("EM_strict", {})
    em_nm = metrics.get("EM_normalized", {})
    md.append("## Bảng B — Kết quả Exact Matching (EM %)\n")
    md.append("> *Ghi chú:* Paper V-SQL không báo cáo chỉ số EM. Số liệu dưới đây được đo bởi nhóm để kiểm tra độ khớp cấu trúc SQL.\n")
    md.append("| Độ khó | Số câu | EM-Strict (%) | **EM-Normalized (Canonical AST %)** |")
    md.append("|---|---|---|---|")
    for d in ["simple", "moderate", "challenging"]:
        cnt = diff_stats[d]["n"]
        md.append(f"| {d.capitalize()} | {cnt} | {em_st.get(d, 0.0):.2f}% | **{em_nm.get(d, 0.0):.2f}%** |")
    md.append(f"| **TOTAL** | **{len(records)}** | **{em_st.get('all', 0.0):.2f}%** | **{em_nm.get('all', 0.0):.2f}%** |\n")

    # Bảng C: Trước và sau JOIN
    md.append("## Bảng C — Chứng minh cơ chế: Thống kê Trước và Sau JOIN\n")
    md.append("| Độ khó | JOIN Gold | JOIN Dummy (Stage 1) | JOIN Final (Stage 2) | Avg Tokens Dummy | Avg Tokens Final | View Leak |")
    md.append("|---|---|---|---|---|---|---|")
    for d in ["simple", "moderate", "challenging"]:
        st = diff_stats[d]
        n = st["n"] if st["n"] > 0 else 1
        md.append(f"| {d.capitalize()} | {st['gold_joins']/n:.2f} | **{st['dummy_joins']/n:.2f}** | {st['final_joins']/n:.2f} | {st['dummy_tokens']/n:.1f} | {st['final_tokens']/n:.1f} | {st['view_leaks']} |")
    md.append("\n")

    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    print(f"[+] Đã tạo báo cáo Markdown tại: {summary_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=str, required=True, help="Thư mục run_id")
    args = parser.parse_args()
    generate_summary_markdown(args.run_dir)
