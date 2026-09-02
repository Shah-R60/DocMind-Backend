import os
import shutil
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.document import Document
from app.schemas.document import DocumentResponse
from app.core.config import settings
from app.rag.document_processor import process_pdf
from app.rag.vector_store import add_documents_to_store, delete_document_from_store

router = APIRouter()

def background_process_pdf(file_path: str, document_id: str, db: Session):
    try:
        chunks = process_pdf(file_path)
        add_documents_to_store(chunks, document_id)
        
        # Update status to ready
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.upload_status = "ready"
            db.commit()
    except Exception as e:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.upload_status = "error"
            db.commit()

@router.post("/", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Create document record
    doc_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    new_doc = Document(
        id=doc_id,
        user_id=current_user.id,
        filename=file.filename,
        file_path=file_path,
        upload_status="processing"
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # Process PDF in background
    background_tasks.add_task(background_process_pdf, file_path, doc_id, db)

    return new_doc

@router.get("/", response_model=list[DocumentResponse])
def get_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Document).filter(Document.user_id == current_user.id).all()

@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Delete from DB
    db.delete(doc)
    db.commit()
    
    # Delete file
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
        
    # Delete from vector store
    delete_document_from_store(document_id)
    
    return {"status": "success"}
