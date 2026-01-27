"""Document Extraction Agent for OCR and text extraction."""
from crewai import Agent, Task
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from datetime import datetime
import mimetypes

# PDF extraction
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    try:
        import PyPDF2
        PYPDF2_AVAILABLE = True
    except ImportError:
        PYPDF2_AVAILABLE = False

# DOCX extraction
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# Tesseract (local OCR)
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from agents.ocr_api_client import OCRAPIClient
from utilities import config, settings, logger, ensure_directory


class DocumentExtractionAgent:
    """Agent responsible for intelligent text extraction from documents."""
    
    # Supported formats
    IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif'}
    PDF_FORMAT = {'.pdf'}
    DOC_FORMATS = {'.docx', '.doc'}
    TEXT_FORMATS = {'.txt', '.csv', '.json'}
    
    def __init__(self, llm=None, ocr_api_client: Optional[OCRAPIClient] = None):
        """
        Initialize the Document Extraction Agent.
        
        Args:
            llm: Language model for the agent
            ocr_api_client: Optional OCR API client
        """
        self.llm = llm
        self.ocr_client = ocr_api_client or OCRAPIClient()
        self.extraction_dir = Path(settings.documents_dir) / "extracted"
        ensure_directory(str(self.extraction_dir))
        self.agent = self._create_agent()
        
        logger.info("Document Extraction Agent initialized")
    
    def _create_agent(self) -> Agent:
        """Create the CrewAI agent."""
        return Agent(
            role="Document Text Extraction Specialist",
            goal="Intelligently extract text from various document formats using the most appropriate method",
            backstory="""You are an expert in document text extraction with deep knowledge 
            of OCR technology, PDF processing, and document format handling. You analyze each 
            document to determine the best extraction method - whether direct text extraction, 
            OCR via API, or local OCR processing. You understand that some PDFs contain 
            searchable text while others are scanned images requiring OCR. Your goal is to 
            extract the highest quality text while being cost-effective and efficient.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
    
    def extract_from_document(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main extraction method - intelligently decides and executes extraction.
        
        Args:
            file_path: Path to the document
            metadata: Optional document metadata
            
        Returns:
            Extraction result with text and metadata
        """
        logger.info(f"Starting extraction for: {file_path}")
        
        try:
            # Step 1: Analyze document type
            doc_analysis = self._analyze_document(file_path)
            
            # Step 2: Extract based on analysis
            if doc_analysis['needs_ocr']:
                if doc_analysis['use_api']:
                    extraction_result = self._extract_with_ocr_api(file_path)
                else:
                    extraction_result = self._extract_with_local_ocr(file_path)
            else:
                extraction_result = self._extract_direct(file_path, doc_analysis)
            
            # Step 3: Validate extraction quality
            extraction_result['quality_score'] = self._assess_quality(
                extraction_result.get('text', '')
            )
            
            # Step 4: Store extracted data
            storage_result = self._store_extraction(file_path, extraction_result)
            extraction_result['storage'] = storage_result
            
            # Add metadata
            extraction_result['file_path'] = file_path
            extraction_result['timestamp'] = datetime.now().isoformat()
            extraction_result['original_metadata'] = metadata
            
            logger.info(
                f"Extraction completed for {Path(file_path).name}: "
                f"method={extraction_result['method']}, "
                f"quality={extraction_result['quality_score']:.2f}"
            )
            
            return extraction_result
            
        except Exception as e:
            logger.error(f"Extraction failed for {file_path}: {str(e)}")
            return {
                'file_path': file_path,
                'status': 'error',
                'error': str(e),
                'text': '',
                'method': 'failed',
                'timestamp': datetime.now().isoformat()
            }
    
    def _analyze_document(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze document to determine extraction strategy.
        
        Returns:
            Analysis result with extraction recommendations
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        
        analysis = {
            'extension': extension,
            'mime_type': mime_type,
            'needs_ocr': False,
            'use_api': False,
            'reason': ''
        }
        
        # Images always need OCR
        if extension in self.IMAGE_FORMATS:
            analysis['needs_ocr'] = True
            analysis['use_api'] = self.ocr_client.base_url is not None
            analysis['reason'] = 'Image file requires OCR'
            return analysis
        
        # Text files - direct extraction
        if extension in self.TEXT_FORMATS:
            analysis['needs_ocr'] = False
            analysis['reason'] = 'Plain text file'
            return analysis
        
        # DOCX - direct extraction
        if extension in self.DOC_FORMATS:
            analysis['needs_ocr'] = False
            analysis['reason'] = 'DOCX with embedded text'
            return analysis
        
        # PDF - needs investigation
        if extension in self.PDF_FORMAT:
            has_text = self._pdf_has_text(file_path)
            if has_text:
                analysis['needs_ocr'] = False
                analysis['reason'] = 'PDF with extractable text layer'
            else:
                analysis['needs_ocr'] = True
                analysis['use_api'] = self.ocr_client.base_url is not None
                analysis['reason'] = 'Scanned PDF requires OCR'
            return analysis
        
        # Unknown format
        analysis['reason'] = f'Unsupported format: {extension}'
        return analysis
    
    def _pdf_has_text(self, file_path: Path) -> bool:
        """Check if PDF has extractable text."""
        try:
            if PDFPLUMBER_AVAILABLE:
                with pdfplumber.open(file_path) as pdf:
                    # Check first page
                    if len(pdf.pages) > 0:
                        text = pdf.pages[0].extract_text()
                        return text is not None and len(text.strip()) > 50
            elif PYPDF2_AVAILABLE:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    if len(reader.pages) > 0:
                        text = reader.pages[0].extract_text()
                        return len(text.strip()) > 50
        except Exception as e:
            logger.warning(f"Error checking PDF text: {str(e)}")
        
        return False
    
    def _extract_direct(self, file_path: str, analysis: Dict) -> Dict[str, Any]:
        """Direct text extraction without OCR."""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        try:
            # Plain text
            if extension in self.TEXT_FORMATS:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                return {
                    'text': text,
                    'method': 'direct_text',
                    'confidence': 1.0,
                    'status': 'success'
                }
            
            # PDF extraction
            if extension in self.PDF_FORMAT:
                text = self._extract_pdf_text(file_path)
                return {
                    'text': text,
                    'method': 'pdf_direct',
                    'confidence': 0.95,
                    'status': 'success'
                }
            
            # DOCX extraction
            if extension in self.DOC_FORMATS and DOCX_AVAILABLE:
                doc = Document(file_path)
                text = '\n'.join([para.text for para in doc.paragraphs])
                return {
                    'text': text,
                    'method': 'docx_direct',
                    'confidence': 1.0,
                    'status': 'success'
                }
            
            raise ValueError(f"No direct extraction method for {extension}")
            
        except Exception as e:
            logger.error(f"Direct extraction failed: {str(e)}")
            return {
                'text': '',
                'method': 'direct_failed',
                'confidence': 0.0,
                'status': 'error',
                'error': str(e)
            }
    
    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF."""
        text_parts = []
        
        try:
            if PDFPLUMBER_AVAILABLE:
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
            elif PYPDF2_AVAILABLE:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text_parts.append(page.extract_text())
        except Exception as e:
            logger.error(f"PDF extraction error: {str(e)}")
            raise
        
        return '\n\n'.join(text_parts)
    
    def _extract_with_ocr_api(self, file_path: str) -> Dict[str, Any]:
        """Extract using OCR API."""
        try:
            result = self.ocr_client.extract_text(file_path)
            return {
                'text': result.get('text', ''),
                'method': 'ocr_api',
                'confidence': result.get('confidence', 0.0),
                'status': 'success',
                'provider': self.ocr_client.provider,
                'api_metadata': result.get('metadata', {})
            }
        except Exception as e:
            logger.error(f"OCR API extraction failed: {str(e)}")
            # Fallback to local OCR if API fails
            logger.info("Attempting fallback to local OCR...")
            return self._extract_with_local_ocr(file_path)
    
    def _extract_with_local_ocr(self, file_path: str) -> Dict[str, Any]:
        """Extract using local Tesseract OCR."""
        if not TESSERACT_AVAILABLE:
            return {
                'text': '',
                'method': 'ocr_local_unavailable',
                'confidence': 0.0,
                'status': 'error',
                'error': 'Tesseract not available'
            }
        
        try:
            file_path = Path(file_path)
            extension = file_path.suffix.lower()
            
            # Handle PDF -> Image conversion if needed
            if extension in self.PDF_FORMAT:
                # For now, return error - PDF to image conversion requires pdf2image
                return {
                    'text': '',
                    'method': 'ocr_local_pdf_unsupported',
                    'confidence': 0.0,
                    'status': 'error',
                    'error': 'Local OCR for PDF requires pdf2image package'
                }
            
            # OCR on image
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            
            return {
                'text': text,
                'method': 'ocr_local_tesseract',
                'confidence': 0.85,  # Estimated confidence
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Local OCR extraction failed: {str(e)}")
            return {
                'text': '',
                'method': 'ocr_local_failed',
                'confidence': 0.0,
                'status': 'error',
                'error': str(e)
            }
    
    def _assess_quality(self, text: str) -> float:
        """
        Assess the quality of extracted text.
        
        Returns:
            Quality score between 0 and 1
        """
        if not text or len(text.strip()) == 0:
            return 0.0
        
        score = 1.0
        
        # Check length
        if len(text) < 10:
            score *= 0.3
        
        # Check for reasonable character distribution
        alpha_count = sum(c.isalpha() for c in text)
        if len(text) > 0:
            alpha_ratio = alpha_count / len(text)
            if alpha_ratio < 0.3:  # Too few letters
                score *= 0.5
        
        # Check for excessive special characters (OCR artifacts)
        special_count = sum(not c.isalnum() and not c.isspace() for c in text)
        if len(text) > 0:
            special_ratio = special_count / len(text)
            if special_ratio > 0.3:  # Too many special chars
                score *= 0.6
        
        return min(score, 1.0)
    
    def _store_extraction(
        self,
        file_path: str,
        extraction_result: Dict[str, Any]
    ) -> Dict[str, str]:
        """Store extracted text and metadata."""
        file_name = Path(file_path).stem
        
        # Store text
        text_file = self.extraction_dir / f"{file_name}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(extraction_result.get('text', ''))
        
        # Store metadata
        metadata_file = self.extraction_dir / f"{file_name}_metadata.json"
        metadata = {
            'method': extraction_result.get('method'),
            'confidence': extraction_result.get('confidence'),
            'quality_score': extraction_result.get('quality_score'),
            'timestamp': extraction_result.get('timestamp'),
            'original_file': file_path
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Extraction stored: {text_file}")
        
        return {
            'text_file': str(text_file),
            'metadata_file': str(metadata_file)
        }
    
    def extract_batch(
        self,
        file_paths: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract text from multiple documents.
        
        Args:
            file_paths: List of document paths
            
        Returns:
            List of extraction results
        """
        results = []
        
        for file_path in file_paths:
            result = self.extract_from_document(file_path)
            results.append(result)
        
        # Generate summary
        successful = sum(1 for r in results if r.get('status') == 'success')
        logger.info(
            f"Batch extraction complete: {successful}/{len(file_paths)} successful"
        )
        
        return results
    
    def create_extraction_task(self, file_paths: List[str]) -> Task:
        """Create a CrewAI task for document extraction."""
        return Task(
            description=f"""Extract text from {len(file_paths)} documents intelligently:
            
            For each document:
            1. Analyze the document type and format
            2. Determine if OCR is needed or if direct extraction is possible
            3. Use the most appropriate extraction method
            4. Validate the quality of extracted text
            5. Store the results with metadata
            
            Documents to process:
            {', '.join([Path(p).name for p in file_paths])}
            
            Provide a summary of:
            - Total documents processed
            - Extraction methods used
            - Success rate
            - Any issues encountered
            """,
            expected_output="""A comprehensive report containing:
            1. Summary statistics
            2. List of successfully extracted documents with methods
            3. Quality scores for each extraction
            4. Any errors or warnings""",
            agent=self.agent
        )
