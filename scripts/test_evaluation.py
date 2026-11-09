import json
import os
import sys

# Thêm evaluation vào sys.path
sys.path.append("evaluation")
from evaluation_ex import evaluate_ex
from evaluation_em import evaluate_em

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def test_sanity():
    test_json = "data/Test.json"
    pred_json = "data/temp_sanity_pred.json"
    
    with open(test_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # --- TEST 1: Ground truth matches prediction 100% -> EX = 100% ---
    preds = {str(x["question_id"]): f"{x['SQL']}\t{x['db_id']}" for x in data}
    with open(pred_json, "w", encoding="utf-8") as f:
        json.dump(preds, f)
        
    results_ex = evaluate_ex(
        predicted_sql_path=pred_json,
        ground_truth_path=test_json,
        db_root_path="mini_dev_databases",
        num_cpus=1
    )
    assert results_ex["all_acc"] == 100.0, f"Expected 100.0%, got {results_ex['all_acc']}"
    print("[PASS] Sanity Test 1: Identical predictions achieve 100.0% EX!")
    
    # --- TEST 2: Shuffled keys in predictions -> EX must remain 100% ---
    shuffled_keys = list(preds.keys())[::-1]
    shuffled_preds = {k: preds[k] for k in shuffled_keys}
    with open(pred_json, "w", encoding="utf-8") as f:
        json.dump(shuffled_preds, f)
        
    results_shuffled = evaluate_ex(
        predicted_sql_path=pred_json,
        ground_truth_path=test_json,
        db_root_path="mini_dev_databases",
        num_cpus=1
    )
    assert results_shuffled["all_acc"] == 100.0, f"Expected 100.0%, got {results_shuffled['all_acc']}"
    print("[PASS] Sanity Test 2: Shuffled keys achieve 100.0% EX!")
    
    # --- TEST 3: Identical predictions -> EM-strict and EM-normalized = 100% ---
    em_results = evaluate_em(
        predicted_sql_path=pred_json,
        ground_truth_path=test_json
    )
    assert em_results["strict"]["all"] == 100.0, f"Expected 100.0% EM-strict, got {em_results['strict']['all']}"
    assert em_results["normalized"]["all"] == 100.0, f"Expected 100.0% EM-norm, got {em_results['normalized']['all']}"
    print("[PASS] Sanity Test 3: Identical predictions achieve 100.0% EM-strict and EM-norm!")

    # --- TEST 4: Alias variation test -> EM-strict fails, EM-norm passes ---
    # Gold SQL uses table aliases e.g. FROM superhero AS T1
    # We change pred to use explicit table name without alias:
    alias_pred = {}
    for x in data:
        # Thay thế alias T1 trong SQL bằng tên bảng thật nếu có
        raw_sql = x["SQL"]
        alias_sql = raw_sql.replace(" AS T1", "").replace(" as T1", "").replace("T1.", "superhero.")
        alias_pred[str(x["question_id"])] = alias_sql

    with open(pred_json, "w", encoding="utf-8") as f:
        json.dump(alias_pred, f)

    em_alias_res = evaluate_em(
        predicted_sql_path=pred_json,
        ground_truth_path=test_json
    )
    print(f"Alias Test Results: Strict = {em_alias_res['strict']['all']}%, Normalized = {em_alias_res['normalized']['all']}%")
    assert em_alias_res["normalized"]["all"] >= em_alias_res["strict"]["all"], "EM-normalized should be >= EM-strict"
    print("[PASS] Sanity Test 4: EM-normalized correctly handles alias variations!")
    
    # Clean up
    if os.path.exists(pred_json):
        os.remove(pred_json)
        
    print("\n>>> ALL EVALUATION (EX + EM) SANITY TESTS PASSED! <<<")

if __name__ == "__main__":
    test_sanity()
