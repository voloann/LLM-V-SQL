import os
import sys
import subprocess
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_cmd(cmd_list, desc):
    print("=" * 70, flush=True)
    print(f"▶ BẮT ĐẦU: {desc}", flush=True)
    print(f"  Command: {' '.join(cmd_list)}", flush=True)
    print("=" * 70, flush=True)
    
    ret = subprocess.run(cmd_list, check=False)
    if ret.returncode != 0:
        print(f"[!] CẢNH BÁO: Lệnh kết thúc với mã lỗi {ret.returncode}", flush=True)
    else:
        print(f"[✔] HOÀN TẤT THÀNH CÔNG: {desc}\n", flush=True)
    return ret.returncode

def main():
    parser = argparse.ArgumentParser(description="Chạy thực nghiệm chuẩn hóa: Direct Baseline & V-SQL")
    parser.add_argument("--db", type=str, default="superhero", help="Tên database (mặc định 'superhero' 52 câu hoặc 'all' 500 câu)")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số câu hỏi (tuỳ chọn)")
    args = parser.parse_args()

    python_exe = sys.executable
    db_tag = args.db if args.db != "all" else "500_all"
    
    direct_out = f"outputs/{db_tag}_direct"
    vsql_out = f"outputs/{db_tag}_vsql"

    limit_args = ["--limit", str(args.limit)] if args.limit else []

    # 1. Chạy Direct Baseline
    cmd_direct = [python_exe, "run_experiment.py", "--method", "direct", "--db", args.db, "--output-dir", direct_out] + limit_args
    run_cmd(cmd_direct, f"Direct Baseline ({args.db})")
    subprocess.run([python_exe, "report.py", "--run-dir", direct_out], check=False)

    # 2. Chạy V-SQL 2-Stage
    cmd_vsql = [python_exe, "run_experiment.py", "--method", "vsql", "--view-mode", "manual", "--db", args.db, "--output-dir", vsql_out] + limit_args
    run_cmd(cmd_vsql, f"V-SQL 2-Stage Manual ({args.db})")
    subprocess.run([python_exe, "report.py", "--run-dir", vsql_out], check=False)

    print("\n" + "#" * 70, flush=True)
    print(f"🎉 TOÀN BỘ THỰC NGHIỆM TRÊN '{args.db}' ĐÃ HOÀN TẤT!", flush=True)
    print(f"  • Direct results: {direct_out}/summary.md", flush=True)
    print(f"  • V-SQL results:  {vsql_out}/summary.md", flush=True)
    print("#" * 70 + "\n", flush=True)

if __name__ == "__main__":
    main()
