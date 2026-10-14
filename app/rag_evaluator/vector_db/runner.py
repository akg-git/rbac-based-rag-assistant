"""Run an isolated Chroma benchmark against the authoritative evaluation dataset."""

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from app.rag_evaluator.vector_db.evaluator import VectorDBEvaluator

class VectorDBRunner:
    """Build a disposable collection, retrieve real sources, and persist metrics."""

    def __init__(
        self,
        report_dir: Path = Path("app/rag_evaluator/reports"),
        data_dir: Path = Path("resources/data"),
        evaluation_dataset_path: Path = Path(
            "app/schemas/eval_dataset/vector_db_eval_dataset.json"
        ),
        embedding_function: Callable | None = None,
        collection_factory: Callable[..., Any] = Chroma,
    ):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.report_dir = report_dir
        self.raw_results_dir = report_dir / "raw_results"
        self.summary_dir = report_dir / "summaries"
        self.data_dir = Path(data_dir)
        self.evaluation_dataset_path = Path(evaluation_dataset_path)
        self.embedding_function = embedding_function
        self.collection_factory = collection_factory
        self.evaluator = VectorDBEvaluator()

        self.raw_results_dir.mkdir(parents=True, exist_ok=True)
        self.summary_dir.mkdir(parents=True, exist_ok=True)

    def _load_dataset(self) -> dict[str, Any]:
        with self.evaluation_dataset_path.open(encoding="utf-8") as dataset_file:
            dataset = json.load(dataset_file)

        documents = dataset.get("documents", [])
        queries = dataset.get("queries", [])
        if not documents or not queries:
            raise ValueError("Vector DB dataset must contain documents and queries")
        return dataset

    def _load_documents(self, documents: list[dict[str, Any]]) -> list[Document]:
        loaded: list[Document] = []
        for document in documents:
            source = document["source"]
            source_path = self.data_dir / document["role"] / source
            if not source_path.is_file():
                raise FileNotFoundError(f"Evaluation document not found: {source_path}")
            loaded.append(
                Document(
                    page_content=source_path.read_text(encoding="utf-8"),
                    metadata={
                        "source": source,
                        "role": document["role"],
                        "description": document.get("description", ""),
                    },
                )
            )
        return loaded

    def _build_collection(self) -> tuple[Any, str]:
        temporary_directory = tempfile.mkdtemp(prefix="rag-vector-db-eval-")
        embedding_function = self.embedding_function or HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        collection = self.collection_factory(
            persist_directory=temporary_directory,
            embedding_function=embedding_function,
            collection_name="evaluation_collection",
        )
        return collection, temporary_directory

    def run(self, k: int = 5) -> tuple[pd.DataFrame, dict[str, float]]:
        """Execute the benchmark and persist one row per query."""
        if k <= 0:
            raise ValueError("k must be greater than zero")

        dataset = self._load_dataset()
        documents = self._load_documents(dataset["documents"])
        collection, temporary_directory = self._build_collection()

        try:
            collection.add_documents(documents=documents)
            rows: list[dict[str, Any]] = []

            for query in dataset["queries"]:
                start = time.perf_counter()
                results = collection.similarity_search(
                    query["query"],
                    k=k,
                )
                retrieval_time = time.perf_counter() - start
                retrieved_sources = [document.metadata["source"] for document in results]
                expected_sources = query.get("expected_sources", [])
                scores = self.evaluator.evaluate(
                    retrieved_sources,
                    expected_sources,
                    [retrieval_time],
                    k=k,
                )
                rows.append(
                    {
                        "query": query["query"],
                        "role": query.get("role", ""),
                        "expected_sources": expected_sources,
                        "retrieved_sources": retrieved_sources,
                        "recall_at_k": scores["recall_at_k"],
                        "mrr": scores["mrr"],
                        "ndcg_at_k": scores["ndcg_at_k"],
                        "avg_retrieval_time": scores["avg_retrieval_time"],
                        "max_retrieval_time": scores["max_retrieval_time"],
                        "min_retrieval_time": scores["min_retrieval_time"],
                    }
                )

            result_df = pd.DataFrame(rows)
            result_file = self.raw_results_dir / f"vector_db_results_{self.timestamp}.csv"
            result_df.to_csv(result_file, index=False)

            summary = {
                "samples": len(result_df),
                "recall_at_k_avg": round(result_df["recall_at_k"].mean(), 3),
                "mrr_avg": round(result_df["mrr"].mean(), 3),
                "ndcg_at_k_avg": round(result_df["ndcg_at_k"].mean(), 3),
                "avg_retrieval_time_avg": round(
                    result_df["avg_retrieval_time"].mean(), 6
                ),
            }
            summary_file = self.summary_dir / f"vector_db_summary_{self.timestamp}.json"
            summary_file.write_text(json.dumps(summary, indent=4), encoding="utf-8")
            return result_df, summary
        finally:
            collection.delete_collection()
            shutil.rmtree(temporary_directory, ignore_errors=True)
