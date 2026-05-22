from app.utils.rag_module import get_rag_chain, vectorstore
from concurrent.futures import ThreadPoolExecutor
import asyncio
import logging

logger = logging.getLogger(__name__)

async def rag_handler(question: str, role: str, cohere_api_key: str = None) -> dict:
    """
    Production-ready RAG handler with proper error handling and validation.
    Uses sync chain in executor to prevent blocking event loop.
    """
    
    try:
        # Validate inputs
        if not question or not question.strip():
            return {"answer": "Error: Question cannot be empty.", "error": True}
        
        if not role:
            return {"answer": "Error: User role is required.", "error": True}
        
        # Check if vectorstore has documents
        doc_count = len(vectorstore.get().get("documents", []))
        if doc_count == 0:
            return {
                "answer": "No documents available in the knowledge base. Please upload documents first.",
                "error": True
            }
        
        logger.info(f"[RAG] Processing question for role={role}: {question[:50]}...")
        
        # Get the chain (synchronous)
        chain = get_rag_chain(user_role=role, cohere_api_key=cohere_api_key)
        
        # Run sync chain in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                lambda: chain.invoke({"input": question})
            )
        
        # Validate response structure
        if not result or "answer" not in result:
            logger.error(f"Invalid chain response: {result}")
            return {"answer": "Error: Invalid response from RAG chain.", "error": True}
        
        answer = result.get("answer", "").strip()
        if not answer:
            logger.warning(f"Empty answer returned for role={role}")
            return {"answer": "No relevant information found for your query.", "error": True}
        
        # Build response with context metadata
        response = {
            "answer": answer,
            "error": False
        }
        
        # Include source documents if available
        if "context" in result and result["context"]:
            sources = []
            for doc in result.get("context", []):
                source = doc.metadata.get("source", "Unknown")
                if source not in sources:
                    sources.append(source)
            if sources:
                response["sources"] = sources
        
        logger.info(f"[RAG] Successfully processed query")
        return response
        
    except Exception as e:
        logger.error(f"[RAG] Error in rag_handler: {type(e).__name__}: {str(e)}", exc_info=True)
        return {
            "answer": "Error processing your query. Please try again or rephrase your question.",
            "error": True
        }
