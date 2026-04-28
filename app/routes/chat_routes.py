# Chat Routes

from fastapi import APIRouter, Depends
from app.authentication.auth import authenticate
from fastapi import Depends
from app.main import ChatRequest
from app.utils.rag_module import detect_query_mode
from app.utils.sql_query import handle_sql_query
from app.utils.rag_chain import rag_handler

router = APIRouter()

# Import ChatRequest from main module
from app.main import ChatRequest

@router.post("/chat/")
async def chat_endpoint(request: ChatRequest, user = Depends(authenticate)):
    # Here you would implement the logic to handle the chat request,

    role = user["role"]
    username = user["username"]
    question = request.question

    # Detect Mode for query processing: SQL or RAG based on question and user role
    mode = detect_query_mode(question)
    print(f"Detected query mode: {mode}")

    result = {}
    fallback_used = False

    # Route to appropriate handler
    if mode == "SQL":
        # Call SQL query handler (to be implemented)
         
        try:
            result = handle_sql_query(question, role, username, return_sql=True)

            if result.get("error") or not result.get("answer", "").strip():
                raise ValueError("SQL query blocked or failed")


        except Exception as e:
            print(f"[SQL Fallback Triggered] Error: {e}")
            result = await rag_handler(question, role)
            fallback_used = True
            mode = "SQL → fallback to RAG"
    else:
        # Call RAG handler (to be implemented)
        result = await rag_handler(question, role)

    response = {
        "user": username,
        "role": role,
        "mode": mode,
        "result": result,
        "fallback": fallback_used,
        "answer": result["answer"],
        **({"sql": result["sql"]} if "sql" in result else {})
    }

    return response