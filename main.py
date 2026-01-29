"""Main entry point for KYC-AML Agentic AI Orchestrator."""
import sys
from pathlib import Path
from typing import List
import argparse
import json
import uuid
from datetime import datetime

# Pure CrewAI orchestration
from flows import kickoff_flow
from crew import process_documents

from utilities import config, logger
from utilities.llm_factory import create_llm


def build_llm(model: str, temperature: float):
    """Build the LLM instance based on configured provider."""
    llm = create_llm(
        provider=config.llm_provider,
        model=model,
        temperature=temperature
    )
    logger.info(f"Using {config.llm_provider} provider with model {model}")
    return llm


def process_with_flow(
    case_id: str,
    document_paths: List[str],
    model: str,
    temperature: float = 0.1,
    visualize: bool = False
) -> dict:
    """
    Process documents using Flow-based CrewAI architecture.
    
    Args:
        case_id: Case identifier
        document_paths: List of document file paths
        model: LLM model name
        temperature: LLM temperature
        visualize: Whether to generate flow visualization
        
    Returns:
        Processing results dictionary
    """
    llm = build_llm(model=model, temperature=temperature)
    
    # Execute flow
    results = kickoff_flow(
        case_id=case_id,
        file_paths=document_paths,
        llm=llm,
        visualize=visualize,
        require_queue_confirmation=config.get('processing.require_queue_confirmation', False)
    )
    
    return results


def format_flow_summary(results: dict) -> str:
    """
    Format flow results into a human-readable summary.
    
    Args:
        results: Results from flow execution
        
    Returns:
        Formatted summary string
    """
    summary_lines = []
    summary_lines.append("\n" + "="*60)
    summary_lines.append("  PROCESSING SUMMARY")
    summary_lines.append("="*60)
    
    # Case info
    summary_lines.append(f"\n📋 Case ID: {results.get('case_id', 'N/A')}")
    summary_lines.append(f"📊 Status: {results.get('status', 'unknown').upper()}")
    
    # Processing time
    if results.get('processing_time'):
        summary_lines.append(f"⏱️  Processing Time: {results['processing_time']:.2f} seconds")
    
    # Document counts
    docs = results.get('documents', {})
    summary_lines.append(f"\n📄 Documents:")
    summary_lines.append(f"   Total: {docs.get('total', 0)}")
    summary_lines.append(f"   ✅ Successful: {docs.get('successful', 0)}")
    summary_lines.append(f"   ❌ Failed: {docs.get('failed', 0)}")
    summary_lines.append(f"   ⚠️  Requires Review: {docs.get('requires_review', 0)}")
    
    # Errors
    errors = results.get('errors', [])
    if errors:
        summary_lines.append(f"\n⚠️  Errors ({len(errors)}):")
        for i, error in enumerate(errors[:5], 1):  # Show first 5 errors
            summary_lines.append(f"   {i}. {error}")
        if len(errors) > 5:
            summary_lines.append(f"   ... and {len(errors) - 5} more")
    
    # Stage results
    if results.get('validated_documents'):
        summary_lines.append(f"\n✓ Intake: {len(results['validated_documents'])} documents validated")
    if results.get('classifications'):
        summary_lines.append(f"✓ Classification: {len(results['classifications'])} documents classified")
    if results.get('extractions'):
        summary_lines.append(f"✓ Extraction: {len(results['extractions'])} documents extracted")
    
    summary_lines.append("\n" + "="*60 + "\n")
    
    return "\n".join(summary_lines)


def normalize_results(result) -> dict:
    """Normalize crew/flow outputs into a dictionary."""
    if hasattr(result, "raw"):
        try:
            return json.loads(result.raw)
        except json.JSONDecodeError:
            return {"status": "unknown", "raw": str(result.raw)[:1000]}
    if isinstance(result, dict):
        return result
    return {"status": "unknown", "raw": str(result)[:1000]}


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
        help="Use the legacy CrewAI pipeline instead of the Flow-based orchestrator"
    )
    
    parser.add_argument(
        "--case-id",
        help="Case ID for document processing (auto-generated if not provided)"
    )
    
    parser.add_argument(
        "--visualize-flow",
        action="store_true",
        help="Generate flow visualization HTML file"
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
    
    # Health check for classifier API
    if args.health_check:
        print("\n🔍 Checking classifier API health...")
        from agents import ClassifierAPIClient
        client = ClassifierAPIClient()
        is_healthy = client.health_check()
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
    
    # Generate case ID if not provided
    case_id = args.case_id or f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    
    print(f"\n📄 Processing {len(document_paths)} document(s)...")
    print(f"   Case ID: {case_id}")
    print(f"   Model: {args.model}")
    print()
    
    # Process documents using CrewAI Flow
    try:
        if args.use_crew:
            llm = build_llm(model=args.model, temperature=args.temperature)
            results = normalize_results(
                process_documents(case_id=case_id, file_paths=document_paths, llm=llm)
            )
        else:
            results = process_with_flow(
                case_id=case_id,
                document_paths=document_paths,
                model=args.model,
                temperature=args.temperature,
                visualize=args.visualize_flow
            )
        
        # Print summary
        if "documents" in results:
            summary = format_flow_summary(results)
            print(summary)
        else:
            print(json.dumps(results, indent=2, default=str))
        
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
