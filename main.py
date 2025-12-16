"""Main entry point for KYC-AML Agentic AI Orchestrator."""
import sys
from pathlib import Path
from typing import List
import argparse
import json
from orchestrator import KYCAMLOrchestrator
from utilities import config, settings, logger


def main():
    """Main function to run the KYC-AML orchestrator."""
    parser = argparse.ArgumentParser(
        description="KYC-AML Agentic AI Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single document
  python main.py --documents document.pdf

  # Process multiple documents
  python main.py --documents doc1.pdf doc2.jpg doc3.docx

  # Use batch classification
  python main.py --documents doc1.pdf doc2.pdf --batch

  # Use CrewAI workflow
  python main.py --documents doc1.pdf doc2.pdf --use-crew

  # Check classifier health
  python main.py --health-check
        """
    )
    
    parser.add_argument(
        "--documents",
        "-d",
        nargs="+",
        help="Paths to document files to process"
    )
    
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Use batch classification endpoint"
    )
    
    parser.add_argument(
        "--use-crew",
        action="store_true",
        help="Use CrewAI workflow orchestration"
    )
    
    parser.add_argument(
        "--model",
        default=config.openai_model,
        help=f"LLM model to use (default: {config.openai_model}). Recommended: gpt-4-turbo-preview, gpt-4, or gpt-3.5-turbo"
    )
    
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="LLM temperature (default: 0.1)"
    )
    
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Check classifier API health"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for results (JSON format)"
    )
    
    args = parser.parse_args()
    
    # Initialize orchestrator
    try:
        orchestrator = KYCAMLOrchestrator(
            model_name=args.model,
            temperature=args.temperature,
            use_batch_classification=args.batch
        )
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {str(e)}")
        print(f"\n❌ Error: {str(e)}")
        print("\nPlease ensure:")
        print("  1. You have created a .env file (copy from .env.example)")
        print("  2. You have set OPENAI_API_KEY in the .env file")
        print("  3. All required dependencies are installed (pip install -r requirements.txt)")
        return 1
    
    # Health check
    if args.health_check:
        print("\n🔍 Checking classifier API health...")
        is_healthy = orchestrator.check_classifier_health()
        if is_healthy:
            print("✅ Classifier API is healthy and responding")
            return 0
        else:
            print("❌ Classifier API is not responding")
            print(f"   Check that the service is running at: {config.classifier_api_url}")
            return 1
    
    # Validate documents argument
    if not args.documents:
        parser.print_help()
        print("\n❌ Error: No documents specified. Use --documents to provide file paths.")
        return 1
    
    # Validate document paths
    document_paths: List[str] = []
    for doc_path in args.documents:
        path = Path(doc_path)
        if not path.exists():
            logger.error(f"Document not found: {doc_path}")
            print(f"❌ Error: Document not found: {doc_path}")
            return 1
        document_paths.append(str(path.absolute()))
    
    print(f"\n📄 Processing {len(document_paths)} document(s)...")
    print(f"   Model: {args.model}")
    print(f"   Batch mode: {'Yes' if args.batch else 'No'}")
    print(f"   CrewAI mode: {'Yes' if args.use_crew else 'No'}")
    print()
    
    # Process documents
    try:
        if args.use_crew:
            results = orchestrator.process_with_crew(document_paths)
        else:
            results = orchestrator.process_documents(document_paths)
        
        # Print summary
        summary = orchestrator.get_processing_summary(results)
        print(summary)
        
        # Save to file if specified
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {output_path}")
        
        # Return appropriate exit code
        if results.get("status") == "completed":
            print("✅ Processing completed successfully")
            return 0
        else:
            print("⚠️  Processing completed with warnings")
            return 0
            
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}", exc_info=True)
        print(f"\n❌ Error during processing: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
