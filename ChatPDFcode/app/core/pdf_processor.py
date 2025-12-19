"""
PDF Processor
Handles extraction of text, tables, images from PDF documents
"""

import os
import io
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
import pytesseract
import cv2
import numpy as np

from app.config import settings


@dataclass
class TextBlock:
    """Represents a block of text from a PDF."""
    content: str
    page_number: int
    bbox: Tuple[float, float, float, float] = None  # x0, y0, x1, y1
    font_size: float = None
    is_heading: bool = False


@dataclass
class TableData:
    """Represents a table extracted from a PDF."""
    content: List[List[str]]
    page_number: int
    title: Optional[str] = None
    bbox: Tuple[float, float, float, float] = None


@dataclass
class ImageData:
    """Represents an image extracted from a PDF."""
    image_bytes: bytes
    page_number: int
    bbox: Tuple[float, float, float, float] = None
    caption: Optional[str] = None
    image_index: int = 0
    description: Optional[str] = None  # AI-generated description


@dataclass
class ProcessedDocument:
    """Result of processing a PDF document."""
    document_id: str
    filename: str
    total_pages: int
    text_blocks: List[TextBlock] = field(default_factory=list)
    tables: List[TableData] = field(default_factory=list)
    images: List[ImageData] = field(default_factory=list)
    is_scanned: bool = False


class PDFProcessor:
    """
    Main class for processing PDF documents.
    Handles both native digital PDFs and scanned documents.
    """
    
    def __init__(self):
        self.min_text_length = 50  # Minimum chars to consider a page as text
        self.dpi = 150  # DPI for image extraction
    
    def process_document(
        self,
        file_path: str,
        document_id: str
    ) -> ProcessedDocument:
        """
        Process a PDF document and extract all content.
        
        Args:
            file_path: Path to the PDF file
            document_id: Unique identifier for the document
            
        Returns:
            ProcessedDocument with all extracted content
        """
        filename = os.path.basename(file_path)
        
        # Detect if PDF is scanned or native
        is_scanned = self._detect_scanned_pdf(file_path)
        
        # Extract content based on type
        if is_scanned:
            text_blocks = self._extract_text_ocr(file_path)
        else:
            text_blocks = self._extract_text_native(file_path)
        
        # Extract tables
        tables = self._extract_tables(file_path)
        
        # Extract images
        images = self._extract_images(file_path)
        
        # Get total pages
        with fitz.open(file_path) as doc:
            total_pages = len(doc)
        
        return ProcessedDocument(
            document_id=document_id,
            filename=filename,
            total_pages=total_pages,
            text_blocks=text_blocks,
            tables=tables,
            images=images,
            is_scanned=is_scanned
        )
    
    def _detect_scanned_pdf(self, file_path: str) -> bool:
        """
        Detect if a PDF is scanned (image-based) or native digital.
        
        Returns True if majority of pages have little/no text.
        """
        with fitz.open(file_path) as doc:
            pages_with_text = 0
            total_pages = min(len(doc), 5)  # Check first 5 pages
            
            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()
                if len(text.strip()) > self.min_text_length:
                    pages_with_text += 1
            
            # If less than 50% of pages have text, consider it scanned
            return pages_with_text < (total_pages * 0.5)
    
    def _extract_text_native(self, file_path: str) -> List[TextBlock]:
        """
        Extract text from a native digital PDF using PyMuPDF.
        Preserves structure and formatting.
        """
        text_blocks = []
        
        with fitz.open(file_path) as doc:
            for page_num, page in enumerate(doc, start=1):
                # Get text blocks with position and font info
                blocks = page.get_text("dict")["blocks"]
                
                for block in blocks:
                    if block["type"] == 0:  # Text block
                        block_text = ""
                        max_font_size = 0
                        
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                block_text += span["text"] + " "
                                max_font_size = max(max_font_size, span.get("size", 12))
                        
                        block_text = block_text.strip()
                        if block_text:
                            text_blocks.append(TextBlock(
                                content=block_text,
                                page_number=page_num,
                                bbox=tuple(block["bbox"]),
                                font_size=max_font_size,
                                is_heading=max_font_size > 14  # Heuristic
                            ))
        
        return text_blocks
    
    def _extract_text_ocr(self, file_path: str) -> List[TextBlock]:
        """
        Extract text from scanned PDF using OCR (Tesseract).
        """
        text_blocks = []
        
        with fitz.open(file_path) as doc:
            for page_num, page in enumerate(doc, start=1):
                # Convert page to image
                pix = page.get_pixmap(dpi=self.dpi)
                img_data = pix.tobytes("png")
                
                # Convert to PIL Image for preprocessing
                image = Image.open(io.BytesIO(img_data))
                
                # Preprocess image for better OCR
                processed_img = self._preprocess_image_for_ocr(image)
                
                # Run OCR
                try:
                    text = pytesseract.image_to_string(
                        processed_img,
                        lang='spa+eng',  # Spanish + English
                        config='--psm 1'  # Automatic page segmentation
                    )
                    
                    if text.strip():
                        text_blocks.append(TextBlock(
                            content=text.strip(),
                            page_number=page_num,
                            is_heading=False
                        ))
                except Exception as e:
                    print(f"OCR error on page {page_num}: {e}")
        
        return text_blocks
    
    def _preprocess_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better OCR results.
        Applies binarization and noise removal.
        """
        # Convert to numpy array
        img_array = np.array(image)
        
        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Apply adaptive thresholding
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(binary, None, 10, 7, 21)
        
        return Image.fromarray(denoised)
    
    def _extract_tables(self, file_path: str) -> List[TableData]:
        """
        Extract tables from PDF using pdfplumber.
        """
        tables = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_tables = page.extract_tables()
                    
                    for table in page_tables:
                        if table and len(table) > 1:  # At least header + 1 row
                            tables.append(TableData(
                                content=table,
                                page_number=page_num
                            ))
        except Exception as e:
            print(f"Table extraction error: {e}")
        
        return tables
    
    def _extract_images(self, file_path: str) -> List[ImageData]:
        """
        Extract embedded images from PDF.
        """
        images = []
        
        with fitz.open(file_path) as doc:
            for page_num, page in enumerate(doc, start=1):
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    
                    try:
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        
                        # Only include reasonably sized images
                        img_pil = Image.open(io.BytesIO(image_bytes))
                        if img_pil.width > 100 and img_pil.height > 100:
                            images.append(ImageData(
                                image_bytes=image_bytes,
                                page_number=page_num,
                                image_index=img_index
                            ))
                    except Exception as e:
                        print(f"Image extraction error: {e}")
        
        return images
    
    def table_to_markdown(self, table: TableData) -> str:
        """Convert a table to markdown format."""
        if not table.content:
            return ""
        
        lines = []
        header = table.content[0]
        
        # Header row
        lines.append("| " + " | ".join(str(cell) for cell in header) + " |")
        # Separator
        lines.append("| " + " | ".join("---" for _ in header) + " |")
        # Data rows
        for row in table.content[1:]:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        
        return "\n".join(lines)
    
    def table_to_json(self, table: TableData) -> List[Dict[str, str]]:
        """Convert a table to list of dictionaries."""
        if not table.content or len(table.content) < 2:
            return []
        
        headers = [str(h).strip() for h in table.content[0]]
        rows = []
        
        for row in table.content[1:]:
            row_dict = {}
            for i, cell in enumerate(row):
                if i < len(headers):
                    row_dict[headers[i]] = str(cell).strip()
            rows.append(row_dict)
        
        return rows


# Global instance
pdf_processor = PDFProcessor()
