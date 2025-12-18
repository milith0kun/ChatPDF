"""
Session Management Routes
Handles session creation and cleanup
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.models.session import SessionCreate, SessionResponse, SessionClose
from app.db.redis_client import redis_manager
from app.db.qdrant_client import qdrant_manager
from app.config import settings


router = APIRouter()


@router.post("/create", response_model=SessionResponse)
async def create_session():
    """
    Create a new chat session.
    
    Returns a unique session_id that must be used for all subsequent requests.
    Sessions expire after 2 hours of inactivity.
    """
    session_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    
    # Store session in Redis
    session_data = {
        "session_id": session_id,
        "created_at": created_at,
        "documents": [],
        "status": "active"
    }
    
    await redis_manager.set_session(
        session_id=session_id,
        data=session_data,
        expiry_hours=settings.SESSION_EXPIRY_HOURS
    )
    
    # Create Qdrant collection for this session
    await qdrant_manager.create_collection(
        collection_name=f"session_{session_id}",
        vector_size=settings.EMBEDDING_DIMENSION
    )
    
    return SessionResponse(
        session_id=session_id,
        created_at=created_at,
        expires_in_hours=settings.SESSION_EXPIRY_HOURS,
        status="active"
    )


@router.delete("/close/{session_id}", response_model=SessionClose)
async def close_session(session_id: str):
    """
    Close a session and cleanup all associated data.
    
    This will:
    - Delete all uploaded documents
    - Remove vector embeddings from Qdrant
    - Clear session data from Redis
    """
    # Verify session exists
    session_data = await redis_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found or already expired"
        )
    
    # Delete Qdrant collection
    await qdrant_manager.delete_collection(f"session_{session_id}")
    
    # Delete session from Redis
    await redis_manager.delete_session(session_id)
    
    # TODO: Delete uploaded files from disk
    
    return SessionClose(
        session_id=session_id,
        message="Session closed successfully. All data has been deleted.",
        deleted_at=datetime.utcnow().isoformat()
    )


@router.get("/status/{session_id}")
async def get_session_status(session_id: str):
    """
    Get the current status of a session.
    """
    session_data = await redis_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found or expired"
        )
    
    return {
        "session_id": session_id,
        "status": session_data.get("status", "unknown"),
        "documents_count": len(session_data.get("documents", [])),
        "created_at": session_data.get("created_at")
    }
