"""
RAG Service
Implements Retrieval-Augmented Generation with hybrid search
"""

from typing import List, Dict, Any, Optional, AsyncGenerator
import json
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.config import settings
from app.core.embeddings import embedding_service
from app.db.qdrant_client import qdrant_manager
from app.db.redis_client import redis_manager
from app.llm.anthropic_client import anthropic_client
from app.llm.prompts import SYSTEM_PROMPT, build_context_prompt


@dataclass
class RetrievedChunk:
    """A chunk retrieved from the vector database."""
    chunk_id: str
    content: str
    score: float
    metadata: Dict[str, Any]


@dataclass
class RAGResponse:
    """Response from the RAG system."""
    answer: str
    references: List[Dict[str, Any]]
    confidence: Optional[float] = None


class RAGService:
    """
    Implements hybrid RAG with vector search and BM25.
    Uses Reciprocal Rank Fusion to combine results.
    """
    
    def __init__(self):
        self.top_k_retrieval = settings.TOP_K_RETRIEVAL
        self.top_k_final = settings.TOP_K_FINAL
        self.rrf_k = settings.RRF_K
    
    async def generate_response(
        self,
        query: str,
        session_id: str,
        chat_history: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a response using RAG pipeline.
        
        1. Retrieve relevant chunks using hybrid search
        2. Build context from top chunks
        3. Generate response with LLM
        4. Extract and validate references
        """
        # Step 1: Retrieve relevant chunks
        retrieved_chunks = await self._hybrid_search(
            query=query,
            session_id=session_id
        )
        
        if not retrieved_chunks:
            return {
                "answer": "No encontré información relevante en los documentos cargados para responder tu pregunta. Por favor, intenta reformular tu consulta o verifica que los documentos contengan la información que buscas.",
                "references": [],
                "confidence": 0.0
            }
        
        # Step 2: Build context
        context = self._build_context(retrieved_chunks)
        
        # Step 3: Generate response
        response = await anthropic_client.generate_response(
            system_prompt=SYSTEM_PROMPT,
            context=context,
            query=query,
            chat_history=chat_history
        )
        
        # Step 4: Extract references
        references = self._extract_references(retrieved_chunks)
        
        return {
            "answer": response["answer"],
            "references": references,
            "confidence": response.get("confidence"),
            "token_usage": {
                "provider": response.get("provider", "anthropic"),
                "model": response.get("model", settings.LLM_MODEL),
                "input_tokens": response.get("input_tokens", 0),
                "output_tokens": response.get("output_tokens", 0),
                "total_tokens": response.get("total_tokens", 0)
            }
        }
    
    async def generate_response_stream(
        self,
        query: str,
        session_id: str,
        chat_history: List[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response.
        """
        # Retrieve chunks
        retrieved_chunks = await self._hybrid_search(
            query=query,
            session_id=session_id
        )
        
        if not retrieved_chunks:
            yield json.dumps({
                "type": "text",
                "content": "No encontré información relevante en los documentos."
            })
            return
        
        # Build context
        context = self._build_context(retrieved_chunks)
        
        # Stream response
        async for chunk in anthropic_client.generate_response_stream(
            system_prompt=SYSTEM_PROMPT,
            context=context,
            query=query,
            chat_history=chat_history
        ):
            yield chunk
        
        # Send references at the end
        references = self._extract_references(retrieved_chunks)
        yield json.dumps({
            "type": "references",
            "content": references
        })
    
    async def _hybrid_search(
        self,
        query: str,
        session_id: str
    ) -> List[RetrievedChunk]:
        """
        Perform hybrid search combining vector and BM25 search.
        """
        collection_name = f"session_{session_id}"
        
        # Check if collection exists
        if not await qdrant_manager.collection_exists(collection_name):
            return []
        
        # Vector search
        query_embedding = embedding_service.generate_query_embedding(query)
        vector_results = await qdrant_manager.search_vectors(
            collection_name=collection_name,
            query_vector=query_embedding,
            top_k=self.top_k_retrieval
        )
        
        # Convert to RetrievedChunk objects
        vector_chunks = [
            RetrievedChunk(
                chunk_id=r["id"],
                content=r["payload"].get("content", ""),
                score=r["score"],
                metadata=r["payload"]
            )
            for r in vector_results
        ]
        
        # BM25 search (on the retrieved texts for efficiency)
        if vector_chunks:
            bm25_chunks = self._bm25_rerank(query, vector_chunks)
        else:
            bm25_chunks = []
        
        # Combine results using RRF
        combined = self._reciprocal_rank_fusion(
            vector_results=vector_chunks,
            bm25_results=bm25_chunks
        )
        
        # Return top K
        return combined[:self.top_k_final]
    
    def _bm25_rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """
        Rerank chunks using BM25.
        """
        # Tokenize documents
        tokenized_corpus = [chunk.content.lower().split() for chunk in chunks]
        bm25 = BM25Okapi(tokenized_corpus)
        
        # Get scores
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)
        
        # Create new chunks with BM25 scores
        scored_chunks = []
        for i, chunk in enumerate(chunks):
            new_chunk = RetrievedChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=float(scores[i]),
                metadata=chunk.metadata
            )
            scored_chunks.append(new_chunk)
        
        # Sort by BM25 score
        scored_chunks.sort(key=lambda x: x.score, reverse=True)
        return scored_chunks
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: List[RetrievedChunk],
        bm25_results: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """
        Combine results using Reciprocal Rank Fusion.
        
        RRF score = sum(1 / (k + rank_i)) for each ranking
        """
        rrf_scores = {}
        chunk_map = {}
        
        # Process vector results
        for rank, chunk in enumerate(vector_results, start=1):
            score = 1 / (self.rrf_k + rank)
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0) + score
            chunk_map[chunk.chunk_id] = chunk
        
        # Process BM25 results
        for rank, chunk in enumerate(bm25_results, start=1):
            score = 1 / (self.rrf_k + rank)
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0) + score
            if chunk.chunk_id not in chunk_map:
                chunk_map[chunk.chunk_id] = chunk
        
        # Sort by combined score
        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda x: rrf_scores[x],
            reverse=True
        )
        
        # Create result list with RRF scores
        results = []
        for chunk_id in sorted_ids:
            chunk = chunk_map[chunk_id]
            new_chunk = RetrievedChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=rrf_scores[chunk_id],
                metadata=chunk.metadata
            )
            results.append(new_chunk)
        
        return results
    
    def _build_context(self, chunks: List[RetrievedChunk]) -> str:
        """
        Build context string from retrieved chunks.
        """
        context_parts = []
        
        for i, chunk in enumerate(chunks, start=1):
            doc_name = chunk.metadata.get("document_name", "Documento")
            page = chunk.metadata.get("primary_page", "?")
            section = chunk.metadata.get("section_title", "")
            chunk_type = chunk.metadata.get("chunk_type", "text")
            
            header = f"[Fragmento {i}] Documento: {doc_name}, Página: {page}"
            if section:
                header += f", Sección: {section}"
            if chunk_type == "table":
                header += " (Tabla)"
            
            context_parts.append(f"{header}\n{chunk.content}")
        
        return "\n\n---\n\n".join(context_parts)
    
    def _extract_references(
        self,
        chunks: List[RetrievedChunk]
    ) -> List[Dict[str, Any]]:
        """
        Extract reference information from chunks.
        """
        references = []
        seen_pages = set()
        
        for chunk in chunks:
            doc_id = chunk.metadata.get("document_id", "")
            doc_name = chunk.metadata.get("document_name", "")
            page = chunk.metadata.get("primary_page", 1)
            section = chunk.metadata.get("section_title")
            
            # Avoid duplicate page references
            ref_key = f"{doc_id}_{page}"
            if ref_key in seen_pages:
                continue
            seen_pages.add(ref_key)
            
            # Get excerpt (first 200 chars)
            excerpt = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
            
            references.append({
                "document_id": doc_id,
                "document_name": doc_name,
                "page_number": page,
                "section": section,
                "excerpt": excerpt,
                "relevance_score": round(chunk.score, 3)
            })
        
        return references
