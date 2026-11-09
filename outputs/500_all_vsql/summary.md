# 📊 BÁO CÁO THỰC NGHIỆM CHI TIẾT: `20261016-0302_vsql_manual_full`

- **Mô hình sử dụng:** `qwen2.5-coder-7b-instruct`
- **Phương pháp:** `VSQL` (View mode: `manual`)
- **Phạm vi:** `all` (500 câu hỏi)

## Bảng A — So sánh Execution Accuracy (EX %) với Paper V-SQL

| Nguồn | Mô hình | Phương pháp | SIM | MOD | CHALL | **TOTAL** |
|---|---|---|---|---|---|---|
| Paper | GPT-3.5-turbo | V-SQL | 58.11% | 43.60% | 31.37% | **45.40%** |
| Paper | GPT-4-turbo | V-SQL | 62.16% | 51.60% | 40.19% | **52.80%** |
| Paper | GPT-4 | V-SQL | 62.84% | 59.60% | 37.25% | **56.00%** |
| **Ours** | **qwen2.5-coder-7b-instruct** | **VSQL** | **47.30%** | **30.80%** | **20.59%** | **33.60%** |

## Bảng B — Kết quả Exact Matching (EM %)

> *Ghi chú:* Paper V-SQL không báo cáo chỉ số EM. Số liệu dưới đây được đo bởi nhóm để kiểm tra độ khớp cấu trúc SQL.

| Độ khó | Số câu | EM-Strict (%) | **EM-Normalized (Canonical AST %)** |
|---|---|---|---|
| Simple | 148 | 4.05% | **10.81%** |
| Moderate | 250 | 0.80% | **2.40%** |
| Challenging | 102 | 0.98% | **1.96%** |
| **TOTAL** | **500** | **1.80%** | **4.80%** |

## Bảng C — Chứng minh cơ chế: Thống kê Trước và Sau JOIN

| Độ khó | JOIN Gold | JOIN Dummy (Stage 1) | JOIN Final (Stage 2) | Avg Tokens Dummy | Avg Tokens Final | View Leak |
|---|---|---|---|---|---|---|
| Simple | 0.68 | **0.33** | 0.71 | 50.6 | 47.2 | 5 |
| Moderate | 1.14 | **0.56** | 0.97 | 74.4 | 65.0 | 9 |
| Challenging | 1.39 | **0.48** | 1.03 | 93.1 | 85.9 | 7 |

