#!/usr/bin/env python3
"""
Document Processing Pipeline - Main CLI Entry Point

This script provides the command-line interface for running the CrewAI-based
document processing pipeline.

Usage:
    python pipeline_main.py /path/to/document.pdf
    python pipeline_main.py /path/to/folder --verbose
    python pipeline_main.py /path/to/folder --dry-run
    python pipeline_main.py /path/to/file.jpg --output /custom/output/dir
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utilities import setup_logging, get_logger

# Initialize logging
setup_logging()
logger = get_logger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Document Processing Pipeline - Process documents through classification and extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process a single document
    python pipeline_main.py /path/to/document.pdf
    
    # Process all documents in a folder
    python pipeline_main.py /path/to/documents/
    
    # Dry run - show what would be processed without actually processing
    python pipeline_main.py /path/to/folder --dry-run
    
    # Verbose output for debugging
    python pipeline_main.py /path/to/file.jpg --verbose
    
    # Custom output directory
    python pipeline_main.py /path/to/file.jpg --output /custom/output
    
    # Use async Flow (default)
    python pipeline_main.py /path/to/folder --async
    
    # Use synchronous processing
    python pipeline_main.py /path/to/folder --sync
        """
    )
    
    parser.add_argument(
        "input_path",
        type=str,
        help="Path to a single document file or a folder containing documents"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output directory for processed documents (default: documents/)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output for debugging"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually processing"
    )
    
    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        default=True,
        help="Use async Flow orchestration (default)"
    )
    
    parser.add_argument(
        "--sync",
        dest="use_sync",
        action="store_true",
        help="Use synchronous processing"
    )
    
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts for failed API calls (default: 3)"
    )
    
    parser.add_argument(
        "--skip-classification",
        action="store_true",
        help="Skip classification stage (use for pre-classified documents)"
    )
    
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip extraction stage"
    )
    
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume processing from existing queue state"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom configuration file"
    )
    
    return parser.parse_args()


def validate_input_path(input_path: str) -> Path:
    """Validate the input path exists and is accessible."""
    path = Path(input_path).resolve()
    
    if not path.exists():
        logger.error(f"Input path does not exist: {path}")
        sys.exit(1)
    
    if path.is_file():
        # Validate file extension
        valid_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
        if path.suffix.lower() not in valid_extensions:
            logger.error(f"Unsupported file type: {path.suffix}")
            logger.info(f"Supported types: {', '.join(sorted(valid_extensions))}")
            sys.exit(1)
    
    return path


def dry_run(input_path: Path) -> None:
    """Perform a dry run showing what would be processed."""
    from tools.queue_tools import scan_input_path
    
    logger.info("=" * 60)
    logger.info("DRY RUN - No documents will be processed")
    logger.info("=" * 60)
    
    result = scan_input_path(str(input_path))
    
    if not result.get("success"):
        logger.error(f"Scan failed: {result.get('error')}")
        return
    
    files = result.get("files", [])
    total_size = result.get("total_size_bytes", 0)
    
    print(f"\nInput Path: {input_path}")
    print(f"Type: {'File' if input_path.is_file() else 'Directory'}")
    print(f"Total Files: {len(files)}")
    print(f"Total Size: {total_size / 1024 / 1024:.2f} MB")
    print(f"\nFiles to be processed:")
    print("-" * 50)
    
    for i, file_path in enumerate(files, 1):
        file = Path(file_path)
        size_kb = file.stat().st_size / 1024
        print(f"  {i:3}. {file.name} ({size_kb:.1f} KB)")
    
    print("-" * 50)
    print(f"\nEstimated processing steps:")
    print(f"  1. Build queue: {len(files)} documents")
    print(f"  2. Classification: {len(files)} API calls")
    print(f"  3. Extraction: {len(files)} API calls")
    print(f"  4. Summary generation: 1 report")
    print(f"\nTotal API calls: {len(files) * 2}")
    
    # Check for PDFs that will be split
    pdfs = [f for f in files if f.lower().endswith('.pdf')]
    if pdfs:
        print(f"\nNote: {len(pdfs)} PDF file(s) will be split into page images")
        print("      Actual processing count may be higher")


def run_pipeline_async(input_path: Path, args: argparse.Namespace) -> dict:
    """Run the pipeline using async Flow orchestration."""
    from pipeline_flow import run_pipeline
    
    logger.info("Starting async Flow-based pipeline...")
    
    try:
        result = asyncio.run(run_pipeline(str(input_path)))
        return result
    except Exception as e:
        logger.error(f"Async pipeline failed: {e}")
        return {"success": False, "error": str(e)}


def run_pipeline_sync(input_path: Path, args: argparse.Namespace) -> dict:
    """Run the pipeline using synchronous crew execution."""
    from pipeline_flow import run_pipeline_sync as sync_runner
    
    logger.info("Starting synchronous pipeline...")
    
    try:
        result = sync_runner(str(input_path))
        return result
    except Exception as e:
        logger.error(f"Sync pipeline failed: {e}")
        return {"success": False, "error": str(e)}


def print_summary(result: dict) -> None:
    """Print processing summary to console."""
    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)
    
    if not result.get("success", False):
        print(f"\n❌ Pipeline failed: {result.get('error', 'Unknown error')}")
        return
    
    summary = result.get("summary", {})
    stats = summary.get("statistics", {})
    
    print(f"\n📊 Processing Statistics:")
    print(f"   Total Documents: {stats.get('total_documents', 0)}")
    print(f"   ✅ Completed: {stats.get('completed', 0)}")
    print(f"   ❌ Failed: {stats.get('failed', 0)}")
    print(f"   ⏭️  Skipped: {stats.get('skipped', 0)}")
    
    if stats.get("completed", 0) > 0:
        print(f"\n📋 Classification Results:")
        by_type = summary.get("by_document_type", {})
        for doc_type, count in by_type.items():
            print(f"   {doc_type}: {count}")
    
    duration = result.get("duration_seconds", 0)
    print(f"\n⏱️  Processing Time: {duration:.1f} seconds")
    
    output_path = result.get("output_path")
    if output_path:
        print(f"\n📁 Output Location: {output_path}")
    
    report_path = result.get("report_path")
    if report_path:
        print(f"📝 Report: {report_path}")


def main() -> int:
    """Main entry point for the pipeline CLI."""
    args = parse_arguments()
    
    # Set log level based on verbosity
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Print banner
    print("\n" + "=" * 60)
    print("  Document Processing Pipeline")
    print("  CrewAI Multi-Agent Orchestration")
    print("=" * 60)
    
    start_time = datetime.now()
    
    # Validate input
    input_path = validate_input_path(args.input_path)
    logger.info(f"Input path: {input_path}")
    
    # Handle dry run
    if args.dry_run:
        dry_run(input_path)
        return 0
    
    # Run the pipeline
    try:
        if args.use_sync:
            result = run_pipeline_sync(input_path, args)
        else:
            result = run_pipeline_async(input_path, args)
        
        # Add timing info
        end_time = datetime.now()
        result["duration_seconds"] = (end_time - start_time).total_seconds()
        
        # Print summary
        print_summary(result)
        
        # Return appropriate exit code
        if result.get("success", False):
            return 0
        else:
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
        logger.warning("Pipeline interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Pipeline failed with exception: {e}")
        print(f"\n❌ Pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
