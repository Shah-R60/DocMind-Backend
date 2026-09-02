from typing import List, AsyncGenerator
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_mistralai.chat_models import ChatMistralAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from app.rag.vector_store import get_vector_store
from app.core.config import settings

def get_llm(streaming=False):
    return ChatMistralAI(
        mistral_api_key=settings.MISTRAL_API_KEY,
        model="mistral-small-latest",
        streaming=streaming
    )

def get_retriever(document_ids: List[str]):
    vectorstore = get_vector_store()
    # Filter by selected document IDs
    search_kwargs = {"k": 5}
    if document_ids:
        # Chroma expects a specific format for IN queries, usually $in
        search_kwargs["filter"] = {"document_id": {"$in": document_ids}}
    
    # Using MMR for diversity
    return vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs=search_kwargs
    )

def get_rag_chain(document_ids: List[str], streaming=False):
    llm = get_llm(streaming=streaming)
    retriever = get_retriever(document_ids)

    # Prompt to contextualize the user's question based on history
    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, "
        "just reformulate it if needed and otherwise return it as is."
    )
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    # Prompt for QA
    system_prompt = (
        "You are an assistant for question-answering tasks. "
        "Use the following pieces of retrieved context to answer the question. "
        "If you don't know the answer, just say that you don't know based on the provided documents. "
        "Use three sentences maximum and keep the answer concise.\n\n"
        "Context: {context}"
    )
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    return rag_chain

async def stream_rag_response(message: str, chat_history: List, document_ids: List[str]) -> AsyncGenerator[str, None]:
    chain = get_rag_chain(document_ids, streaming=True)
    
    # Langchain history format
    formatted_history = []
    for msg in chat_history:
        if msg.role == 'user':
            formatted_history.append(HumanMessage(content=msg.content))
        else:
            formatted_history.append(AIMessage(content=msg.content))
            
    # Stream the response
    # Yielding JSON chunks that the frontend can parse
    import json
    
    async for chunk in chain.astream({"input": message, "chat_history": formatted_history}):
        if "answer" in chunk:
            yield f"data: {json.dumps({'content': chunk['answer'], 'type': 'content'})}\n\n"
        if "context" in chunk:
            # Send sources at the beginning
            sources = []
            for doc in chunk["context"]:
                sources.append({
                    "source": doc.metadata.get("source", "Unknown"),
                    "page": doc.metadata.get("page", "Unknown")
                })
            # Deduplicate sources
            unique_sources = [dict(t) for t in {tuple(d.items()) for d in sources}]
            yield f"data: {json.dumps({'sources': unique_sources, 'type': 'sources'})}\n\n"
            
    yield "data: [DONE]\n\n"
