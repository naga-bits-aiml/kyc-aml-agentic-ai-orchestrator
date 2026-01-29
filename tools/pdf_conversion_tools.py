"""
Production-Grade PDF to Image Conversion Tools.

Converts PDF documents to images in the intake folder and treats them as new documents.
Each converted image gets its own document ID and metadata, linked to the source PDF.

Features comprehensive logging of file generation.
"""
from crewai.tools import tool
from typing import Dict, Any, List, Optional
from pathlib import Path
from utilities import logger, settings, generate_document_id, compute_file_hash
import json
from datetime import datetime

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.warning("pdf2image not available. PDF conversion will be skipped.")


@tool("Convert PDF to Images")
def convert_pdf_to_images_tool(document_id: str, max_pages: int = 10) -> Dict[str, Any]:
    """
    Convert a PDF document to images and store them in the intake folder.
    Each image gets its own document ID and metadata, linked to the source PDF as child documents.
    
    The child image documents are tracked in the PDF's metadata under 'child_documents'.
    After the PDF completes its processing flow, the LLM should process these child documents.
    
    This is useful when:
    - PDF needs to be processed by image-based classification APIs
    - OCR needs to be performed on individual pages
    - Each page should be processed independently
    
    Args:
        document_id: Document ID of the PDF to convert (e.g., DOC_20260127_143022_A3F8B)
        max_pages: Maximum number of pages to convert (default: 10, prevents huge PDFs)
        
    Returns:
        Dictionary with conversion results:
        - success: Boolean indicating success
        - source_document_id: Original PDF document ID
        - child_documents: List of child image document IDs
        - total_pages: Total number of pages converted
        - message: Instructions for processing child documents
    """
    if not PDF2IMAGE_AVAILABLE:
        return {
            "success": False,
            "error": "pdf2image not available. Install with: pip install pdf2image",
            "source_document_id": document_id,
            "converted_images": []
        }
    
    logger.info(f"Converting PDF {document_id} to images")
    
    try:
        # Find the PDF document in intake stage
        intake_dir = Path(settings.documents_dir) / "intake"
        metadata_path = intake_dir / f"{document_id}.metadata.json"
        
        if not metadata_path.exists():
            return {
                "success": False,
                "error": f"Document {document_id} not found in intake stage",
                "source_document_id": document_id,
                "converted_images": []
            }
        
        # Load source document metadata
        with open(metadata_path, 'r') as f:
            source_metadata = json.load(f)
        
        pdf_path = Path(source_metadata['stored_path'])
        
        if not pdf_path.exists():
            return {
                "success": False,
                "error": f"PDF file not found: {pdf_path}",
                "source_document_id": document_id,
                "converted_images": []
            }
        
        # Check if it's actually a PDF
        if pdf_path.suffix.lower() != '.pdf':
            return {
                "success": False,
                "error": f"Document is not a PDF: {pdf_path.suffix}",
                "source_document_id": document_id,
                "converted_images": []
            }
        
        # Convert PDF to images
        logger.info(f"Converting {pdf_path} (max {max_pages} pages)")
        images = convert_from_path(
            str(pdf_path),
            dpi=200,
            first_page=1,
            last_page=max_pages,
            fmt='jpeg'
        )
        
        if not images:
            return {
                "success": False,
                "error": "No pages extracted from PDF",
                "source_document_id": document_id,
                "converted_images": []
            }
        
        # Store each image as a new document
        converted_images = []
        
        for page_num, image in enumerate(images, start=1):
            # Generate unique document ID for this image (each page gets its own ID)
            image_doc_id = generate_document_id()
            # Use just the document ID for filename (no _page suffix)
            image_filename = f"{image_doc_id}.jpg"
            image_path = intake_dir / image_filename
            
            # Save image
            image.save(str(image_path), 'JPEG', quality=85)
            
            # Compute file hash
            file_hash = compute_file_hash(str(image_path))
            file_size = image_path.stat().st_size
            
            # Create metadata for image document with proper stage blocks
            current_timestamp = datetime.now().isoformat()
            image_metadata = {
                "document_id": image_doc_id,
                "original_filename": f"{pdf_path.stem}_page{page_num}.jpg",
                "stored_filename": image_filename,
                "stored_path": str(image_path),
                "size_bytes": file_size,
                "extension": ".jpg",
                "file_hash": file_hash,
                "stage": "intake",
                "uploaded_at": current_timestamp,
                "linked_cases": [],
                "validation_status": "valid",
                "source_document_id": document_id,
                "source_document_type": "pdf",
                "page_number": page_num,
                "conversion_dpi": 200,
                "generated_from_pdf": True,
                # Stage-specific blocks for proper tracking
                "intake": {
                    "status": "success",
                    "msg": f"Generated from PDF conversion (page {page_num} of {document_id})",
                    "error": None,
                    "trace": None,
                    "timestamp": current_timestamp,
                    "additional_data": {
                        "source_document_id": document_id,
                        "source_document_type": "pdf",
                        "page_number": page_num,
                        "total_pages_in_pdf": len(images),
                        "conversion_dpi": 200,
                        "generation_method": "pdf2image"
                    }
                },
                "classification": {
                    "status": "pending",
                    "msg": None,
                    "error": None,
                    "trace": None,
                    "timestamp": None,
                    "additional_data": {}
                },
                "extraction": {
                    "status": "pending",
                    "msg": None,
                    "error": None,
                    "trace": None,
                    "timestamp": None,
                    "additional_data": {}
                }
            }
            
            # Save image metadata
            image_metadata_path = intake_dir / f"{image_doc_id}.metadata.json"
            with open(image_metadata_path, 'w') as f:
                json.dump(image_metadata, f, indent=2)
            
            converted_images.append({
                "document_id": image_doc_id,
                "page_number": page_num,
                "stored_path": str(image_path),
                "size_bytes": file_size
            })
            
            logger.info(f"Created image document {image_doc_id} for page {page_num}")
        
        # Update source PDF metadata to track child documents
        child_document_ids = [img["document_id"] for img in converted_images]
        source_metadata["child_documents"] = child_document_ids
        source_metadata["converted_to_images"] = True
        source_metadata["conversion_timestamp"] = datetime.now().isoformat()
        source_metadata["total_pages_converted"] = len(converted_images)
        
        with open(metadata_path, 'w') as f:
            json.dump(source_metadata, f, indent=2)
        
        # Log file generation with ALL details
        generated_file_paths = [img["stored_path"] for img in converted_images]
        generated_file_names = [Path(p).name for p in generated_file_paths]
        
        logger.critical(
            "\n" + "="*80 + "\n" +
            f"📄 FILES GENERATED: PDF to Image Conversion\n" +
            "="*80 + "\n" +
            f"Source PDF: {pdf_path.name}\n" +
            f"Source Path: {pdf_path}\n" +
            f"Source Document ID: {document_id}\n" +
            f"Pages Converted: {len(converted_images)}\n" +
            f"DPI: 200\n" +
            f"Format: JPEG\n" +
            f"Child Document IDs:\n" +
            "\n".join([f"  - {doc_id}" for doc_id in child_document_ids]) + "\n" +
            f"Generated Files:\n" +
            "\n".join([f"  - {name}" for name in generated_file_names]) + "\n" +
            "="*80
        )
        
        logger.info(f"Successfully converted {len(converted_images)} pages from {document_id}")
        logger.info(f"Child documents tracked in PDF metadata: {child_document_ids}")
        
        return {
            "success": True,
            "source_document_id": document_id,
            "child_documents": child_document_ids,
            "total_pages": len(converted_images),
            "skipped_pages": 0,
            "message": f"Created {len(converted_images)} child image documents. These should be processed after the PDF completes its flow."
        }
        
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        logger.exception("Full traceback:")
        return {
            "success": False,
            "error": str(e),
            "source_document_id": document_id,
            "converted_images": []
        }


@tool("Check If PDF Needs Conversion")
def check_pdf_conversion_needed_tool(document_id: str) -> Dict[str, Any]:
    """
    Check if a document is a PDF that needs conversion to images.
    
    Args:
        document_id: Document ID to check
        
    Returns:
        Dictionary with:
        - needs_conversion: Boolean indicating if PDF conversion is needed
        - document_id: The document ID
        - is_pdf: Boolean indicating if document is a PDF
        - already_converted: Boolean indicating if already converted
    """
    try:
        # Find document in intake stage
        intake_dir = Path(settings.documents_dir) / "intake"
        metadata_path = intake_dir / f"{document_id}.metadata.json"
        
        if not metadata_path.exists():
            return {
                "needs_conversion": False,
                "document_id": document_id,
                "is_pdf": False,
                "already_converted": False,
                "error": "Document not found in intake stage"
            }
        
        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        is_pdf = metadata.get("extension", "").lower() == ".pdf"
        already_converted = "converted_to_images" in metadata
        
        return {
            "needs_conversion": is_pdf and not already_converted,
            "document_id": document_id,
            "is_pdf": is_pdf,
            "already_converted": already_converted
        }
        
    except Exception as e:
        logger.error(f"Failed to check PDF conversion status: {e}")
        return {
            "needs_conversion": False,
            "document_id": document_id,
            "is_pdf": False,
            "already_converted": False,
            "error": str(e)
        }
