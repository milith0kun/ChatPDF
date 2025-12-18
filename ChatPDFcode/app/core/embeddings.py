"""
Embeddings Service
Generates vector embeddings for document chunks
"""

from typing import List, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.core.chunking import DocumentChunk
from app.db.qdrant_client import qdrant_manager


class EmbeddingService:
    """
    Service for generating and storing text embeddings.
    Uses sentence-transformers for multilingual support.
    """
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._model = None
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._model is None:
            print(f"📥 Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            print(f"✅ Embedding model loaded")
        return self._model
    
    def generate_embeddings(
        self,
        texts: List[str],
        batch_size: int = 32,
        normalize: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            batch_size: Number of texts to process at once
            normalize: Whether to L2-normalize vectors
            
        Returns:
            numpy array of shape (len(texts), embedding_dim)
        """
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 100,
            normalize_embeddings=normalize
        )
        
        return embeddings
    
    def generate_query_embedding(
        self,
        query: str,
        normalize: bool = True
    ) -> List[float]:
        """
        Generate embedding for a single query.
        
        Returns a list of floats suitable for vector search.
        """
        embedding = self.model.encode(
            query,
            normalize_embeddings=normalize
        )
        return embedding.tolist()
    
    async def embed_and_store_chunks(
        self,
        chunks: List[DocumentChunk],
        session_id: str
    ) -> int:
        """
        Generate embeddings for chunks and store in Qdrant.
        
        Args:
            chunks: List of DocumentChunk objects
            session_id: Session ID (used as collection name)
            
        Returns:
            Number of chunks stored
        """
        if not chunks:
            return 0
        
        collection_name = f"session_{session_id}"
        
        # Generate embeddings
        texts = [chunk.content for chunk in chunks]
        embeddings = self.generate_embeddings(texts)
        
        # Prepare points for Qdrant
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            points.append({
                "id": chunk.chunk_id,
                "vector": embedding.tolist(),
                "payload": {
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                    **chunk.metadata
                }
            })
        
        # Store in Qdrant
        await qdrant_manager.upsert_vectors(
            collection_name=collection_name,
            points=points
        )
        
        return len(points)
    
    def calculate_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.
        """
        # If already normalized, dot product equals cosine similarity
        return float(np.dot(embedding1, embedding2))


# Global instance
embedding_service = EmbeddingService()
