from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Dict[str, Any]]] = []