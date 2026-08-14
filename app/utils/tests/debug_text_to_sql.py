import json
from pathlib import Path
from app.rag_evaluator.text_to_sql.runner import TextToSQLRunner

def main():
    # --- Load schema ---
    schema_path = Path("app/schemas/eval_dataset/schema.json")
    with open(schema_path) as f:
        schema = json.load(f)

    # --- Load QA dataset sample ---
    qa_path = Path("app/schemas/eval_dataset/qa_dataset_sample.json")
    with open(qa_path) as f:
        qa_dataset = json.load(f)

    # --- Initialize runner ---
    report_dir = Path("app/rag_evaluator/reports")
    runner = TextToSQLRunner(schema=schema, report_dir=report_dir)

    # --- Run evaluation ---
    df, summary = runner.run(qa_dataset)

    # --- Debug output ---
    print("=== Raw Results ===")
    print(df)
    print("\n=== Summary ===")
    print(json.dumps(summary, indent=4))

if __name__ == "__main__":
    main()
