# LLM-V

## Dataset của paper
```
Link git: https://bird-bench.github.io/
Link dataset: https://github.com/bird-bench/mini_dev
Câu để truy vấn trong paper: https://huggingface.co/datasets/birdsql/bird_mini_dev/viewer/default/mini_dev_mysql?row=0
```


## Tổng quan
```
Ngôn ngữ sử dụng: python
CSDL để chạy: SQLlite
Mô hình LLM: local thông qua LM studio (mô hình hiện tại là qwen/qwen3-4b-2507
CSDL test trong đây là superhero
Tổng số câu test là 6 câu
```

## Thư mục
```
Demo Test-to-SQL/
├── .venv/: mô trường python ảo cần tạo
├── config.py: chỉnh sửa mô hình LM studio
├── create_views_LLM.py: bước 0 tạo table mapping
├── prompts.py: tổng hợp 3 câu prompts
├── requirements.txt
├── run_demo_LLM.py: demo và đánh giá mô hình
├── v_sql_pipeline_LLM.py: Mô hình V-SQL 2 stage
├── data/
│   ├── Test.json: 6 câu để test
│   ├── mini_dev_sqllite.json: toàn bộ 500 câu SQL
├── evaluation/
│   ├── evaluation_ex.py
│   └── evaluation_utils.py
├── mini_dev_databases/
│   └── superhero/
│       └── superhero.sqlite
```

## Cách chạy
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 run_demo_LLM.py
```
Khi chạy xong sẽ tạo ra 2 file: view_mappings.json (bước 0) và predict_dev.json (file json dự đoán kết quả)




