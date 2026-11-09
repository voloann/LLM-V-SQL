# 📊 BÁO CÁO THỰC NGHIỆM CHI TIẾT: `20261016-0104_direct_manual_full`

- **Mô hình sử dụng:** `qwen2.5-coder-7b-instruct`
- **Phương pháp:** `DIRECT` (View mode: `manual`)
- **Phạm vi:** `all` (500 câu hỏi)

## Bảng A — So sánh Execution Accuracy (EX %) với Paper V-SQL

| Nguồn | Mô hình | Phương pháp | SIM | MOD | CHALL | **TOTAL** |
|---|---|---|---|---|---|---|
| Paper | GPT-3.5-turbo | V-SQL | 58.11% | 43.60% | 31.37% | **45.40%** |
| Paper | GPT-4-turbo | V-SQL | 62.16% | 51.60% | 40.19% | **52.80%** |
| Paper | GPT-4 | V-SQL | 62.84% | 59.60% | 37.25% | **56.00%** |
| **Ours** | **qwen2.5-coder-7b-instruct** | **DIRECT** | **67.57%** | **43.60%** | **27.45%** | **47.40%** |

## Bảng B — Kết quả Exact Matching (EM %)

> *Ghi chú:* Paper V-SQL không báo cáo chỉ số EM. Số liệu dưới đây được đo bởi nhóm để kiểm tra độ khớp cấu trúc SQL.

| Độ khó | Số câu | EM-Strict (%) | **EM-Normalized (Canonical AST %)** |
|---|---|---|---|
| Simple | 148 | 20.27% | **22.97%** |
| Moderate | 250 | 4.80% | **4.80%** |
| Challenging | 102 | 1.96% | **2.94%** |
| **TOTAL** | **500** | **8.80%** | **9.80%** |

## Bảng C — Chứng minh cơ chế: Thống kê Trước và Sau JOIN

| Độ khó | JOIN Gold | JOIN Dummy (Stage 1) | JOIN Final (Stage 2) | Avg Tokens Dummy | Avg Tokens Final | View Leak |
|---|---|---|---|---|---|---|
| Simple | 0.68 | **0.00** | 0.69 | 0.0 | 40.7 | 0 |
| Moderate | 1.14 | **0.00** | 1.12 | 0.0 | 60.4 | 0 |
| Challenging | 1.39 | **0.00** | 1.40 | 0.0 | 83.3 | 0 |

