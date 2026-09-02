from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DocumentResponse(BaseModel):
    id: str
    filename: str
    upload_status: str
    created_at: datetime

    class Config:
        from_attributes = True
