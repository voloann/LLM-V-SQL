# Môn HỆ CƠ SỞ DỮ LIỆU TIÊN TIẾN - IS6002.26.1.CH.02
# Paper: V-SQL: A View-based Two-stage Text-to-SQL Framework 2024

Dự án tái hiện nghiên cứu **V-SQL: A View-based Two-stage Text-to-SQL Framework** (2024) trên bộ dữ liệu chuẩn **BIRD mini-dev** (500 câu hỏi trên 11 CSDL).

- **Tài liệu phân tích chuyên sâu:** [PROJECT_PLAN_V-SQL.md](PROJECT_PLAN_V-SQL.md)
- **Kế hoạch & bảng kiểm soát tiến độ:** [PROJECT_TRACKER.md](PROJECT_TRACKER.md)

**Thành viên nhóm **
- Lâm Thị Anh Đào - 250201049
- Võ Đoàn Tố Loan - 26848115
- Trương Kim Lâm - 250202044
- Mou Sa Ka Riêm - 26848186


---

## ⚡ Khởi chạy Toàn bộ Dự án (Chỉ 1 câu lệnh)

Để khởi động đồng thời cả **Backend Python (FastAPI)** và **Frontend Studio (React + Vite)**:

```bash
npm run dev
```

* 🖥️ **Giao diện Web Frontend (Hot-reload):** `http://localhost:5173`
* ⚙️ **Backend API & Swagger Docs:** `http://localhost:8000` (Docs: `http://localhost:8000/docs`)
* Bấm `Ctrl + C` để tắt đồng thời cả Backend và Frontend.
* Trên macOS/Linux, kích hoạt `.venv` trước để có lệnh `python`.
* Nếu port 8000 đã bị chiếm, đổi port backend (frontend tự proxy theo): `API_PORT=8001 npm run dev`

---

## Demo báo cáo

Sau khi chạy `npm run dev`, mở hai trang đầu của mục **Tương tác & Học thuật** ở thanh bên:

- **Hành trình thực nghiệm:** các lần chạy theo thứ tự thực hiện, lý do của từng lần và kết quả.
- **Chạy pipeline từng bước:** chọn câu hỏi, framework, model, bộ view, rồi xem đầu vào và đầu ra của từng bước.
  - *Phát lại kết quả đã lưu:* không gọi model, không tốn tiền, không cần mạng. Nên dùng khi trình bày.
  - *Gọi model thật:* cần Ollama đang chạy cho model cục bộ, hoặc API key ở `~/.config/llm-v-sql/llm.key` cho GPT-6 Luna. Key chỉ nằm ở server, mỗi lần chạy có hạn mức tiền riêng.

## Tái lập kết quả

```bash
python build_views.py                                # tạo views/fk, views/gold, views/paper và views/coverage_report.json
scripts/run_view_extension_benchmark.sh 0.6          # V-SQL 500 câu với 3 bộ view, tối đa $0.60 mỗi lượt
python scripts/analyze_view_extension.py             # so sánh theo từng câu, ghi outputs/view_extension_analysis.json
python scripts/run_benchmark.py outputs/<thư_mục> gpt-6-luna --view-mode manual --schema-mode described --budget 1
```

`run_benchmark.py` đọc `outputs/<thư_mục>/questions.json`, dùng lại trace đã có nên chạy tiếp được khi bị ngắt, và chấm trên kết nối chỉ đọc tới bảng gốc. Mẫu 100 câu tạo bằng `scripts/make_sample.py`, kết quả 7B được chấm lại bằng `scripts/rescore_physical.py`.

| Bộ view | Cách tạo | Lưu ý |
|---|---|---|
| `manual` | 27 view viết tay từ các phép join trong gold SQL | Phủ 279/798 cột |
| `paper` | `manual` thêm các cột gold SQL cần, cộng view `LEFT JOIN` cho tổ hợp bảng dùng từ 3 câu trở lên | **Cấu hình chính.** Bám cách paper mô tả nhưng không phải bộ view của paper, vì paper không công bố |
| `fk` | `manual` thêm mọi cột, và thêm view cho từng bảng còn thiếu theo khóa ngoại | Mở rộng của nhóm. Phần mở rộng không đọc gold SQL |
| `gold` | `manual` thêm đúng cột và mọi tổ hợp join mà gold SQL cần | Đối chứng cho cảnh báo của paper. View INNER JOIN có thể làm mất dòng |

Kết quả cấu hình chính (view `paper`, schema có kiểu và mô tả cột, 500 câu, chấm trên bảng gốc, mỗi model chạy một lần). `scripts/run_main_config_benchmark.sh` chạy lại 3 model Qwen.

| Model | Direct | Stage 1 | V-SQL | Chỉ Direct đúng / chỉ V-SQL đúng | p |
|---|---|---|---|---|---|
| Qwen3 4B | 47.4% | 36.6% | 42.2% | 66 / 40 | 0.015 |
| Qwen2.5-Coder 7B | 49.8% | 36.2% | 38.6% | 92 / 36 | < 0.001 |
| Qwen2.5-Coder 32B | 56.2% | 47.4% | 54.2% | 47 / 37 | 0.33 |
| GPT-6 Luna | 61.4% | 53.8% | 58.6% | 42 / 28 | 0.12 |

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
