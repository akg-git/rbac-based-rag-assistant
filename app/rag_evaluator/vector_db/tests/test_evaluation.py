import json
import tempfile
import unittest
from pathlib import Path

from langchain_core.documents import Document

from app.rag_evaluator.vector_db.evaluator import VectorDBEvaluator
from app.rag_evaluator.vector_db.runner import VectorDBRunner


class FakeCollection:
    def __init__(self, *args, **kwargs):
        self.added_documents = []
        self.deleted = False

    def add_documents(self, documents):
        self.added_documents = documents

    def similarity_search(self, query, k):
        return [
            Document(
                page_content=query,
                metadata={"source": "marketing_report_2024.md"},
            ),
            Document(page_content=query, metadata={"source": "source_b"}),
        ][:k]

    def delete_collection(self):
        self.deleted = True


class TestVectorDBEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = VectorDBEvaluator()
        self.retrieval_times = [0.05, 0.07, 0.06]

    def test_index_performance(self):
        result = self.evaluator.index_performance(self.retrieval_times)
        self.assertIn("avg_retrieval_time", result)
        self.assertIn("max_retrieval_time", result)
        self.assertIn("min_retrieval_time", result)

    def test_ranking_metrics(self):
        result = self.evaluator.evaluate(
            ["source_a", "source_b", "source_c"],
            ["source_a", "source_c"],
            self.retrieval_times,
        )

        self.assertEqual(result["recall_at_k"], 2 / 2)
        self.assertEqual(result["mrr"], 1.0)
        self.assertAlmostEqual(result["ndcg_at_k"], 1.0, delta=0.1)
        self.assertIn("avg_retrieval_time", result)

    def test_ranking_metrics_handle_missing_expected_sources(self):
        result = self.evaluator.evaluate(
            ["source_a", "source_b"],
            ["source_c"],
            self.retrieval_times,
        )

        self.assertEqual(result["recall_at_k"], 0.0)
        self.assertEqual(result["mrr"], 0.0)
        self.assertEqual(result["ndcg_at_k"], 0.0)


class TestVectorDBRunner(unittest.TestCase):
    def test_run_uses_isolated_collection_and_persists_metrics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            data_dir = root / "data"
            data_dir.joinpath("marketing").mkdir(parents=True)
            source = data_dir / "marketing" / "marketing_report_2024.md"
            source.write_text("Marketing results", encoding="utf-8")

            dataset_path = root / "dataset.json"
            dataset_path.write_text(
                json.dumps(
                    {
                        "documents": [
                            {
                                "source": "marketing_report_2024.md",
                                "role": "marketing",
                                "description": "Marketing results",
                            }
                        ],
                        "queries": [
                            {
                                "query": "What annual marketing results are described?",
                                "expected_sources": ["marketing_report_2024.md"],
                                "role": "marketing",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report_dir = root / "reports"
            collection = FakeCollection()
            runner = VectorDBRunner(
                report_dir=report_dir,
                data_dir=data_dir,
                evaluation_dataset_path=dataset_path,
                embedding_function=lambda documents: [0.1] * len(documents),
                collection_factory=lambda **kwargs: collection,
            )

            result_df, summary = runner.run(k=2)

            self.assertEqual(len(result_df), 1)
            self.assertEqual(result_df.iloc[0]["recall_at_k"], 1.0)
            self.assertEqual(summary["samples"], 1)
            self.assertTrue(collection.deleted)
            self.assertEqual(
                len(list((report_dir / "raw_results").glob("vector_db_results_*.csv"))),
                1,
            )


if __name__ == "__main__":
    unittest.main()
