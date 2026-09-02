from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[str] = None
    feedback: Optional[bool] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ChatCreate(BaseModel):
    document_ids: List[str]

class ChatResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatDetailResponse(ChatResponse):
    messages: List[MessageResponse]
