"""
Chat Routes
Handles conversation with the RAG system
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.chat import (
    ChatMessage,
    ChatResponse,
    ChatHistory,
    TokenUsage
)
from app.db.redis_client import redis_manager
from app.core.rag import RAGService


router = APIRouter()
rag_service = RAGService()


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatMessage):
    """
    Send a message to the chatbot and receive a response.
    
    The system will:
    1. Search for relevant content in uploaded documents
    2. Build context from most relevant chunks
    3. Generate a response using Claude (Anthropic)
    4. Include document references with page numbers
    
    If no relevant information is found, the system will
    explicitly indicate that the query cannot be answered.
    """
    session_id = request.session_id
    query = request.message
    
    # Verify session exists
    session_data = await redis_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    # Check if documents are loaded
    if not session_data.get("documents"):
        raise HTTPException(
            status_code=400,
            detail="No documents uploaded. Please upload PDFs before asking questions."
        )
    
    # Get chat history for context
    chat_history = await redis_manager.get_chat_history(session_id)
    
    try:
        # Execute RAG pipeline
        response = await rag_service.generate_response(
            query=query,
            session_id=session_id,
            chat_history=chat_history
        )
        
        # Save message and response to history
        timestamp = datetime.utcnow().isoformat()
        
        await redis_manager.add_chat_message(
            session_id=session_id,
            message={
                "role": "user",
                "content": query,
                "timestamp": timestamp
            }
        )
        
        await redis_manager.add_chat_message(
            session_id=session_id,
            message={
                "role": "assistant",
                "content": response["answer"],
                "references": response.get("references", []),
                "timestamp": timestamp
            }
        )
        
        # Build token usage
        token_usage = None
        if response.get("token_usage"):
            token_usage = TokenUsage(**response["token_usage"])
        
        return ChatResponse(
            session_id=session_id,
            answer=response["answer"],
            references=response.get("references", []),
            confidence=response.get("confidence"),
            timestamp=timestamp,
            token_usage=token_usage
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating response: {str(e)}"
        )


@router.post("/message/stream")
async def send_message_stream(request: ChatMessage):
    """
    Send a message and receive a streaming response.
    
    Uses Server-Sent Events (SSE) to stream the response
    as it's being generated.
    """
    session_id = request.session_id
    query = request.message
    
    # Verify session
    session_data = await redis_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    if not session_data.get("documents"):
        raise HTTPException(
            status_code=400,
            detail="No documents uploaded"
        )
    
    chat_history = await redis_manager.get_chat_history(session_id)
    
    async def generate():
        async for chunk in rag_service.generate_response_stream(
            query=query,
            session_id=session_id,
            chat_history=chat_history
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.get("/history/{session_id}", response_model=ChatHistory)
async def get_chat_history(session_id: str, limit: Optional[int] = 50):
    """
    Retrieve the chat history for a session.
    
    Returns the most recent messages up to the specified limit.
    """
    session_data = await redis_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    history = await redis_manager.get_chat_history(session_id, limit=limit)
    
    return ChatHistory(
        session_id=session_id,
        messages=history,
        total_messages=len(history)
    )


@router.delete("/history/{session_id}")
async def clear_chat_history(session_id: str):
    """
    Clear the chat history for a session while keeping documents.
    """
    session_data = await redis_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    await redis_manager.clear_chat_history(session_id)
    
    return {
        "session_id": session_id,
        "message": "Chat history cleared successfully"
    }
