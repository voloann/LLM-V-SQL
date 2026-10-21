# LLM-V-SQL: Tái hiện & Mở rộng Framework V-SQL

Dự án tái hiện nghiên cứu **V-SQL: A View-based Two-stage Text-to-SQL Framework** (2024) trên bộ dữ liệu chuẩn **BIRD mini-dev** (500 câu hỏi trên 11 CSDL).

- **Tài liệu phân tích chuyên sâu:** [PROJECT_PLAN_V-SQL.md](PROJECT_PLAN_V-SQL.md)
- **Kế hoạch & bảng kiểm soát tiến độ:** [PROJECT_TRACKER.md](PROJECT_TRACKER.md)

---

## ⚡ Khởi chạy Toàn bộ Dự án (Chỉ 1 câu lệnh)

Để khởi động đồng thời cả **Backend Python (FastAPI)** và **Frontend Studio (React + Vite)**:

```bash
npm run dev
```

* 🖥️ **Giao diện Web Frontend (Hot-reload):** `http://localhost:5173`
* ⚙️ **Backend API & Swagger Docs:** `http://localhost:8000` (Docs: `http://localhost:8000/docs`)
* Bấm `Ctrl + C` để tắt đồng thời cả Backend và Frontend.

---

## 1. Yêu cầu hệ thống & Môi trường

- Hệ điều hành: Windows / Linux / macOS
- Python >= 3.10 (Khuyên dùng Python 3.12)
- LM Studio chạy local server tại `http://localhost:1234/v1` (Khuyên dùng mô hình `qwen/qwen3-4b-2507` hoặc `Qwen2.5-Coder-7B`)

### Hướng dẫn cài đặt trên Windows (PowerShell)

```powershell
# 1. Chuyển sang nhánh dev
git checkout dev

# 2. Tạo môi trường ảo .venv
python -m venv .venv

# 3. Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# 4. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt
```

---

## 2. Cấu trúc thư mục

```
LLM-V-SQL/
├── config.py                 # Cấu hình tập trung (URL, model, temp=0, paths)
├── prompts.py                # 3 prompts chuẩn của paper (Hình 2, 4, 5) + baseline Direct
├── llm_client.py             # Client gọi LM Studio (loại <think>, đo token & latency)
├── download_minidev.py       # Tải & giải nén 11 CSDL BIRD mini-dev
├── data/
│   ├── Test.json             # 5 câu smoke test (đã lọc trùng)
│   └── mini_dev_sqlite.json  # 500 câu hỏi chuẩn BIRD mini-dev
├── evaluation/
│   ├── evaluation_ex.py      # Đánh giá Execution Accuracy (EX), khớp strictly theo question_id
│   └── evaluation_utils.py   # Utility kết nối DB (lazy import)
├── mini_dev_databases/       # Thư mục chứa 11 CSDL SQLite
├── scripts/
│   ├── check_gold.py         # Kiểm thử thực thi của 500 câu gold SQL
│   └── test_evaluation.py    # Sanity unit test cho bộ đánh giá EX
├── PROJECT_PLAN_V-SQL.md     # Kế hoạch & phân tích paper chuyên sâu
└── PROJECT_TRACKER.md        # Bảng theo dõi tiến độ từng task (G0 - G7)
```

---

## 3. Quy trình thực hiện

1. **Chuẩn bị dữ liệu (G0):**
   ```powershell
   python scripts/check_gold.py
   ```
2. **Kiểm thử bộ đánh giá EX (G1):**
   ```powershell
   python scripts/test_evaluation.py
   ```
3. **Chạy suy luận demo:**
   Bật LM Studio (Start Local Server tại port 1234), sau đó chạy:
   ```powershell
   python run_demo_LLM.py
   ```
