"""
Redis Client
Handles session storage, job tracking, and chat history
"""

import json
from typing import Dict, List, Optional, Any
from redis import asyncio as aioredis

from app.config import settings


class RedisManager:
    """Manager for Redis connections and operations."""
    
    def __init__(self):
        self.client: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Establish connection to Redis."""
        self.client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        print(f"✅ Connected to Redis at {settings.REDIS_URL}")
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            print("🔌 Disconnected from Redis")
    
    async def ping(self) -> bool:
        """Check if Redis is reachable."""
        try:
            if self.client:
                await self.client.ping()
                return True
            return False
        except Exception:
            return False
    
    # ======================
    # Session Management
    # ======================
    
    async def set_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        expiry_hours: int = None
    ):
        """Store session data with expiration."""
        expiry = expiry_hours or settings.SESSION_EXPIRY_HOURS
        key = f"session:{session_id}"
        await self.client.setex(
            key,
            expiry * 3600,  # Convert to seconds
            json.dumps(data)
        )
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data."""
        key = f"session:{session_id}"
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def delete_session(self, session_id: str):
        """Delete a session and all related data."""
        # Delete session
        await self.client.delete(f"session:{session_id}")
        # Delete chat history
        await self.client.delete(f"chat:{session_id}")
        # Delete any jobs associated
        pattern = f"job:*:{session_id}"
        async for key in self.client.scan_iter(pattern):
            await self.client.delete(key)
    
    async def refresh_session(self, session_id: str):
        """Refresh session expiration time."""
        key = f"session:{session_id}"
        await self.client.expire(key, settings.SESSION_EXPIRY_HOURS * 3600)
    
    # ======================
    # Job Management
    # ======================
    
    async def set_job(self, job_id: str, data: Dict[str, Any]):
        """Store processing job data."""
        key = f"job:{job_id}"
        await self.client.setex(
            key,
            24 * 3600,  # 24 hour expiry
            json.dumps(data)
        )
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job data."""
        key = f"job:{job_id}"
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def update_job_document_status(
        self,
        job_id: str,
        document_id: str,
        status: str,
        error: str = None
    ):
        """Update the status of a document in a job."""
        job_data = await self.get_job(job_id)
        if job_data:
            for doc in job_data.get("documents", []):
                if doc["document_id"] == document_id:
                    doc["status"] = status
                    if error:
                        doc["error"] = error
                    break
            await self.set_job(job_id, job_data)
    
    # ======================
    # Chat History
    # ======================
    
    async def add_chat_message(self, session_id: str, message: Dict[str, Any]):
        """Add a message to chat history."""
        key = f"chat:{session_id}"
        await self.client.rpush(key, json.dumps(message))
        # Set expiry same as session
        await self.client.expire(key, settings.SESSION_EXPIRY_HOURS * 3600)
    
    async def get_chat_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve chat history."""
        key = f"chat:{session_id}"
        messages = await self.client.lrange(key, -limit, -1)
        return [json.loads(m) for m in messages]
    
    async def clear_chat_history(self, session_id: str):
        """Clear chat history for a session."""
        key = f"chat:{session_id}"
        await self.client.delete(key)


# Global instance
redis_manager = RedisManager()
