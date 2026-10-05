import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter


MAX_CONTEXT_CHUNKS_PER_DOCUMENT = 3


class EvaluationDatasetBuilder:
    def __init__(
        self,
        groq_client,
        vectorstore,
        model_name,
        data_dir: Path,
        raw_results_dir: Path,
        timestamp: str,
    ):
        self.groq_client = groq_client
        self.vectorstore = vectorstore
        self.model_name = model_name
        self.data_dir = Path(data_dir)
        self.raw_results_dir = Path(raw_results_dir)
        self.raw_results_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = timestamp

    def load_source_documents(self):
        documents = []

        for role_dir in self.data_dir.iterdir():
            if not role_dir.is_dir():
                continue

            role = role_dir.name.lower()

            for file in role_dir.glob("*"):
                if file.suffix.lower() not in [".txt", ".md", ".csv"]:
                    continue

                if file.suffix.lower() == ".csv":
                    content = pd.read_csv(file).to_string()
                else:
                    with open(file, "r", encoding="utf-8") as source_file:
                        content = source_file.read()

                documents.append({
                    "role": role,
                    "source": file.name,
                    "content": content,
                })

        return documents

    def generate_qa_pairs(self, text_chunk, num_questions=1):
        prompt = f"""
                You are generating evaluation questions for an enterprise RAG system.

                Based ONLY on the Document text provided below, generate exactly {num_questions} unique factual QA pairs that satisfy all conditions:

                - answer must be concise
                - answer should contain only necessary information
                - answerable directly from the document
                - specific and objective
                - non-overlapping
                - cover different sections of the document
                - avoid yes/no questions
                - avoid duplicate meaning

                Document:
                \"\"\"
                {text_chunk}
                \"\"\"

                Return ONLY a valid JSON object with a top-level "qa_pairs" array.

                Example JSON format:
                {{
                    "qa_pairs": [
                    {{
                        "question": "Sample Question 1?",
                        "answer": "Sample Answer 1"
                    }}
                    ]
                }}
                """
        try:
            response = self.groq_client.chat.completions.create(
                model=self.model_name,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )

            parsed = json.loads(response.choices[0].message.content.strip())
            if isinstance(parsed, dict):
                qa_pairs = parsed.get("qa_pairs", parsed.get("questions", []))
            elif isinstance(parsed, list):
                qa_pairs = parsed
            else:
                return []

            return qa_pairs[:num_questions]

        except Exception as exc:
            print(f"QA generation failed: {exc}")
            return []

    def generate_qa_dataset(self):
        documents = self.load_source_documents()
        qa_list = []
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=2500,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""],
        )

        for doc in documents:
            print(f"Generating QA pairs for {doc['source']} ({doc['role']})")
            chunks = splitter.split_text(doc["content"])
            if not chunks:
                print(f"Warning: no usable content in {doc['source']}")
                continue

            selected_count = min(MAX_CONTEXT_CHUNKS_PER_DOCUMENT, len(chunks))
            selected_indices = np.linspace(
                0, len(chunks) - 1, selected_count, dtype=int
            )
            context = "\n\n".join(chunks[index] for index in selected_indices)
            qa_pairs = self.generate_qa_pairs(context, num_questions=1)

            if not qa_pairs:
                print(f"Warning: no question generated for {doc['source']}")

            for qa in qa_pairs:
                retrieved_docs = []
                try:
                    raw_hits = self.vectorstore.similarity_search(
                        qa["question"],
                        k=4,
                        filter={"role": doc["role"]},
                    )
                    retrieved_docs = [hit.page_content for hit in raw_hits]
                except Exception as retrieve_error:
                    print(
                        f"Retrieval lookup failed for '{qa['question']}': "
                        f"{retrieve_error}"
                    )

                relevant_docs = [context, qa["answer"]]
                if not retrieved_docs:
                    retrieved_docs = [context]

                # Generate actual answer from RAG chain for this question & role
                generated_answer = ""
                try:
                    from app.utils.rag_module import get_rag_chain
                    chain = get_rag_chain(user_role=doc["role"])
                    res = chain.invoke({"input": qa["question"]})
                    generated_answer = res.get("answer", "")
                except Exception as gen_err:
                    print(f"RAG answer generation failed for '{qa['question']}': {gen_err}")

                qa_list.append({
                    "question": qa["question"],
                    "answer": qa["answer"],
                    "generated_answer": generated_answer,
                    "role": doc["role"],
                    "source": doc["source"],
                    "retrieved_docs": retrieved_docs,
                    "context": "\n".join(retrieved_docs),
                    "relevant_docs": relevant_docs,
                })

                time.sleep(1.2)

        output_file = self.raw_results_dir / f"qa_dataset_{self.timestamp}.csv"
        pd.DataFrame(qa_list).to_csv(output_file, index=False)

        print(f"\nGenerated {len(qa_list)} QA pairs.")
        print(f"Saved to: {output_file}")

        return qa_list