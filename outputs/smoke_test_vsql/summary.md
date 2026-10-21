# 📊 BÁO CÁO THỰC NGHIỆM CHI TIẾT: `20261015-2344_vsql_manual_full`

- **Mô hình sử dụng:** `qwen2.5-coder-7b-instruct`
- **Phương pháp:** `VSQL` (View mode: `manual`)
- **Phạm vi:** `all` (5 câu hỏi)

## Bảng A — So sánh Execution Accuracy (EX %) với Paper V-SQL

| Nguồn | Mô hình | Phương pháp | SIM | MOD | CHALL | **TOTAL** |
|---|---|---|---|---|---|---|
| Paper | GPT-3.5-turbo | V-SQL | 58.11% | 43.60% | 31.37% | **45.40%** |
| Paper | GPT-4-turbo | V-SQL | 62.16% | 51.60% | 40.19% | **52.80%** |
| Paper | GPT-4 | V-SQL | 62.84% | 59.60% | 37.25% | **56.00%** |
| **Ours** | **qwen2.5-coder-7b-instruct** | **VSQL** | **0.00%** | **66.67%** | **100.00%** | **60.00%** |

## Bảng B — Kết quả Exact Matching (EM %)

> *Ghi chú:* Paper V-SQL không báo cáo chỉ số EM. Số liệu dưới đây được đo bởi nhóm để kiểm tra độ khớp cấu trúc SQL.

| Độ khó | Số câu | EM-Strict (%) | **EM-Normalized (Canonical AST %)** |
|---|---|---|---|
| Simple | 1 | 0.00% | **0.00%** |
| Moderate | 3 | 0.00% | **0.00%** |
| Challenging | 1 | 0.00% | **0.00%** |
| **TOTAL** | **5** | **0.00%** | **0.00%** |

## Bảng C — Chứng minh cơ chế: Thống kê Trước và Sau JOIN

| Độ khó | JOIN Gold | JOIN Dummy (Stage 1) | JOIN Final (Stage 2) | Avg Tokens Dummy | Avg Tokens Final | View Leak |
|---|---|---|---|---|---|---|
| Simple | 2.00 | **1.00** | 1.00 | 49.0 | 43.0 | 0 |
| Moderate | 2.00 | **0.67** | 1.00 | 49.3 | 45.0 | 1 |
| Challenging | 2.00 | **4.00** | 0.00 | 114.0 | 38.0 | 1 |

