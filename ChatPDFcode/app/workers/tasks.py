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
    # Don't reconnect if already connected
    if redis_manager.client is None:
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


def _update_document_status_sync(
    job_id: str,
    document_id: str,
    status: str,
    error: str = None,
    extra_info: Dict[str, Any] = None
):
    """Synchronous version - uses separate Redis connection."""
    import redis
    import json
    from app.config import settings
    
    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    key = f"job:{job_id}"
    data = r.get(key)
    if data:
        job_data = json.loads(data)
        for doc in job_data.get("documents", []):
            if doc["document_id"] == document_id:
                doc["status"] = status
                if error:
                    doc["error"] = error
                if extra_info:
                    doc.update(extra_info)
                break
        r.setex(key, 24 * 3600, json.dumps(job_data))
    r.close()


def process_document_sync(
    job_id: str,
    document_id: str,
    file_path: str,
    session_id: str
):
    """
    Synchronous document processing using sync Redis.
    """
    try:
        # Update status to processing
        _update_document_status_sync(
            job_id=job_id,
            document_id=document_id,
            status="processing"
        )
        
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
        
        # Step 3: Generate embeddings and store (sync version)
        from app.core.embeddings import EmbeddingService
        from app.db.qdrant_client import QdrantManager
        from qdrant_client import QdrantClient
        from app.config import settings
        
        # Create sync Qdrant client
        sync_qdrant = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        collection_name = f"session_{session_id}"
        
        # Ensure collection exists
        try:
            sync_qdrant.get_collection(collection_name)
        except:
            sync_qdrant.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "size": settings.EMBEDDING_DIMENSION,
                    "distance": "Cosine"
                }
            )
        
        # Generate embeddings
        embed_service = EmbeddingService()
        texts = [chunk.content for chunk in chunks]  # Use .content attribute
        embeddings = embed_service.model.encode(texts)
        
        # Store in Qdrant
        from qdrant_client.models import PointStruct
        import uuid
        
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding.tolist(),
                payload={
                    "content": chunk.content,
                    "chunk_id": chunk.chunk_id,
                    "token_count": chunk.token_count,
                    **chunk.metadata
                }
            ))
        
        sync_qdrant.upsert(collection_name=collection_name, points=points)
        print(f"  ✅ Stored {len(points)} vectors in Qdrant")
        
        # Update status to completed
        _update_document_status_sync(
            job_id=job_id,
            document_id=document_id,
            status="completed",
            extra_info={
                "pages": processed_doc.total_pages,
                "chunks": len(chunks)
            }
        )
        
        print(f"  ✅ Document processed successfully!")
        
    except Exception as e:
        print(f"  ❌ Error processing document: {e}")
        import traceback
        traceback.print_exc()
        
        # Update status to failed
        _update_document_status_sync(
            job_id=job_id,
            document_id=document_id,
            status="failed",
            error=str(e)
        )


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
