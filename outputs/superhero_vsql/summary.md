# 📊 BÁO CÁO THỰC NGHIỆM CHI TIẾT: `20261016-0007_vsql_manual_superhero`

- **Mô hình sử dụng:** `qwen2.5-coder-7b-instruct`
- **Phương pháp:** `VSQL` (View mode: `manual`)
- **Phạm vi:** `superhero` (52 câu hỏi)

## Bảng A — So sánh Execution Accuracy (EX %) với Paper V-SQL

| Nguồn | Mô hình | Phương pháp | SIM | MOD | CHALL | **TOTAL** |
|---|---|---|---|---|---|---|
| Paper | GPT-3.5-turbo | V-SQL | 58.11% | 43.60% | 31.37% | **45.40%** |
| Paper | GPT-4-turbo | V-SQL | 62.16% | 51.60% | 40.19% | **52.80%** |
| Paper | GPT-4 | V-SQL | 62.84% | 59.60% | 37.25% | **56.00%** |
| **Ours** | **qwen2.5-coder-7b-instruct** | **VSQL** | **64.29%** | **53.85%** | **33.33%** | **51.92%** |

## Bảng B — Kết quả Exact Matching (EM %)

> *Ghi chú:* Paper V-SQL không báo cáo chỉ số EM. Số liệu dưới đây được đo bởi nhóm để kiểm tra độ khớp cấu trúc SQL.

| Độ khó | Số câu | EM-Strict (%) | **EM-Normalized (Canonical AST %)** |
|---|---|---|---|
| Simple | 14 | 7.14% | **7.14%** |
| Moderate | 26 | 0.00% | **0.00%** |
| Challenging | 12 | 0.00% | **0.00%** |
| **TOTAL** | **52** | **1.92%** | **1.92%** |

## Bảng C — Chứng minh cơ chế: Thống kê Trước và Sau JOIN

| Độ khó | JOIN Gold | JOIN Dummy (Stage 1) | JOIN Final (Stage 2) | Avg Tokens Dummy | Avg Tokens Final | View Leak |
|---|---|---|---|---|---|---|
| Simple | 0.93 | **0.36** | 0.50 | 33.4 | 33.5 | 3 |
| Moderate | 1.81 | **0.77** | 0.77 | 58.6 | 51.0 | 7 |
| Challenging | 1.58 | **0.50** | 0.67 | 77.1 | 71.2 | 3 |

