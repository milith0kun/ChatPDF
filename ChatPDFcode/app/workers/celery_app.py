"""
Celery Application Configuration
"""

from celery import Celery

from app.config import settings

# Create Celery app
celery_app = Celery(
    "chatpdf",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    
    # Result settings
    result_expires=3600,  # 1 hour
    
    # Task routes
    task_routes={
        "app.workers.tasks.process_document_task": {"queue": "documents"},
        "app.workers.tasks.cleanup_session_task": {"queue": "cleanup"},
    },
    
    # Default queue
    task_default_queue="default",
)
