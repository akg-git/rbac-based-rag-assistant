import unittest
from unittest.mock import patch, MagicMock
from app.rag_evaluator.answer_quality.evaluator import AnswerQualityEvaluator

class TestAnswerQualityEvaluator(unittest.TestCase):

    def setUp(self):
        # Initialize evaluator with default embedding model
        self.evaluator = AnswerQualityEvaluator()

    @patch("app.rag_evaluator.answer_quality.evaluator.SentenceTransformer")
    def test_embedding_similarity(self, mock_embedder):
        # Mock embeddings
        mock_model = MagicMock()
        mock_model.encode.side_effect = [
            [0.1, 0.2, 0.3],  # generated answer embedding
            [0.1, 0.2, 0.3]   # reference answer embedding
        ]
        mock_embedder.return_value = mock_model

        score = self.evaluator.embedding_similarity("Generated answer", "Reference answer")
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    @patch("app.rag_evaluator.answer_quality.evaluator.SentenceTransformer")
    @patch("app.rag_evaluator.answer_quality.evaluator.Groq")
    def test_initialization_is_lazy(self, mock_groq, mock_embedder):
        AnswerQualityEvaluator()

        mock_embedder.assert_not_called()
        mock_groq.assert_not_called()

    @patch("app.rag_evaluator.answer_quality.evaluator.Groq")
    def test_llm_judge(self, mock_groq):
        # Mock Groq client response
        mock_message = MagicMock()
        mock_message.content = '{"Faithfulness":1,"Relevance":0.8,"Completeness":0.8,"Clarity":1}'
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        mock_groq.return_value = mock_client    

        result = self.evaluator.llm_judge("What is AI?", "AI is machine learning", "AI is ML")
        
        for metric in ["Faithfulness", "Relevance", "Completeness", "Clarity"]:
            self.assertIn(metric, result)
            # Verify all scores are floats and within valid range
            self.assertIsInstance(result[metric], float)
            self.assertGreaterEqual(result[metric], 0.0)
            self.assertLessEqual(result[metric], 1.0)

    def test_evaluate_answer_with_reference(self):
        # Patch methods to avoid real API calls
        with patch.object(self.evaluator, "embedding_similarity", return_value=0.95), \
             patch.object(self.evaluator, "llm_judge", return_value={"Faithfulness":1.0,"Relevance":0.8,"Completeness":0.8,"Clarity":1.0}):
            
            results = self.evaluator.evaluate_answer(
                query="What is AI?",
                context="AI is machine learning",
                generated_answer="AI is ML",
                reference_answer="Artificial Intelligence is ML"
            )
            # self.assertIn("embedding_similarity", results)
            # self.assertIn("llm_scores", results)
            
            # Verify all LLM scores are floats in valid range
            for metric in ["Faithfulness", "Relevance", "Completeness", "Clarity"]:
                # self.assertIn(metric, results["llm_scores"])
                # self.assertIsInstance(results["llm_scores"][metric], float)
                metric = metric.lower()
                self.assertIn(metric, results)
                self.assertIsInstance(results[metric], float)

    @patch("app.rag_evaluator.answer_quality.evaluator.Groq")
    def test_llm_judge_with_out_of_range_values(self, mock_groq):
        """Test that out-of-range values are clamped to valid range."""
        # Return values outside 0-1 range
        mock_message = MagicMock()
        mock_message.content = '{"Faithfulness":1.5,"Relevance":-0.2,"Completeness":0.8,"Clarity":1}'
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        mock_groq.return_value = mock_client
        
        result = self.evaluator.llm_judge("What is AI?", "AI is machine learning", "AI is ML")
        
        # Verify clamping
        self.assertEqual(result["Faithfulness"], 1.0)  # Clamped from 1.5
        self.assertEqual(result["Relevance"], 0.0)     # Clamped from -0.2
        self.assertEqual(result["Completeness"], 0.8)  # Within range
        self.assertIsInstance(result["Clarity"], float)

    @patch("app.rag_evaluator.answer_quality.evaluator.Groq")
    def test_llm_judge_with_markdown_wrapped_json(self, mock_groq):
        """Test parsing when the model wraps JSON in markdown fences."""
        mock_message = MagicMock()
        mock_message.content = '```json\n{"Faithfulness": 1.0, "Relevance": 0.8, "Completeness": 0.8, "Clarity": 1.0}\n```'

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        mock_groq.return_value = mock_client

        result = self.evaluator.llm_judge("What is AI?", "AI is machine learning", "AI is ML")

        for metric in ["Faithfulness", "Relevance", "Completeness", "Clarity"]:
            self.assertIn(metric, result)
            self.assertIsInstance(result[metric], float)
            self.assertGreaterEqual(result[metric], 0.0)
            self.assertLessEqual(result[metric], 1.0)

    @patch("app.rag_evaluator.answer_quality.evaluator.Groq")
    def test_llm_judge_with_invalid_json(self, mock_groq):
        """Test fallback when LLM returns invalid JSON."""
        # Return invalid JSON
        mock_message = MagicMock()
        mock_message.content = 'This is not JSON'
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        mock_groq.return_value = mock_client
        
        result = self.evaluator.llm_judge("What is AI?", "AI is machine learning", "AI is ML")
        
        # Should return default neutral scores (0.5)
        for metric in ["Faithfulness", "Relevance", "Completeness", "Clarity"]:
            self.assertIn(metric, result)
            self.assertIsInstance(result[metric], float)
            self.assertEqual(result[metric], 0.5)

if __name__ == "__main__":
    unittest.main()