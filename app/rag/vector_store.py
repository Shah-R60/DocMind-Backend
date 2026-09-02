import os
from langchain_community.vectorstores import Chroma
from langchain_mistralai.embeddings import MistralAIEmbeddings
from app.core.config import settings

def get_embeddings():
    return MistralAIEmbeddings(mistral_api_key=settings.MISTRAL_API_KEY)

def get_vector_store():
    embeddings = get_embeddings()
    return Chroma(
        collection_name="docmind_collection",
        embedding_function=embeddings,
        persist_directory=settings.VECTOR_STORE_DIR
    )

def add_documents_to_store(chunks, document_id: str):
    # Add document_id to metadata for filtering
    for chunk in chunks:
        chunk.metadata["document_id"] = document_id
        
    vectorstore = get_vector_store()
    vectorstore.add_documents(chunks)
    vectorstore.persist()

def delete_document_from_store(document_id: str):
    vectorstore = get_vector_store()
    # Chroma DB allows deleting by where clause
    collection = vectorstore._collection
    collection.delete(where={"document_id": document_id})
