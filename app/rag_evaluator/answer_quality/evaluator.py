# evaluator.py
try:
    from ragas.metrics.collections import Faithfulness, ContextRelevance, AnswerRelevancy, AnswerAccuracy
    from ragas import evaluate
except ImportError:  # pragma: no cover - exercised when optional deps are missing
    Faithfulness = ContextRelevance = AnswerRelevancy = AnswerAccuracy = None
    evaluate = None

try:
    from sentence_transformers import SentenceTransformer, util
except ImportError:  # pragma: no cover - exercised when optional deps are missing
    SentenceTransformer = None
    util = None

try:
    from groq import Groq
except ImportError:  # pragma: no cover - exercised when optional deps are missing
    Groq = None

import os, json, logging
from typing import Dict

logger = logging.getLogger(__name__)

# Define required metrics and their valid range
REQUIRED_METRICS = {"Faithfulness", "Relevance", "Completeness", "Clarity"}
VALID_SCORE_RANGE = (0.0, 1.0)

class AnswerQualityEvaluator:
    def __init__(self, embedding_model="sentence-transformers/all-MiniLM-L6-v2"):
        self.embedding_model_name = embedding_model
        self._embedder = None
        self._groq_client = None

    # Embedding Model for similarity
    @property
    def embedder(self):
        if self._embedder is None and SentenceTransformer is not None:
            self._embedder = SentenceTransformer(self.embedding_model_name)
        return self._embedder

    #Groq Client for LLM evaluation
    @property
    def groq_client(self):
        if self._groq_client is None and Groq is not None:
            groq_api_key = os.getenv("GROQ_API_KEY")
            self._groq_client = Groq(api_key=groq_api_key)
        return self._groq_client

    def embedding_similarity(self, generated_answer: str, reference_answer: str) -> float:
        """Compute cosine similarity between generated and reference answers."""
        if self.embedder is None or util is None:
            return 0.0

        emb1 = self.embedder.encode(generated_answer, convert_to_tensor=True)
        emb2 = self.embedder.encode(reference_answer, convert_to_tensor=True)
        return float(util.cos_sim(emb1, emb2).item())

    def _validate_and_convert_scores(self, scores: dict) -> Dict[str, float]:
        """
        Validate and convert scores to float with range checking.
        
        Args:
            scores: Dictionary of metric scores
            
        Returns:
            Dictionary with validated float scores
            
        Raises:
            ValueError: If scores are invalid or out of range
        """
        validated = {}
        
        for metric in REQUIRED_METRICS:
            if metric not in scores:
                metric = metric.lower()
                logger.warning(f"Missing metric: {metric}. Using default 0.0")
                validated[metric] = 0.0
                continue
            
            try:
                # Convert to float explicitly
                value = float(scores[metric])
            except (TypeError, ValueError) as e:
                logger.error(f"Cannot convert {metric}={scores[metric]} to float: {e}")
                raise ValueError(f"Invalid score for {metric}: {scores[metric]}") from e
            
            # Validate range
            if not (VALID_SCORE_RANGE[0] <= value <= VALID_SCORE_RANGE[1]):
                logger.warning(f"{metric}={value} out of range [0.0, 1.0]. Clamping to valid range.")
                value = max(VALID_SCORE_RANGE[0], min(VALID_SCORE_RANGE[1], value))
            
            validated[metric] = value
        
        return validated

    def llm_judge(self, query: str, context: str, answer: str) -> Dict[str, float]:
        """Use Groq LLM to rate answer quality on multiple dimensions."""
        if self.groq_client is None:
            return {metric: 0.5 for metric in REQUIRED_METRICS}

        prompt = f"""You are an evaluator for a RAG system.

        Evaluate the predicted answer to a question using the retrieved context and compare it to the ground truth.

        Return a JSON object with the following keys and value must be float between 0.0 and 1.0:
        - "Faithfulness": Is the predicted answer grounded in the retrieved context?
        - "Relevance": Is the answer relevant to the question?
        - "Clarity": How clear and understandable is the answer?
        - "Completeness": Does the answer fully address the question?

        Evaluate the following answer for the query: {query}
        Context: {context}
        Answer: {answer}

        Provide scores ONLY in valid JSON like:
        {{
        "Faithfulness": 1.0,
        "Relevance": 0.8,
        "Completeness": 0.9,
        "Clarity": 0.7
        }}
        """
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_output = response.choices[0].message.content.strip()
            
            try:
                scores = json.loads(raw_output)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed: {e}. Raw output: {raw_output}")
                scores = {metric: 0.5 for metric in REQUIRED_METRICS}

            if not isinstance(scores, dict):
                logger.warning(f"LLM response was not a JSON object, got {type(scores).__name__}; using default scores")
                scores = {metric: 0.5 for metric in REQUIRED_METRICS}
            
            # Validate and convert all scores to float
            validated_scores = self._validate_and_convert_scores(scores)
            return validated_scores
            
        except Exception as e:
            logger.error(f"Error in llm_judge: {e}")
            # Fallback: return neutral scores
            return {metric: 0.5 for metric in REQUIRED_METRICS}

    def ragas_evaluation(self, dataset):
        """Run RAGAS evaluation on dataset (queries, contexts, answers)."""
        if evaluate is None or any(metric is None for metric in [Faithfulness, ContextRelevance, AnswerRelevancy, AnswerAccuracy]):
            return {"status": "unavailable", "reason": "ragas is not installed"}

        result = evaluate(dataset, metrics=[
            # faithfulness, answer_relevancy, context_relevancy, answer_similarity
            Faithfulness, ContextRelevance, AnswerRelevancy, AnswerAccuracy
        ])
        return result

    def evaluate_answer(self, query, context, generated_answer, reference_answer=None) -> Dict[str, float]:
        """Main entry point for evaluation pipeline."""
        results = {}

        embedding_score = None
        # Embedding similarity if reference available
        if reference_answer:
            embedding_score = self.embedding_similarity(
                generated_answer, reference_answer
            )

        # LLM judge scoring
        llm_scores = self.llm_judge(
        query,
        context,
        generated_answer
    )

        results = {
            "faithfulness": llm_scores.get("Faithfulness", 0.0),
            "relevance": llm_scores.get("Relevance", 0.0),
            "completeness": llm_scores.get("Completeness", 0.0),
            "clarity": llm_scores.get("Clarity", 0.0),
            "embedding_similarity": embedding_score
            if embedding_score is not None
            else 0.0
        }

        return results