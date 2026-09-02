from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.chat import Chat, DocumentChat, Message
from app.models.document import Document
from app.schemas.chat import ChatCreate, ChatResponse, ChatDetailResponse, MessageResponse
from app.rag.chain import stream_rag_response
from pydantic import BaseModel

router = APIRouter()

class ChatMessageInput(BaseModel):
    message: str

@router.post("/", response_model=ChatResponse)
def create_chat(chat_in: ChatCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify all documents belong to user
    docs = db.query(Document).filter(Document.id.in_(chat_in.document_ids), Document.user_id == current_user.id).all()
    if len(docs) != len(chat_in.document_ids):
        raise HTTPException(status_code=400, detail="Some documents were not found or don't belong to the user")
        
    title = docs[0].filename if docs else "New Chat"
    if len(docs) > 1:
        title = f"{title} + {len(docs)-1} more"

    chat = Chat(user_id=current_user.id, title=title)
    db.add(chat)
    db.commit()
    db.refresh(chat)

    for doc_id in chat_in.document_ids:
        doc_chat = DocumentChat(chat_id=chat.id, document_id=doc_id)
        db.add(doc_chat)
    db.commit()
    
    return chat

@router.get("/", response_model=list[ChatResponse])
def get_chats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Chat).filter(Chat.user_id == current_user.id).order_by(Chat.created_at.desc()).all()

@router.get("/{chat_id}", response_model=ChatDetailResponse)
def get_chat(chat_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat

@router.post("/{chat_id}/message")
async def send_message(
    chat_id: str, 
    input_data: ChatMessageInput, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    # Save user message
    user_message = Message(chat_id=chat.id, role="user", content=input_data.message)
    db.add(user_message)
    db.commit()
    
    # Get document IDs for this chat
    doc_chats = db.query(DocumentChat).filter(DocumentChat.chat_id == chat.id).all()
    doc_ids = [dc.document_id for dc in doc_chats]
    
    # Get chat history (last 10 messages)
    history = db.query(Message).filter(Message.chat_id == chat.id).order_by(Message.created_at.asc()).limit(10).all()
    
    # We will let the frontend handle the streaming, and then the frontend must call a separate endpoint to save the final AI message, or we could save it after stream completes using background task.
    # For a production app with streaming, usually the final message is saved to DB via a separate call or background task.
    
    return StreamingResponse(
        stream_rag_response(input_data.message, history, doc_ids),
        media_type="text/event-stream"
    )

@router.post("/{chat_id}/save_message")
def save_ai_message(
    chat_id: str, 
    content: str,
    sources: str = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    ai_message = Message(chat_id=chat.id, role="ai", content=content, sources=sources)
    db.add(ai_message)
    db.commit()
    return {"status": "success"}

@router.post("/messages/{message_id}/feedback")
def set_feedback(
    message_id: str, 
    helpful: bool,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    message = db.query(Message).join(Chat).filter(Message.id == message_id, Chat.user_id == current_user.id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
        
    message.feedback = helpful
    db.commit()
    return {"status": "success"}
