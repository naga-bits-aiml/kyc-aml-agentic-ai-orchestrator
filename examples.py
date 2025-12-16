"""
Example usage of the KYC-AML Agentic AI Orchestrator.

This script demonstrates various ways to use the orchestrator.
"""
from orchestrator import KYCAMLOrchestrator
from agents import DocumentIntakeAgent, DocumentClassifierAgent
from langchain_openai import ChatOpenAI
import json


def example_1_basic_processing():
    """Example 1: Basic document processing."""
    print("\n" + "="*60)
    print("Example 1: Basic Document Processing")
    print("="*60)
    
    # Initialize orchestrator
    orchestrator = KYCAMLOrchestrator(
        model_name="gpt-4-turbo-preview",
        temperature=0.1
    )
    
    # Process documents
    document_paths = [
        "sample_documents/passport.pdf",
        "sample_documents/utility_bill.jpg"
    ]
    
    results = orchestrator.process_documents(document_paths)
    
    # Print summary
    print(orchestrator.get_processing_summary(results))
    
    return results


def example_2_batch_processing():
    """Example 2: Batch processing with batch API endpoint."""
    print("\n" + "="*60)
    print("Example 2: Batch Processing")
    print("="*60)
    
    # Initialize with batch mode
    orchestrator = KYCAMLOrchestrator(
        model_name="gpt-4-turbo-preview",
        use_batch_classification=True
    )
    
    # Process multiple documents
    document_paths = [
        "sample_documents/passport.pdf",
        "sample_documents/license.jpg",
        "sample_documents/bank_statement.pdf",
        "sample_documents/utility_bill.jpg"
    ]
    
    results = orchestrator.process_documents(document_paths)
    
    print(orchestrator.get_processing_summary(results))
    
    return results


def example_3_crewai_workflow():
    """Example 3: Using CrewAI workflow orchestration."""
    print("\n" + "="*60)
    print("Example 3: CrewAI Workflow Orchestration")
    print("="*60)
    
    orchestrator = KYCAMLOrchestrator()
    
    document_paths = [
        "sample_documents/passport.pdf",
        "sample_documents/bank_statement.pdf"
    ]
    
    # Use CrewAI for coordinated workflow
    results = orchestrator.process_with_crew(
        document_paths=document_paths,
        process_type="sequential"
    )
    
    print("\n📋 CrewAI Output:")
    print(results.get("crew_output", ""))
    
    print(orchestrator.get_processing_summary(results))
    
    return results


def example_4_individual_agents():
    """Example 4: Using individual agents separately."""
    print("\n" + "="*60)
    print("Example 4: Individual Agent Usage")
    print("="*60)
    
    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.1)
    
    # Create agents
    intake_agent = DocumentIntakeAgent(llm=llm)
    classifier_agent = DocumentClassifierAgent(llm=llm)
    
    # Step 1: Intake
    print("\n📥 Step 1: Document Intake")
    document_paths = ["sample_documents/passport.pdf"]
    intake_results = intake_agent.process_documents(document_paths)
    
    print(f"Intake Results: {json.dumps(intake_results, indent=2, default=str)}")
    
    # Step 2: Get validated documents
    validated_docs = intake_agent.get_validated_documents(intake_results)
    print(f"\n✅ Validated Documents: {len(validated_docs)}")
    
    # Step 3: Classification
    print("\n🔍 Step 2: Document Classification")
    if validated_docs:
        classification_results = classifier_agent.classify_documents(validated_docs)
        print(f"Classification Results: {json.dumps(classification_results, indent=2, default=str)}")
        
        # Step 4: Summary
        summary = classifier_agent.get_classification_summary(classification_results)
        print(f"\n📊 Summary: {json.dumps(summary, indent=2)}")
    
    return {
        "intake_results": intake_results,
        "classification_results": classification_results if validated_docs else []
    }


def example_5_health_check():
    """Example 5: Health check for classifier API."""
    print("\n" + "="*60)
    print("Example 5: Classifier API Health Check")
    print("="*60)
    
    orchestrator = KYCAMLOrchestrator()
    
    print("\n🔍 Checking classifier API health...")
    is_healthy = orchestrator.check_classifier_health()
    
    if is_healthy:
        print("✅ Classifier API is healthy and responding")
    else:
        print("❌ Classifier API is not responding")
        print("   Please check the service configuration")
    
    return is_healthy


def example_6_error_handling():
    """Example 6: Handling errors and invalid documents."""
    print("\n" + "="*60)
    print("Example 6: Error Handling")
    print("="*60)
    
    orchestrator = KYCAMLOrchestrator()
    
    # Mix of valid and invalid documents
    document_paths = [
        "sample_documents/valid_doc.pdf",
        "nonexistent_file.pdf",  # This will fail
        "sample_documents/too_large.pdf",  # Might fail size validation
    ]
    
    results = orchestrator.process_documents(document_paths)
    
    print("\n📊 Results with errors:")
    print(orchestrator.get_processing_summary(results))
    
    # Check for errors
    intake_results = results.get("intake_results", [])
    failed_docs = [doc for doc in intake_results if not doc["validation"]["valid"]]
    
    if failed_docs:
        print("\n❌ Failed Documents:")
        for doc in failed_docs:
            print(f"  • {doc['file_path']}")
            print(f"    Errors: {doc['validation']['errors']}")
    
    return results


def example_7_save_results():
    """Example 7: Processing and saving results to file."""
    print("\n" + "="*60)
    print("Example 7: Save Results to File")
    print("="*60)
    
    orchestrator = KYCAMLOrchestrator()
    
    document_paths = [
        "sample_documents/passport.pdf",
        "sample_documents/utility_bill.jpg"
    ]
    
    results = orchestrator.process_documents(document_paths)
    
    # Save to JSON file
    output_file = "processing_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    print(orchestrator.get_processing_summary(results))
    
    return results


def main():
    """Run all examples."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║    KYC-AML Agentic AI Orchestrator - Example Usage        ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    examples = [
        ("Health Check", example_5_health_check),
        ("Basic Processing", example_1_basic_processing),
        ("Batch Processing", example_2_batch_processing),
        ("CrewAI Workflow", example_3_crewai_workflow),
        ("Individual Agents", example_4_individual_agents),
        ("Error Handling", example_6_error_handling),
        ("Save Results", example_7_save_results),
    ]
    
    print("\n📋 Available Examples:")
    for idx, (name, _) in enumerate(examples, 1):
        print(f"  {idx}. {name}")
    
    print("\n⚠️  Note: Make sure you have:")
    print("  • Created .env file with API keys")
    print("  • Sample documents in sample_documents/ directory")
    print("  • Classifier API service running")
    
    # Uncomment to run specific example
    # example_1_basic_processing()
    # example_2_batch_processing()
    # example_3_crewai_workflow()
    # example_4_individual_agents()
    # example_5_health_check()
    # example_6_error_handling()
    # example_7_save_results()


if __name__ == "__main__":
    main()
