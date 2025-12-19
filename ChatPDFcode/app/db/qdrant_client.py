"""
Qdrant Client
Handles vector storage for document embeddings
"""

from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue
)

from app.config import settings


class QdrantManager:
    """Manager for Qdrant vector database operations."""
    
    def __init__(self):
        self.client: Optional[AsyncQdrantClient] = None
    
    async def connect(self):
        """Establish connection to Qdrant."""
        self.client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        print(f"✅ Connected to Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    
    async def disconnect(self):
        """Close Qdrant connection."""
        if self.client:
            await self.client.close()
            print("🔌 Disconnected from Qdrant")
    
    async def ping(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            if self.client:
                # Try to get collections as a health check
                await self.client.get_collections()
                return True
            return False
        except Exception:
            return False
    
    # ======================
    # Collection Management
    # ======================
    
    async def create_collection(
        self,
        collection_name: str,
        vector_size: int = None
    ):
        """Create a new collection for a session."""
        size = vector_size or settings.EMBEDDING_DIMENSION
        
        # Check if collection exists
        collections = await self.client.get_collections()
        existing = [c.name for c in collections.collections]
        
        if collection_name not in existing:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=size,
                    distance=Distance.COSINE
                ),
                # HNSW index configuration for fast search
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100
                )
            )
            print(f"📦 Created collection: {collection_name}")
    
    async def delete_collection(self, collection_name: str):
        """Delete a collection."""
        try:
            await self.client.delete_collection(collection_name)
            print(f"🗑️ Deleted collection: {collection_name}")
        except Exception:
            pass  # Collection might not exist
    
    async def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists."""
        collections = await self.client.get_collections()
        return collection_name in [c.name for c in collections.collections]
    
    # ======================
    # Vector Operations
    # ======================
    
    async def upsert_vectors(
        self,
        collection_name: str,
        points: List[Dict[str, Any]]
    ):
        """
        Insert or update vectors in a collection.
        
        points format:
        [
            {
                "id": "unique-id",
                "vector": [0.1, 0.2, ...],
                "payload": {"document_id": "...", "page": 1, ...}
            }
        ]
        """
        point_structs = [
            PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=p.get("payload", {})
            )
            for p in points
        ]
        
        await self.client.upsert(
            collection_name=collection_name,
            points=point_structs
        )
    
    async def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int = 10,
        filter_conditions: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Returns list of results with id, score, and payload.
        """
        # Build filter if provided
        search_filter = None
        if filter_conditions:
            conditions = []
            for field, value in filter_conditions.items():
                conditions.append(
                    FieldCondition(
                        key=field,
                        match=MatchValue(value=value)
                    )
                )
            search_filter = Filter(must=conditions)
        
        # Use query_points (new API) instead of search
        results = await self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=search_filter,
            with_payload=True
        )
        
        return [
            {
                "id": str(r.id),
                "score": r.score,
                "payload": r.payload
            }
            for r in results.points
        ]
    
    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a collection."""
        info = await self.client.get_collection(collection_name)
        return {
            "name": collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.value
        }


# Global instance
qdrant_manager = QdrantManager()
