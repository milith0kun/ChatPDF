"""
Session Models
Pydantic schemas for session management
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """Request model for creating a session."""
    pass  # No input required


class SessionResponse(BaseModel):
    """Response model for session creation."""
    session_id: str = Field(..., description="Unique session identifier")
    created_at: str = Field(..., description="ISO timestamp of creation")
    expires_in_hours: int = Field(..., description="Hours until session expires")
    status: str = Field(..., description="Session status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2024-01-15T10:30:00Z",
                "expires_in_hours": 2,
                "status": "active"
            }
        }


class SessionClose(BaseModel):
    """Response model for closing a session."""
    session_id: str
    message: str
    deleted_at: str


class SessionData(BaseModel):
    """Internal session data structure."""
    session_id: str
    created_at: str
    documents: List[str] = []
    status: str = "active"
