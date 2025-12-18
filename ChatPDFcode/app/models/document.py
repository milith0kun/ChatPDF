"""
Document Models
Pydantic schemas for document upload and processing
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class DocumentStatus(BaseModel):
    """Status of a single document."""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status: pending, processing, completed, failed")
    error: Optional[str] = Field(None, description="Error message if failed")
    pages: Optional[int] = Field(None, description="Number of pages (after processing)")
    chunks: Optional[int] = Field(None, description="Number of chunks created")


class DocumentUploadResponse(BaseModel):
    """Response after uploading documents."""
    job_id: str = Field(..., description="Job ID to track processing")
    session_id: str = Field(..., description="Associated session ID")
    documents: List[DocumentStatus] = Field(..., description="List of uploaded documents")
    message: str = Field(..., description="Status message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job-123456",
                "session_id": "session-789",
                "documents": [
                    {
                        "document_id": "doc-001",
                        "filename": "paper.pdf",
                        "status": "pending"
                    }
                ],
                "message": "Processing 1 document(s)"
            }
        }


class ProcessingStatus(BaseModel):
    """Overall processing status for a job."""
    job_id: str
    status: str = Field(..., description="Overall status: pending, processing, completed, failed")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    documents: List[DocumentStatus]
    message: str


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""
    document_id: str
    document_name: str
    page_number: int
    section_title: Optional[str] = None
    chunk_type: str = "text"  # text, table, image_description
    position_in_document: int


class DocumentChunk(BaseModel):
    """A chunk of document content with metadata."""
    chunk_id: str
    content: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None
