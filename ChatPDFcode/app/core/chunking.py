"""
Chunking Module
Implements semantic chunking with overlap for document processing
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import tiktoken

from app.config import settings
from app.core.pdf_processor import ProcessedDocument, TextBlock, TableData


@dataclass
class DocumentChunk:
    """Represents a chunk of document content."""
    chunk_id: str
    content: str
    metadata: Dict[str, Any]
    token_count: int


class SemanticChunker:
    """
    Implements semantic chunking with overlap.
    Preserves section boundaries and maintains context.
    """
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        model_name: str = "gpt-4"
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        
        # Use tiktoken for accurate token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))
    
    def chunk_document(
        self,
        document: ProcessedDocument
    ) -> List[DocumentChunk]:
        """
        Chunk a processed document into semantic chunks.
        
        Returns list of DocumentChunk objects.
        """
        chunks = []
        chunk_counter = 0
        
        # Process text blocks
        text_chunks = self._chunk_text_blocks(
            document.text_blocks,
            document.document_id,
            document.filename
        )
        for chunk in text_chunks:
            chunk.chunk_id = f"{document.document_id}_chunk_{chunk_counter}"
            chunks.append(chunk)
            chunk_counter += 1
        
        # Process tables as special chunks
        for i, table in enumerate(document.tables):
            table_chunk = self._create_table_chunk(
                table=table,
                document_id=document.document_id,
                document_name=document.filename,
                chunk_id=f"{document.document_id}_table_{i}"
            )
            chunks.append(table_chunk)
        
        return chunks
    
    def _chunk_text_blocks(
        self,
        text_blocks: List[TextBlock],
        document_id: str,
        document_name: str
    ) -> List[DocumentChunk]:
        """
        Chunk text blocks with semantic awareness.
        """
        chunks = []
        current_chunk_text = ""
        current_chunk_pages = []
        current_section = None
        
        for block in text_blocks:
            # Detect section changes
            if block.is_heading:
                # If we have accumulated text, save it as a chunk
                if current_chunk_text.strip():
                    chunk = self._create_text_chunk(
                        content=current_chunk_text.strip(),
                        pages=current_chunk_pages,
                        section=current_section,
                        document_id=document_id,
                        document_name=document_name
                    )
                    chunks.append(chunk)
                    current_chunk_text = ""
                    current_chunk_pages = []
                
                current_section = block.content
            
            # Add block content
            block_text = block.content
            block_tokens = self.count_tokens(block_text)
            current_tokens = self.count_tokens(current_chunk_text)
            
            # Check if adding this block exceeds chunk size
            if current_tokens + block_tokens > self.chunk_size:
                # Save current chunk
                if current_chunk_text.strip():
                    chunk = self._create_text_chunk(
                        content=current_chunk_text.strip(),
                        pages=current_chunk_pages,
                        section=current_section,
                        document_id=document_id,
                        document_name=document_name
                    )
                    chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk_text)
                current_chunk_text = overlap_text + " " + block_text
                current_chunk_pages = [block.page_number]
            else:
                current_chunk_text += " " + block_text
                if block.page_number not in current_chunk_pages:
                    current_chunk_pages.append(block.page_number)
        
        # Don't forget the last chunk
        if current_chunk_text.strip():
            chunk = self._create_text_chunk(
                content=current_chunk_text.strip(),
                pages=current_chunk_pages,
                section=current_section,
                document_id=document_id,
                document_name=document_name
            )
            chunks.append(chunk)
        
        return chunks
    
    def _get_overlap_text(self, text: str) -> str:
        """
        Get the last N tokens of text for overlap.
        """
        tokens = self.tokenizer.encode(text)
        overlap_tokens = tokens[-self.chunk_overlap:]
        return self.tokenizer.decode(overlap_tokens)
    
    def _create_text_chunk(
        self,
        content: str,
        pages: List[int],
        section: Optional[str],
        document_id: str,
        document_name: str
    ) -> DocumentChunk:
        """Create a text chunk with metadata."""
        return DocumentChunk(
            chunk_id="",  # Will be set by parent
            content=content,
            token_count=self.count_tokens(content),
            metadata={
                "document_id": document_id,
                "document_name": document_name,
                "page_numbers": pages,
                "section_title": section,
                "chunk_type": "text",
                "primary_page": pages[0] if pages else 1
            }
        )
    
    def _create_table_chunk(
        self,
        table: TableData,
        document_id: str,
        document_name: str,
        chunk_id: str
    ) -> DocumentChunk:
        """Create a chunk from a table."""
        # Convert table to text representation
        table_text = self._table_to_text(table)
        
        return DocumentChunk(
            chunk_id=chunk_id,
            content=table_text,
            token_count=self.count_tokens(table_text),
            metadata={
                "document_id": document_id,
                "document_name": document_name,
                "page_numbers": [table.page_number],
                "section_title": table.title,
                "chunk_type": "table",
                "primary_page": table.page_number
            }
        )
    
    def _table_to_text(self, table: TableData) -> str:
        """Convert table to searchable text format."""
        if not table.content:
            return ""
        
        lines = []
        if table.title:
            lines.append(f"Tabla: {table.title}")
        
        # Add header description
        if table.content:
            headers = table.content[0]
            lines.append(f"Columnas: {', '.join(str(h) for h in headers)}")
        
        # Add rows as key-value pairs
        if len(table.content) > 1:
            headers = table.content[0]
            for row in table.content[1:]:
                row_desc = []
                for i, cell in enumerate(row):
                    if i < len(headers) and cell:
                        row_desc.append(f"{headers[i]}: {cell}")
                if row_desc:
                    lines.append(" | ".join(row_desc))
        
        return "\n".join(lines)


# Global instance
semantic_chunker = SemanticChunker()
