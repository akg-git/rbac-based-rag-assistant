import logging
import os
from typing import Any, Dict, List
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

logger = logging.getLogger(__name__)

# history-aware query contextualization
CONTEXTUALIZE_Q_SYSTEM_PROMPT = """You are an AI assistant tasked with contextualizing follow-up questions.
Given a conversation history between a user and an AI assistant, and the latest user question which might reference context in the history (such as pronouns 'it', 'they', 'their', 'that', or implicit comparisons), formulate a standalone question that can be understood completely WITHOUT the chat history.

Rules:
1. Do NOT answer the question.
2. Do NOT add any extra information, pleasantries, or preamble.
3. If the question is already standalone or self-contained, return it EXACTLY as is.
4. Only rephrase to resolve pronouns and implicit references based on the provided conversation history.
5. Return ONLY the reformulated question as a single plain text string.
"""

def get_groq_client() -> Groq | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        logger.warning(f"[CONTEXT_MEMORY] Failed to initialize Groq client: {e}")
        return None


def contextualize_question_with_history(
    question: str,
    history: List[Dict[str, Any]] | None,
    max_history_turns: int = 5,
) -> str:
    """
    Reformulates a user question using recent chat history into a standalone query.
    If history is empty or already standalone, returns original question.
    """
    clean_question = question.strip() if question else ""
    if not clean_question:
        return clean_question

    if not history or not isinstance(history, list) or len(history) == 0:
        return clean_question

    # Filter and format recent turns
    valid_turns = []
    for msg in history[-max_history_turns:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role and content:
            valid_turns.append(f"{role.capitalize()}: {content}")

    if not valid_turns:
        return clean_question

    formatted_history = "\n".join(valid_turns)
    user_prompt = f"Chat History:\n{formatted_history}\n\nLatest Question: {clean_question}\nStandalone Question:"

    client = get_groq_client()
    if not client:
        return clean_question

    try:
        model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": CONTEXTUALIZE_Q_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=256,
        )

        raw_response = response.choices[0].message.content if response.choices else None
        reformulated = raw_response.strip() if raw_response else ""
        if reformulated and len(reformulated) > 3:
            logger.info(f"[CONTEXT_MEMORY] Original: '{clean_question}' -> Contextualized: '{reformulated}'")
            return reformulated
        return clean_question

    except Exception as e:
        logger.warning(f"[CONTEXT_MEMORY] Contextualization failed, fallback to original question: {e}")
        return clean_question
