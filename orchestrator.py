"""Main orchestrator for KYC-AML document processing using CrewAI."""
from crewai import Crew, Process
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from agents import DocumentIntakeAgent, DocumentClassifierAgent, ClassifierAPIClient
from utilities import config, settings, logger
import json


class KYCAMLOrchestrator:
    """Orchestrator for coordinating KYC-AML document processing agents."""
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        use_batch_classification: bool = False
    ):
        """
        Initialize the KYC-AML Orchestrator.
        
        Args:
            model_name: Name of the LLM model to use
            temperature: Temperature for LLM responses (lower = more deterministic)
            use_batch_classification: Whether to use batch classification endpoint
        """
        self.model_name = model_name or config.openai_model
        self.temperature = temperature
        self.use_batch_classification = use_batch_classification
        
        # Initialize LLM
        self.llm = self._initialize_llm()
        
        # Initialize agents
        self.intake_agent = DocumentIntakeAgent(llm=self.llm)
        self.classifier_agent = DocumentClassifierAgent(llm=self.llm)
        
        logger.info(f"Orchestrator initialized with model: {self.model_name}")
    
    def _initialize_llm(self):
        """Initialize the language model based on configuration."""
        provider = config.llm_provider
        
        # Google Gemini
        if provider == "google":
            return self._initialize_google_llm()
        
        # OpenAI
        elif provider == "openai" or config.openai_api_key:
            return self._initialize_openai_llm()
        
        raise ValueError(
            "No valid LLM configuration found. Please set OPENAI_API_KEY or GOOGLE_API_KEY in .env file."
        )
    
    def _initialize_google_llm(self):
        """Initialize Google Gemini with automatic fallback and model selection."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            import google.generativeai as genai
        except ImportError:
            logger.error("langchain-google-genai not installed. Run: pip install langchain-google-genai")
            raise
        
        google_config = config.get('llm.google', {})
        api_key = google_config.get('api_key')
        configured_model = google_config.get('model', 'gemini-pro')
        
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        
        # Try configured model first
        logger.info(f"Attempting to initialize Google Gemini: {configured_model}")
        
        try:
            llm = ChatGoogleGenerativeAI(
                model=configured_model,
                temperature=self.temperature,
                google_api_key=api_key
            )
            logger.info(f"✓ Successfully initialized: {configured_model}")
            return llm
        except Exception as e:
            logger.warning(f"Model '{configured_model}' not available: {str(e)}")
            logger.info("Fetching available Google models...")
            
            # Get available models
            genai.configure(api_key=api_key)
            available_models = []
            
            try:
                for model in genai.list_models():
                    if 'generateContent' in model.supported_generation_methods:
                        model_name = model.name.replace('models/', '')
                        available_models.append(model_name)
            except Exception as list_error:
                logger.error(f"Could not list models: {list_error}")
                raise
            
            if not available_models:
                raise ValueError("No Google Gemini models available")
            
            # Let user choose
            print("\n" + "="*70)
            print("📋 Available Google Gemini Models:")
            print("="*70)
            for i, model in enumerate(available_models, 1):
                print(f"  {i}. {model}")
            print("="*70)
            
            while True:
                try:
                    choice = input(f"\nChoose a model (1-{len(available_models)}) [default: 1]: ").strip()
                    if not choice:
                        choice = 1
                    else:
                        choice = int(choice)
                    
                    if 1 <= choice <= len(available_models):
                        selected_model = available_models[choice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(available_models)}")
                except ValueError:
                    print("Please enter a valid number")
            
            logger.info(f"User selected model: {selected_model}")
            
            # Initialize with selected model
            try:
                llm = ChatGoogleGenerativeAI(
                    model=selected_model,
                    temperature=self.temperature,
                    google_api_key=api_key
                )
                logger.info(f"✓ Successfully initialized: {selected_model}")
                print(f"\n✅ Using Google Gemini model: {selected_model}\n")
                return llm
            except Exception as init_error:
                logger.error(f"Failed to initialize {selected_model}: {init_error}")
                raise
    
    def _initialize_openai_llm(self):
        """Initialize OpenAI with automatic fallback and model selection."""
        from openai import OpenAI
        
        configured_model = self.model_name
        
        if not config.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        # Try configured model first
        logger.info(f"Attempting to initialize OpenAI: {configured_model}")
        
        try:
            llm = ChatOpenAI(
                model=configured_model,
                temperature=self.temperature,
                openai_api_key=config.openai_api_key
            )
            logger.info(f"✓ Successfully initialized: {configured_model}")
            return llm
        except Exception as e:
            if "does not exist" in str(e) or "model_not_found" in str(e):
                logger.warning(f"Model '{configured_model}' not available: {str(e)}")
                logger.info("Fetching available OpenAI models...")
                
                # Get available models
                try:
                    client = OpenAI(api_key=config.openai_api_key)
                    models = client.models.list()
                    
                    # Filter for chat models
                    available_models = []
                    for model in models.data:
                        if 'gpt' in model.id.lower() and not model.id.endswith('-instruct'):
                            available_models.append(model.id)
                    
                    available_models = sorted(available_models)
                    
                except Exception as list_error:
                    logger.error(f"Could not list models: {list_error}")
                    raise
                
                if not available_models:
                    raise ValueError("No OpenAI chat models available")
                
                # Show top 10 most common models
                common_models = [m for m in available_models if any(x in m for x in ['gpt-4o', 'gpt-3.5-turbo', 'gpt-4'])][:10]
                
                print("\n" + "="*70)
                print("📋 Available OpenAI Models (showing most common):")
                print("="*70)
                for i, model in enumerate(common_models, 1):
                    print(f"  {i}. {model}")
                print("="*70)
                
                while True:
                    try:
                        choice = input(f"\nChoose a model (1-{len(common_models)}) [default: 1]: ").strip()
                        if not choice:
                            choice = 1
                        else:
                            choice = int(choice)
                        
                        if 1 <= choice <= len(common_models):
                            selected_model = common_models[choice - 1]
                            break
                        else:
                            print(f"Please enter a number between 1 and {len(common_models)}")
                    except ValueError:
                        print("Please enter a valid number")
                
                logger.info(f"User selected model: {selected_model}")
                
                # Initialize with selected model
                try:
                    llm = ChatOpenAI(
                        model=selected_model,
                        temperature=self.temperature,
                        openai_api_key=config.openai_api_key
                    )
                    logger.info(f"✓ Successfully initialized: {selected_model}")
                    print(f"\n✅ Using OpenAI model: {selected_model}\n")
                    return llm
                except Exception as init_error:
                    logger.error(f"Failed to initialize {selected_model}: {init_error}")
                    raise
            else:
                # Other error, re-raise
                raise
    
    def process_documents(
        self,
        document_paths: List[str],
        process_type: str = "sequential"
    ) -> Dict[str, Any]:
        """
        Process documents through the intake and classification pipeline.
        
        Args:
            document_paths: List of document file paths to process
            process_type: CrewAI process type ("sequential" or "hierarchical")
            
        Returns:
            Processing results including intake and classification data
        """
        logger.info(f"Starting document processing for {len(document_paths)} documents")
        
        # Step 1: Document Intake
        logger.info("Step 1: Document Intake")
        intake_results = self.intake_agent.process_documents(document_paths)
        validated_documents = self.intake_agent.get_validated_documents(intake_results)
        
        logger.info(
            f"Intake complete: {len(validated_documents)}/{len(document_paths)} documents validated"
        )
        
        # Step 2: Document Classification
        if not validated_documents:
            logger.warning("No validated documents to classify")
            return {
                "status": "completed_with_warnings",
                "intake_results": intake_results,
                "classification_results": [],
                "summary": {
                    "total_documents": len(document_paths),
                    "validated": 0,
                    "classified": 0
                }
            }
        
        logger.info(f"Step 2: Document Classification for {len(validated_documents)} documents")
        
        if self.use_batch_classification:
            classification_results = self.classifier_agent.classify_documents_batch(
                validated_documents
            )
        else:
            classification_results = self.classifier_agent.classify_documents(
                validated_documents
            )
        
        # Generate summary
        if isinstance(classification_results, list):
            summary = self.classifier_agent.get_classification_summary(classification_results)
        else:
            summary = classification_results
        
        logger.info("Document processing completed")
        
        return {
            "status": "completed",
            "intake_results": intake_results,
            "classification_results": classification_results,
            "summary": {
                "total_documents": len(document_paths),
                "validated": len(validated_documents),
                "classification_summary": summary
            }
        }
    
    def process_with_crew(
        self,
        document_paths: List[str],
        process_type: str = "sequential"
    ) -> Dict[str, Any]:
        """
        Process documents using CrewAI's crew coordination.
        
        Args:
            document_paths: List of document file paths to process
            process_type: CrewAI process type ("sequential" or "hierarchical")
            
        Returns:
            Crew execution results
        """
        logger.info(f"Starting CrewAI orchestration for {len(document_paths)} documents")
        
        # First, do intake validation (not as a task, but as preparation)
        intake_results = self.intake_agent.process_documents(document_paths)
        validated_documents = self.intake_agent.get_validated_documents(intake_results)
        
        if not validated_documents:
            logger.warning("No validated documents to classify")
            return {
                "status": "no_valid_documents",
                "intake_results": intake_results,
                "message": "No documents passed validation"
            }
        
        # Create tasks
        intake_task = self.intake_agent.create_intake_task(document_paths)
        classification_task = self.classifier_agent.create_classification_task(
            validated_documents
        )
        
        # Create crew
        crew = Crew(
            agents=[self.intake_agent.agent, self.classifier_agent.agent],
            tasks=[intake_task, classification_task],
            process=Process.sequential if process_type == "sequential" else Process.hierarchical,
            verbose=True
        )
        
        # Execute crew
        logger.info("Executing CrewAI workflow")
        result = crew.kickoff()
        
        # Also get programmatic results
        classification_results = self.classifier_agent.classify_documents(validated_documents)
        
        return {
            "status": "completed",
            "crew_output": str(result),
            "intake_results": intake_results,
            "classification_results": classification_results,
            "summary": {
                "total_documents": len(document_paths),
                "validated": len(validated_documents),
                "classification_summary": self.classifier_agent.get_classification_summary(
                    classification_results
                )
            }
        }
    
    def check_classifier_health(self) -> bool:
        """
        Check if the classifier API is available.
        
        Returns:
            True if classifier is healthy, False otherwise
        """
        is_healthy = self.classifier_agent.api_client.health_check()
        if is_healthy:
            logger.info("Classifier API is healthy")
        else:
            logger.warning("Classifier API is not responding")
        return is_healthy
    
    def get_processing_summary(self, results: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of processing results.
        
        Args:
            results: Processing results dictionary
            
        Returns:
            Formatted summary string
        """
        summary = results.get("summary", {})
        
        output = f"""
╔═══════════════════════════════════════════════════════════╗
║        KYC-AML Document Processing Summary                ║
╚═══════════════════════════════════════════════════════════╝

Status: {results.get('status', 'unknown').upper()}

Documents:
  • Total Submitted: {summary.get('total_documents', 0)}
  • Validated: {summary.get('validated', 0)}

"""
        
        if "classification_summary" in summary:
            class_summary = summary["classification_summary"]
            output += f"""Classification Results:
  • Successfully Classified: {class_summary.get('successfully_classified', 0)}
  • Errors: {class_summary.get('errors', 0)}
  • Success Rate: {class_summary.get('success_rate', 0):.1f}%

Document Types Identified:
"""
            doc_types = class_summary.get('document_types', {})
            for doc_type, count in doc_types.items():
                output += f"  • {doc_type}: {count}\n"
        
        return output
