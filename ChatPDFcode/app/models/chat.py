"""
Chat Models
Pydantic schemas for chat interactions
"""

from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Role of a message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class DocumentReference(BaseModel):
    """Reference to a source document."""
    document_id: str
    document_name: str
    page_number: int
    section: Optional[str] = None
    excerpt: Optional[str] = None
    relevance_score: Optional[float] = None


class ChatMessage(BaseModel):
    """Request model for sending a chat message."""
    session_id: str = Field(..., description="Session ID")
    message: str = Field(..., min_length=1, max_length=4000, description="User's question")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "message": "¿Cuáles son los principales hallazgos del estudio?"
            }
        }


class TokenUsage(BaseModel):
    """Token usage statistics for an API call."""
    provider: str = Field(..., description="API provider (anthropic/openai)")
    model: str = Field(..., description="Model used")
    input_tokens: int = Field(0, description="Input tokens used")
    output_tokens: int = Field(0, description="Output tokens generated")
    total_tokens: int = Field(0, description="Total tokens used")


class ChatResponse(BaseModel):
    """Response model for chat messages."""
    session_id: str
    answer: str = Field(..., description="Generated answer from the chatbot")
    references: List[DocumentReference] = Field(
        default=[],
        description="Document references supporting the answer"
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score of the answer"
    )
    timestamp: str
    token_usage: Optional[TokenUsage] = Field(
        None,
        description="Token usage statistics"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "answer": "Los principales hallazgos del estudio incluyen...",
                "references": [
                    {
                        "document_id": "doc-001",
                        "document_name": "paper.pdf",
                        "page_number": 5,
                        "section": "Resultados",
                        "excerpt": "Los resultados muestran..."
                    }
                ],
                "confidence": 0.95,
                "timestamp": "2024-01-15T10:35:00Z",
                "token_usage": {
                    "provider": "anthropic",
                    "model": "claude-3-haiku",
                    "input_tokens": 1500,
                    "output_tokens": 300,
                    "total_tokens": 1800
                }
            }
        }


class HistoryMessage(BaseModel):
    """A message in the chat history."""
    role: MessageRole
    content: str
    timestamp: str
    references: Optional[List[DocumentReference]] = None


class ChatHistory(BaseModel):
    """Chat history for a session."""
    session_id: str
    messages: List[HistoryMessage]
    total_messages: int
