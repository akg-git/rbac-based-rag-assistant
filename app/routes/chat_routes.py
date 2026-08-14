# Chat Routes

from fastapi import APIRouter, Depends, HTTPException
from app.authentication.auth import authenticate
from app.models.request_model import ChatRequest
from app.utils.query_classifier import detect_query_mode
from app.utils.sql_query import handle_sql_query
from app.utils.rag_chain import rag_handler
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(request: ChatRequest, user = Depends(authenticate)):
    """
    Routes to SQL or RAG based on query classification with fallback strategy.
    """
    
    try:
        role = user["role"]
        username = user["username"]
        question = request.question.strip() if request.question else ""
        
        # Validate input
        if not question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        logger.info(f"[CHAT] User={username}, Role={role}, Question={question[:50]}...")
        
        # Detect query mode
        mode = detect_query_mode(question)
        logger.info(f"[CHAT] Detected mode: {mode}")
        
        result = {}
        fallback_used = False
        sql_query = None
        
        # Route to appropriate handler
        if mode == "SQL":
            try:
                result = handle_sql_query(question, role, username, return_sql=True)
                
                # Check if SQL execution failed
                if result.get("error"):
                    if result.get("error_type") == "authorization":
                        raise HTTPException(
                            status_code=403,
                            detail="You are not authorized to access the requested data.",
                        )
                    logger.warning(f"[CHAT] SQL query failed: {result.get('answer')}")
                    raise ValueError(result.get("answer", "SQL query execution failed"))
                
                # Check if answer is empty even without error
                if not result.get("answer", "").strip():
                    logger.warning(f"[CHAT] SQL returned empty result")
                    raise ValueError("SQL query returned no results")
                
                sql_query = result.get("sql")
                logger.info(f"[CHAT] SQL mode succeeded")
                
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"[CHAT] SQL fallback triggered: {str(e)}")
                # Fallback to RAG
                result = await rag_handler(question, role)
                fallback_used = True
                mode = "SQL → RAG Fallback"
        else:
            # Direct RAG mode
            result = await rag_handler(question, role)
        
        # Validate result structure
        if not result or "answer" not in result:
            logger.error(f"[CHAT] Invalid result structure: {result}")
            raise HTTPException(status_code=500, detail="Invalid response from backend")
        
        # Handle error from handler
        if result.get("error"):
            logger.warning(f"[CHAT] Handler returned error: {result.get('answer')}")
            raise HTTPException(status_code=400, detail=result.get("answer"))
        
        # Build response
        response = {
            "user": username,
            "role": role,
            "mode": mode,
            "answer": result["answer"],
            "fallback": fallback_used
        }
        
        # Add SQL if available
        if sql_query:
            response["sql"] = sql_query
        
        # Add sources if available
        if "sources" in result:
            response["sources"] = result["sources"]
        
        logger.info(f"[CHAT] Successfully processed request")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CHAT] Unexpected error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again.")