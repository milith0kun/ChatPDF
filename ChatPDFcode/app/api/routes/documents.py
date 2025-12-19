"""
Document Upload and Processing Routes
Handles PDF upload and async processing status
"""

import os
import uuid
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks

from app.models.document import (
    DocumentUploadResponse,
    DocumentStatus,
    ProcessingStatus
)
from app.db.redis_client import redis_manager
from app.workers.tasks import process_document_task
from app.config import settings
from app.utils.file_handler import save_uploaded_file, validate_pdf


router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    session_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    Upload one or more PDF documents for processing.
    
    - Maximum file size: 50MB per file
    - Maximum files per session: 20
    - Accepted format: PDF only
    
    Returns a job_id to track processing status.
    """
    # Verify session exists
    session_data = await redis_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found. Create a session first."
        )
    
    # Validate file count
    existing_docs = session_data.get("documents", [])
    if len(existing_docs) + len(files) > settings.MAX_FILES_PER_SESSION:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.MAX_FILES_PER_SESSION} files allowed per session"
        )
    
    # Validate and save files
    uploaded_files = []
    job_id = str(uuid.uuid4())
    
    for file in files:
        # Validate PDF
        validation_result = await validate_pdf(file)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file {file.filename}: {validation_result['error']}"
            )
        
        # Save file
        file_path = await save_uploaded_file(
            file=file,
            session_id=session_id,
            upload_dir=settings.UPLOAD_DIR
        )
        
        document_id = str(uuid.uuid4())
        uploaded_files.append({
            "document_id": document_id,
            "filename": file.filename,
            "file_path": file_path,
            "status": "pending"
        })
    
    # Store job info in Redis
    job_data = {
        "job_id": job_id,
        "session_id": session_id,
        "documents": uploaded_files,
        "status": "processing",
        "progress": 0,
        "total_documents": len(uploaded_files)
    }
    await redis_manager.set_job(job_id, job_data)
    
    # Update session with new documents
    session_data["documents"].extend([d["document_id"] for d in uploaded_files])
    await redis_manager.set_session(session_id, session_data)
    
    # Queue processing tasks for each document using threading (simpler for dev)
    import threading
    from app.workers.tasks import process_document_sync
    for doc in uploaded_files:
        thread = threading.Thread(
            target=process_document_sync,
            kwargs={
                "job_id": job_id,
                "document_id": doc["document_id"],
                "file_path": doc["file_path"],
                "session_id": session_id
            }
        )
        thread.start()
    
    return DocumentUploadResponse(
        job_id=job_id,
        session_id=session_id,
        documents=[
            DocumentStatus(
                document_id=d["document_id"],
                filename=d["filename"],
                status="pending"
            )
            for d in uploaded_files
        ],
        message=f"Processing {len(uploaded_files)} document(s). Use job_id to check status."
    )


@router.get("/status/{job_id}", response_model=ProcessingStatus)
async def get_processing_status(job_id: str):
    """
    Get the processing status of an upload job.
    
    Status values:
    - pending: Waiting to be processed
    - processing: Currently being processed
    - completed: Processing finished successfully
    - failed: Processing failed with error
    """
    job_data = await redis_manager.get_job(job_id)
    if not job_data:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    # Calculate overall progress
    total = job_data.get("total_documents", 1)
    completed = sum(1 for d in job_data.get("documents", []) 
                   if d.get("status") == "completed")
    progress = int((completed / total) * 100) if total > 0 else 0
    
    # Determine overall status
    statuses = [d.get("status") for d in job_data.get("documents", [])]
    if all(s == "completed" for s in statuses):
        overall_status = "completed"
    elif any(s == "failed" for s in statuses):
        overall_status = "failed"
    elif any(s == "processing" for s in statuses):
        overall_status = "processing"
    else:
        overall_status = "pending"
    
    return ProcessingStatus(
        job_id=job_id,
        status=overall_status,
        progress=progress,
        documents=[
            DocumentStatus(
                document_id=d["document_id"],
                filename=d["filename"],
                status=d["status"],
                error=d.get("error")
            )
            for d in job_data.get("documents", [])
        ],
        message=f"Processing {progress}% complete"
    )


@router.get("/list/{session_id}")
async def list_session_documents(session_id: str):
    """
    List all documents uploaded to a session.
    """
    session_data = await redis_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    return {
        "session_id": session_id,
        "documents": session_data.get("documents", []),
        "count": len(session_data.get("documents", []))
    }
