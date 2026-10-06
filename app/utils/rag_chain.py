from app.utils.rag_module import get_rag_chain, vectorstore
from app.utils.audit_events import emit_audit_event
from concurrent.futures import ThreadPoolExecutor
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


def _emit_rag_audit_event(
    *,
    username: str,
    role: str,
    request_id: str,
    correlation_id: str,
    action: str,
    resource: str,
    authorization_decision: str,
    result: str,
    outcome_status: str,
    source_count: int = 0,
) -> None:
    emit_audit_event(
        user_id=username,
        role=role,
        action=action,
        resource=resource,
        authorization_decision=authorization_decision,
        result=result,
        outcome_status=outcome_status,
        request_id=request_id,
        correlation_id=correlation_id,
        query_mode="rag",
        source_count=source_count,
    )


async def rag_handler(
    question: str,
    role: str,
    cohere_api_key: str = None,
    username: str = "unknown",
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """
    Production-ready RAG handler with proper error handling and validation.
    Uses sync chain in executor to prevent blocking event loop.
    """
    request_id = request_id or str(uuid.uuid4())
    correlation_id = correlation_id or request_id

    try:
        # Validate inputs
        if not question or not question.strip():
            _emit_rag_audit_event(
                username=username,
                role=role,
                request_id=request_id,
                correlation_id=correlation_id,
                action="chat.ask",
                resource="document.read",
                authorization_decision="denied",
                result="failure",
                outcome_status="failed",
            )
            return {"answer": "Error: Question cannot be empty.", "error": True}

        if not role:
            _emit_rag_audit_event(
                username=username,
                role=role,
                request_id=request_id,
                correlation_id=correlation_id,
                action="chat.ask",
                resource="document.read",
                authorization_decision="denied",
                result="failure",
                outcome_status="denied",
            )
            return {"answer": "Error: User role is required.", "error": True}
        
        # Check if vectorstore has documents
        doc_count = len(vectorstore.get().get("documents", []))
        if doc_count == 0:
            _emit_rag_audit_event(
                username=username,
                role=role,
                request_id=request_id,
                correlation_id=correlation_id,
                action="chat.ask",
                resource="document.read",
                authorization_decision="allowed",
                result="failure",
                outcome_status="failed",
            )
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

        _emit_rag_audit_event(
            username=username,
            role=role,
            request_id=request_id,
            correlation_id=correlation_id,
            action="chat.ask",
            resource="document.read",
            authorization_decision="allowed",
            result="success",
            outcome_status="authorized",
            source_count=len(response.get("sources", [])),
        )
        logger.info(f"[RAG] Successfully processed query")
        return response
        
    except Exception as e:
        _emit_rag_audit_event(
            username=username,
            role=role,
            request_id=request_id,
            correlation_id=correlation_id,
            action="chat.ask",
            resource="document.read",
            authorization_decision="allowed",
            result="failure",
            outcome_status="failed",
        )
        logger.error(f"[RAG] Error in rag_handler: {type(e).__name__}: {str(e)}", exc_info=True)
        return {
            "answer": "Error processing your query. Please try again or rephrase your question.",
            "error": True
        }
