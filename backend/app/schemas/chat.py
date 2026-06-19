from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    pregunta: str
    documento_ids: Optional[List[int]] = None
    top_k: Optional[int] = 3

class ChatResponse(BaseModel):
    respuesta: str
    fuentes: List[str] = []
    chunks: List[Dict[str, Any]] = []
    transcripcion: Optional[str] = None

class AudioChatRequest(BaseModel):
    documento_ids: Optional[List[int]] = None
    top_k: Optional[int] = 3