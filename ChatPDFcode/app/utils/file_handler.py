"""
File Handler
Utilities for handling file uploads and storage
"""

import os
import uuid
import aiofiles
from typing import Dict, Any

from fastapi import UploadFile

from app.config import settings


async def validate_pdf(file: UploadFile) -> Dict[str, Any]:
    """
    Validate that an uploaded file is a valid PDF.
    
    Checks:
    - File extension is .pdf
    - File size is within limits
    - File has valid PDF magic bytes
    
    Returns dict with 'valid' boolean and optional 'error' message.
    """
    # Check extension
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        return {
            "valid": False,
            "error": f"Invalid file type: {ext}. Only PDF files are allowed."
        }
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if size > max_size_bytes:
        return {
            "valid": False,
            "error": f"File too large: {size / (1024*1024):.1f}MB. Maximum: {settings.MAX_FILE_SIZE_MB}MB"
        }
    
    # Check PDF magic bytes
    magic_bytes = await file.read(5)
    await file.seek(0)  # Reset position
    
    if magic_bytes != b'%PDF-':
        return {
            "valid": False,
            "error": "Invalid PDF file. File does not have valid PDF header."
        }
    
    return {"valid": True}


async def save_uploaded_file(
    file: UploadFile,
    session_id: str,
    upload_dir: str = None
) -> str:
    """
    Save an uploaded file to disk.
    
    Args:
        file: The uploaded file
        session_id: Session ID for organizing files
        upload_dir: Base upload directory
        
    Returns:
        Full path to the saved file
    """
    upload_dir = upload_dir or settings.UPLOAD_DIR
    
    # Create session directory
    session_dir = os.path.join(upload_dir, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    # Generate unique filename
    original_name = file.filename or "document.pdf"
    base_name = os.path.splitext(original_name)[0]
    unique_name = f"{base_name}_{uuid.uuid4().hex[:8]}.pdf"
    
    file_path = os.path.join(session_dir, unique_name)
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    
    return file_path


async def delete_session_files(session_id: str, upload_dir: str = None):
    """
    Delete all files for a session.
    """
    import shutil
    
    upload_dir = upload_dir or settings.UPLOAD_DIR
    session_dir = os.path.join(upload_dir, session_id)
    
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)


def get_file_size_mb(file_path: str) -> float:
    """Get file size in megabytes."""
    if os.path.exists(file_path):
        return os.path.getsize(file_path) / (1024 * 1024)
    return 0.0
