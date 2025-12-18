"""
Celery Tasks
Async tasks for document processing
"""

import asyncio
from typing import Dict, Any

from celery import shared_task

from app.workers.celery_app import celery_app
from app.core.pdf_processor import pdf_processor
from app.core.chunking import semantic_chunker
from app.core.embeddings import embedding_service
from app.db.redis_client import redis_manager
from app.db.qdrant_client import qdrant_manager


def run_async(coro):
    """Helper to run async code in Celery tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3)
def process_document_task(
    self,
    job_id: str,
    document_id: str,
    file_path: str,
    session_id: str
):
    """
    Process a single PDF document.
    
    Pipeline:
    1. Extract text, tables, images from PDF
    2. Chunk content semantically
    3. Generate embeddings
    4. Store in Qdrant
    """
    try:
        # Update status to processing
        run_async(_update_document_status(
            job_id=job_id,
            document_id=document_id,
            status="processing"
        ))
        
        print(f"📄 Processing document: {file_path}")
        
        # Step 1: Extract content from PDF
        processed_doc = pdf_processor.process_document(
            file_path=file_path,
            document_id=document_id
        )
        
        print(f"  ✅ Extracted: {len(processed_doc.text_blocks)} text blocks, "
              f"{len(processed_doc.tables)} tables, {len(processed_doc.images)} images")
        
        # Step 2: Chunk the content
        chunks = semantic_chunker.chunk_document(processed_doc)
        print(f"  ✅ Created {len(chunks)} chunks")
        
        # Step 3: Generate embeddings and store
        stored_count = run_async(
            embedding_service.embed_and_store_chunks(
                chunks=chunks,
                session_id=session_id
            )
        )
        print(f"  ✅ Stored {stored_count} vectors in Qdrant")
        
        # Update status to completed
        run_async(_update_document_status(
            job_id=job_id,
            document_id=document_id,
            status="completed",
            extra_info={
                "pages": processed_doc.total_pages,
                "chunks": len(chunks)
            }
        ))
        
        return {
            "status": "completed",
            "document_id": document_id,
            "pages": processed_doc.total_pages,
            "chunks": len(chunks)
        }
        
    except Exception as e:
        print(f"  ❌ Error processing document: {e}")
        
        # Update status to failed
        run_async(_update_document_status(
            job_id=job_id,
            document_id=document_id,
            status="failed",
            error=str(e)
        ))
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


async def _update_document_status(
    job_id: str,
    document_id: str,
    status: str,
    error: str = None,
    extra_info: Dict[str, Any] = None
):
    """Update document status in Redis."""
    await redis_manager.connect()
    
    job_data = await redis_manager.get_job(job_id)
    if job_data:
        for doc in job_data.get("documents", []):
            if doc["document_id"] == document_id:
                doc["status"] = status
                if error:
                    doc["error"] = error
                if extra_info:
                    doc.update(extra_info)
                break
        await redis_manager.set_job(job_id, job_data)
    
    await redis_manager.disconnect()


@celery_app.task
def cleanup_session_task(session_id: str):
    """
    Cleanup all data for an expired session.
    """
    async def cleanup():
        await redis_manager.connect()
        await qdrant_manager.connect()
        
        # Delete Qdrant collection
        collection_name = f"session_{session_id}"
        await qdrant_manager.delete_collection(collection_name)
        
        # Delete Redis data
        await redis_manager.delete_session(session_id)
        
        # TODO: Delete uploaded files
        
        await redis_manager.disconnect()
        await qdrant_manager.disconnect()
        
        print(f"🧹 Cleaned up session: {session_id}")
    
    run_async(cleanup())
    return {"status": "cleaned", "session_id": session_id}


@celery_app.task
def health_check_task():
    """Simple health check task."""
    return {"status": "healthy"}
