"""
Supervisor Agent - Orchestrates multi-step command execution.

Implements the Plan-and-Execute pattern:
1. PLAN: Parse user input into atomic steps with dependencies
2. EXECUTE: Delegate each step to the appropriate crew/agent
3. REPORT: Provide consolidated results

Architecture:
    Supervisor
        ├── knows → Agents (what they do, not how)
        │               └── Agents know → Tools (implementation)
        └── knows → Crews (groups of agents for tasks)

Configuration: config/supervisor_agent.yaml
"""

import json
import re
import yaml
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime
from utilities import logger, settings
from utilities.llm_factory import create_llm


def _load_config() -> Dict[str, Any]:
    """Load supervisor configuration from YAML."""
    config_path = Path(__file__).parent.parent / "config" / "supervisor_agent.yaml"
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        agent_config = config.get('agent', {})
        return {
            'role': agent_config.get('role', 'Orchestration Supervisor'),
            'goal': agent_config.get('goal', ''),
            'backstory': agent_config.get('backstory', ''),
            'planning_prompt': config.get('planning_prompt', ''),
            'actions': config.get('actions', {}),
            'crews': config.get('crews', {}),
            'agents': config.get('agents', {}),
            'execution': config.get('execution', {})
        }
    except Exception as e:
        logger.warning(f"Failed to load supervisor config: {e}")
        return {}


class ActionType(Enum):
    """Action types - mapped from config."""
    CREATE_CASE = "create_case"
    SWITCH_CASE = "switch_case"
    PROCESS_DOCUMENTS = "process_documents"
    PROCESS_FOLDER = "process_folder"
    CLASSIFY = "classify"
    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    LIST_CASES = "list_cases"
    LIST_DOCUMENTS = "list_documents"
    GET_STATUS = "get_status"
    LINK_DOCUMENT = "link_document"
    UNKNOWN = "unknown"


@dataclass
class ExecutionStep:
    """A single step in the execution plan."""
    step_id: int
    action: ActionType
    args: Dict[str, Any]
    depends_on: Optional[int] = None
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None


@dataclass
class ExecutionPlan:
    """Complete execution plan for a user request."""
    user_input: str
    steps: List[ExecutionStep] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "created"


class SupervisorAgent:
    """
    Orchestrates multi-step command execution by delegating to crews/agents.
    
    The supervisor only knows WHAT agents/crews can do, not HOW they do it.
    All implementation details are encapsulated within the agents themselves.
    """
    
    def __init__(self, chat_interface=None):
        self.chat_interface = chat_interface
        self.llm = create_llm()
        self.current_plan: Optional[ExecutionPlan] = None
        self.pending_plan: Optional[ExecutionPlan] = None  # Plan waiting for user response
        self.pending_action: Optional[str] = None  # What we're waiting for (e.g., 'case_reference')
        
        # Load all configuration from YAML
        self.config = _load_config()
        self.role = self.config.get('role', '')
        self.goal = self.config.get('goal', '')
        self.backstory = self.config.get('backstory', '')
        self.planning_prompt = self.config.get('planning_prompt', '')
        self.actions = self.config.get('actions', {})
        self.crews = self.config.get('crews', {})
        self.agents = self.config.get('agents', {})
        self.execution_settings = self.config.get('execution', {})
        
        # Lazy-loaded pipeline crew
        self._pipeline_crew = None
    
    # ==================== PUBLIC API ====================
    
    def process_command(self, user_input: str) -> str:
        """Main entry point - process a user command."""
        try:
            # Check if we're waiting for user response (e.g., case reference)
            if self.pending_plan and self.pending_action == 'case_reference':
                return self._handle_pending_case_response(user_input)
            
            # Create execution plan
            self.current_plan = self._create_plan(user_input)
            
            if not self.current_plan.steps:
                return self._handle_simple_query(user_input)
            
            # Check if plan requires a case but none is set
            case_prompt = self._check_case_requirement()
            if case_prompt:
                return case_prompt
            
            # Execute and format results
            plan_summary = self._format_plan()
            results = self._execute_plan()
            return self._format_results(plan_summary, results)
            
        except Exception as e:
            logger.error(f"Supervisor error: {e}")
            return f"❌ Error: {str(e)}"
    
    # ==================== PLANNING ====================
    
    def _create_plan(self, user_input: str) -> ExecutionPlan:
        """Parse user input into an execution plan using LLM."""
        plan = ExecutionPlan(user_input=user_input)
        
        # Use LLM with planning prompt from config
        parsed_actions = self._parse_command(user_input)
        
        for i, action_data in enumerate(parsed_actions, 1):
            try:
                action_type = ActionType(action_data.get("action", "unknown"))
            except ValueError:
                action_type = ActionType.UNKNOWN
            
            step = ExecutionStep(
                step_id=i,
                action=action_type,
                args=action_data.get("args", {}),
                depends_on=action_data.get("depends_on")
            )
            plan.steps.append(step)
        
        return plan
    
    def _parse_command(self, user_input: str) -> List[Dict[str, Any]]:
        """Use LLM to parse user command into structured actions."""
        if not self.planning_prompt:
            return []
        
        current_case = getattr(self.chat_interface, 'case_reference', None) or "Not set"
        prompt = self.planning_prompt.format(
            user_input=user_input,
            current_case=current_case
        )
        
        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON array from response
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                return json.loads(json_match.group())
            return []
            
        except Exception as e:
            logger.warning(f"Command parsing failed: {e}")
            return []
    
    # ==================== CASE REQUIREMENT CHECK ====================
    
    def _check_case_requirement(self) -> Optional[str]:
        """
        Check if the plan requires a case but none is set.
        Returns a prompt asking user for case reference, or None if OK to proceed.
        """
        if not self.current_plan or not self.current_plan.steps:
            return None
        
        current_case = getattr(self.chat_interface, 'case_reference', None)
        
        # Check if plan already has a create_case or switch_case step
        has_case_step = any(
            step.action in (ActionType.CREATE_CASE, ActionType.SWITCH_CASE)
            for step in self.current_plan.steps
        )
        
        if has_case_step or current_case:
            return None  # Case is handled
        
        # Check if any step requires a case AND doesn't already have one in args
        requires_case_actions = []
        for step in self.current_plan.steps:
            action_cfg = self.actions.get(step.action.value, {})
            if action_cfg.get('requires_case', False):
                # Skip if step already has a case_reference in its args
                if step.args.get('case_reference'):
                    continue
                requires_case_actions.append(step.action.value)
        
        if not requires_case_actions:
            return None  # No case required (all steps have case_reference or don't need one)
        
        # Store pending plan and prompt user
        self.pending_plan = self.current_plan
        self.pending_action = 'case_reference'
        
        # Build user prompt
        actions_str = ", ".join(set(requires_case_actions))
        return (
            f"📋 **Case Required**\n\n"
            f"The following actions require a case: **{actions_str}**\n\n"
            f"Would you like to:\n"
            f"1. **Create a new case** - Enter a case ID (e.g., `KYC_2026_004`)\n"
            f"2. **Use existing case** - Enter an existing case ID\n"
            f"3. **Skip case linking** - Type `skip` to process documents without a case\n\n"
            f"👉 Please enter your choice:"
        )
    
    def _handle_pending_case_response(self, user_input: str) -> str:
        """Handle user response when we were waiting for case reference."""
        user_input = user_input.strip()
        
        if not self.pending_plan:
            self.pending_action = None
            return "❌ No pending action. Please try your request again."
        
        # User wants to skip case linking
        if user_input.lower() in ('skip', 'no', 'none', 'cancel'):
            self.current_plan = self.pending_plan
            self.pending_plan = None
            self.pending_action = None
            
            # Execute without case - remove case requirements from plan
            logger.info("User chose to skip case linking")
            plan_summary = self._format_plan()
            results = self._execute_plan()
            return self._format_results(plan_summary, results)
        
        # User provided a case reference
        case_ref = user_input.upper().replace('-', '_').replace(' ', '_')
        
        # Validate case reference format (basic check)
        if not re.match(r'^[A-Z0-9_]+$', case_ref):
            return (
                f"⚠️ Invalid case reference format: `{user_input}`\n\n"
                f"Please use alphanumeric characters and underscores (e.g., `KYC_2026_004`)\n"
                f"Or type `skip` to process without a case."
            )
        
        # Create or switch to the case
        case_result = self._create_or_switch_case(case_ref)
        
        if not case_result.get('success'):
            return f"❌ Failed to set case: {case_result.get('error', 'Unknown error')}"
        
        # Update ALL pending plan steps to use the case reference
        for step in self.pending_plan.steps:
            step.args['case_reference'] = case_ref
        
        # Execute the pending plan
        self.current_plan = self.pending_plan
        self.pending_plan = None
        self.pending_action = None
        
        is_new = case_result.get('is_new', False)
        case_status = "created" if is_new else "switched to"
        
        logger.info(f"Case {case_ref} {case_status}, executing pending plan")
        
        plan_summary = f"📁 Case **{case_ref}** {case_status}.\n\n" + self._format_plan()
        results = self._execute_plan()
        return self._format_results(plan_summary, results)
    
    # ==================== EXECUTION ====================
    
    def _execute_plan(self) -> List[Dict[str, Any]]:
        """Execute all steps, respecting dependencies."""
        results = []
        
        for step in self.current_plan.steps:
            # Skip if dependency failed
            if step.depends_on:
                dep = next((s for s in self.current_plan.steps if s.step_id == step.depends_on), None)
                if dep and dep.status == "failed":
                    step.status = "skipped"
                    step.error = f"Dependency (step {step.depends_on}) failed"
                    results.append({"step": step.step_id, "status": "skipped", "error": step.error})
                    continue
            
            # Execute step
            step.status = "running"
            try:
                step.result = self._delegate(step)
                step.status = "completed"
                results.append({"step": step.step_id, "status": "completed", "result": step.result})
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                results.append({"step": step.step_id, "status": "failed", "error": str(e)})
                logger.error(f"Step {step.step_id} failed: {e}")
        
        self.current_plan.status = "failed" if any(s.status == "failed" for s in self.current_plan.steps) else "completed"
        return results
    
    def _delegate(self, step: ExecutionStep) -> Any:
        """Delegate step execution based on handler type from config."""
        action_cfg = self.actions.get(step.action.value, {})
        handler = action_cfg.get('handler', 'direct')
        
        if handler == 'crew':
            return self._delegate_to_crew(step, action_cfg)
        elif handler == 'flow':
            return self._delegate_to_flow(step)
        else:
            return self._handle_direct(step)
    
    def _delegate_to_crew(self, step: ExecutionStep, action_cfg: Dict) -> Dict[str, Any]:
        """Delegate execution to a CrewAI crew."""
        crew_name = action_cfg.get('crew')
        if not crew_name:
            return {"success": False, "error": f"No crew configured for {step.action.value}"}
        
        # Lazy-load pipeline crew (let it create its own CrewAI-compatible LLM)
        if self._pipeline_crew is None:
            from pipeline_crew import DocumentProcessingCrew
            self._pipeline_crew = DocumentProcessingCrew()  # Uses config-based CrewAI LLM
        
        crew_info = self.crews.get(crew_name, {})
        logger.info(f"Delegating to {crew_name}: {crew_info.get('description', '')}")
        
        try:
            crew_method = getattr(self._pipeline_crew, crew_name, None)
            if not crew_method:
                return {"success": False, "error": f"Crew '{crew_name}' not found"}
            
            result = crew_method().kickoff(inputs=step.args)
            return {"success": True, "crew": crew_name, "result": result}
        except Exception as e:
            logger.error(f"Crew execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _delegate_to_flow(self, step: ExecutionStep) -> Dict[str, Any]:
        """Delegate execution to DocumentProcessingFlow."""
        from pipeline_flow import run_pipeline_sync
        
        # Case reference from step args (user-provided) or chat interface
        case_ref = step.args.get('case_reference') or getattr(self.chat_interface, 'case_reference', None)
        
        if step.action == ActionType.PROCESS_FOLDER:
            folder = step.args.get("folder_path")
            if not folder:
                return {"success": False, "error": "No folder path provided"}
            
            path = Path(folder).expanduser().resolve()
            if not path.exists():
                return {"success": False, "error": f"Folder not found: {folder}"}
            
            return run_pipeline_sync(input_path=str(path), case_reference=case_ref)
        
        elif step.action == ActionType.PROCESS_DOCUMENTS:
            file_paths = step.args.get("file_paths", [])
            results = []
            for fp in file_paths:
                p = Path(fp).expanduser().resolve()
                if p.exists():
                    results.append(run_pipeline_sync(input_path=str(p), case_reference=case_ref))
                else:
                    results.append({"success": False, "error": f"File not found: {fp}"})
            return {"success": True, "documents_processed": len(results), "results": results}
        
        return {"success": False, "error": f"No flow handler for {step.action.value}"}
    
    def _handle_direct(self, step: ExecutionStep) -> Dict[str, Any]:
        """Handle actions that don't require crew/flow delegation."""
        action = step.action
        args = step.args
        
        if action in (ActionType.CREATE_CASE, ActionType.SWITCH_CASE):
            return self._create_or_switch_case(args.get("case_reference"))
        
        elif action == ActionType.LIST_CASES:
            return self._list_cases()
        
        elif action == ActionType.GET_STATUS:
            return self._get_status()
        
        elif action == ActionType.SUMMARIZE:
            return self._generate_summary(args.get("case_reference"))
        
        elif action == ActionType.LIST_DOCUMENTS:
            return self._list_documents(args.get("case_reference"))
        
        return {"success": False, "error": f"Unknown action: {action.value}"}
    
    # ==================== DIRECT HANDLERS ====================
    
    def _create_or_switch_case(self, case_reference: str) -> Dict[str, Any]:
        """Create or switch to a case."""
        if not case_reference:
            return {"success": False, "error": "No case reference provided"}
        
        case_ref = case_reference.upper().replace('-', '_')
        
        if self.chat_interface and hasattr(self.chat_interface, 'set_case_reference'):
            result = self.chat_interface.set_case_reference(case_ref)
            return {"success": True, "case_reference": case_ref, "message": result}
        
        # Fallback: create case directory
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        is_new = not case_dir.exists()
        case_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_file = case_dir / "case_metadata.json"
        if not metadata_file.exists():
            metadata = {
                "case_reference": case_ref,
                "created_date": datetime.now().isoformat(),
                "status": "active"
            }
            metadata_file.write_text(json.dumps(metadata, indent=2))
        
        return {"success": True, "case_reference": case_ref, "is_new": is_new}
    
    def _list_cases(self) -> Dict[str, Any]:
        """List all cases."""
        cases_dir = Path(settings.documents_dir) / "cases"
        if not cases_dir.exists():
            return {"success": True, "cases": [], "count": 0}
        
        cases = [
            {"case_reference": d.name, "document_count": max(0, len(list(d.glob("*.*"))) - 1)}
            for d in sorted(cases_dir.iterdir()) if d.is_dir()
        ]
        return {"success": True, "cases": cases, "count": len(cases)}
    
    def _get_status(self) -> Dict[str, Any]:
        """Get system status."""
        from tools.queue_tools import get_queue_status
        return {
            "success": True,
            "status": {
                "llm": "connected" if self.llm else "not connected",
                "current_case": getattr(self.chat_interface, 'case_reference', None),
                "queue": get_queue_status()
            }
        }
    
    def _generate_summary(self, case_reference: str = None) -> Dict[str, Any]:
        """Generate case summary using case-aware summary tool."""
        case_ref = case_reference or getattr(self.chat_interface, 'case_reference', None)
        if not case_ref:
            return {"success": False, "error": "No case reference available"}
        
        # Check config - if handler is 'crew', delegate to crew
        action_cfg = self.actions.get('summarize', {})
        if action_cfg.get('handler') == 'crew':
            step = ExecutionStep(step_id=0, action=ActionType.SUMMARIZE, args={"case_reference": case_ref})
            return self._delegate_to_crew(step, action_cfg)
        
        # Use case-aware summary tool directly
        from tools.case_summary_tools import generate_comprehensive_case_summary_tool
        result = generate_comprehensive_case_summary_tool.run(case_id=case_ref)
        return {"success": result.get("success", False), "case_reference": case_ref, "summary": result}
    
    def _list_documents(self, case_reference: str = None) -> Dict[str, Any]:
        """List documents."""
        from tools.metadata_tools import list_all_metadata
        # list_all_metadata is a @tool decorated function, need to invoke it properly
        if hasattr(list_all_metadata, 'invoke'):
            result = list_all_metadata.invoke({})
        elif hasattr(list_all_metadata, 'run'):
            result = list_all_metadata.run()
        else:
            # Direct function call as fallback
            result = list_all_metadata._run() if hasattr(list_all_metadata, '_run') else {"documents": [], "count": 0}
        
        if case_reference:
            result["documents"] = [
                d for d in result.get("documents", [])
                if case_reference in d.get("linked_cases", [])
            ]
            result["count"] = len(result["documents"])
        
        return result
    
    # ==================== FORMATTING ====================
    
    def _handle_simple_query(self, user_input: str) -> str:
        """Handle queries that don't need a plan."""
        if self.chat_interface and hasattr(self.chat_interface, 'get_llm_response'):
            return self.chat_interface.get_llm_response(user_input)
        return "I couldn't understand that command. Try 'help' for available commands."
    
    def _format_plan(self) -> str:
        """Format execution plan for display."""
        if not self.current_plan or not self.current_plan.steps:
            return ""
        
        lines = ["📋 **Execution Plan:**", ""]
        for step in self.current_plan.steps:
            dep = f" (after step {step.depends_on})" if step.depends_on else ""
            lines.append(f"   {step.step_id}. {step.action.value}{dep}")
            for key, value in step.args.items():
                lines.append(f"      └─ {key}: {value}")
        return "\n".join(lines)
    
    def _format_results(self, plan_summary: str, results: List[Dict]) -> str:
        """Format execution results for display."""
        lines = [plan_summary, "", "🚀 **Execution Results:**", ""]
        
        full_summary = None  # Store full case summary for display at end
        
        for r in results:
            status = r["status"]
            emoji = {"completed": "✅", "failed": "❌", "skipped": "⏭️"}.get(status, "❓")
            result_data = r.get("result", {})
            
            # Check if this is a summarize step with full summary
            if status == "completed" and isinstance(result_data, dict) and "summary" in result_data:
                summary = result_data.get("summary", {})
                if isinstance(summary, dict) and summary.get("success"):
                    full_summary = summary  # Save for display at end
                    detail = f"Case summary generated for {result_data.get('case_reference', 'case')}"
                else:
                    detail = self._summarize_result(result_data)
            elif status == "completed":
                detail = self._summarize_result(result_data)
            else:
                detail = r.get("error", status)
            
            lines.append(f"   {emoji} Step {r['step']}: {detail}")
        
        completed = sum(1 for r in results if r["status"] == "completed")
        failed = sum(1 for r in results if r["status"] == "failed")
        
        lines.append("")
        lines.append(f"✨ **All {completed} steps completed!**" if failed == 0 else f"⚠️ **{completed} completed, {failed} failed**")
        
        # Append full case summary if available
        if full_summary:
            lines.append("")
            lines.append(self._format_case_summary(full_summary))
        return "\n".join(lines)
    
    def _format_case_summary(self, summary: Dict[str, Any]) -> str:
        """Format full case summary for display."""
        lines = ["📊 **Case Summary:**", ""]
        
        case_summary = summary.get("case_summary", {})
        if isinstance(case_summary, dict):
            # Primary entity
            primary = case_summary.get("primary_entity", {})
            if primary:
                lines.append(f"**Primary Entity:** {primary.get('name', 'Unknown')} ({primary.get('entity_type', 'unknown')})")
                lines.append("")
            
            # Persons
            persons = case_summary.get("persons", [])
            if persons:
                lines.append("**Persons Identified:**")
                for person in persons:
                    name = person.get("name", "Unknown")
                    pan = person.get("pan_number", "")
                    dob = person.get("dob", "")
                    details = []
                    if pan:
                        details.append(f"PAN: {pan}")
                    if dob:
                        details.append(f"DOB: {dob}")
                    lines.append(f"   • {name}" + (f" ({', '.join(details)})" if details else ""))
                lines.append("")
            
            # Organizations
            orgs = case_summary.get("organizations", [])
            if orgs:
                lines.append("**Organizations:**")
                for org in orgs:
                    lines.append(f"   • {org.get('name', 'Unknown')}")
                lines.append("")
            
            # KYC Verification Status
            kyc = case_summary.get("kyc_verification", {})
            if kyc:
                identity = "✅ Verified" if kyc.get("identity_verified") else "❌ Not Verified"
                lines.append(f"**KYC Status:** Identity {identity}")
                missing = kyc.get("missing_documents", [])
                if missing:
                    lines.append(f"   Missing: {', '.join(missing)}")
                lines.append("")
            
            # Narrative summary
            narrative = case_summary.get("summary", "")
            if narrative:
                lines.append("**Summary:**")
                lines.append(f"   {narrative}")
        
        # Document count
        doc_count = summary.get("document_count", 0)
        lines.append("")
        lines.append(f"**Documents Processed:** {doc_count}")
        
        return "\n".join(lines)
    
    def _summarize_result(self, result: Any) -> str:
        """Create brief summary of a result."""
        if not isinstance(result, dict):
            return str(result)[:100]
        
        # Case summary with empty case - provide friendly message
        if "summary" in result and isinstance(result.get("summary"), dict):
            summary = result["summary"]
            # Empty case - no documents yet
            if summary.get("error") == "No documents found in case":
                case_ref = result.get("case_reference", "case")
                return f"Case {case_ref} is ready (no documents yet)"
        
        # Handle summary tool result that failed due to empty case
        if result.get("error") == "No documents found in case":
            case_ref = result.get("case_reference", "case")
            return f"Case {case_ref} is ready (no documents yet)"
        
        # Pipeline processing result - has summary.statistics
        if "summary" in result and isinstance(result["summary"], dict):
            summary = result["summary"]
            # Check if it's a pipeline summary (has statistics) or a case summary (has case_summary)
            if "statistics" in summary:
                stats = summary["statistics"]
                total = stats.get("total_documents", 0)
                completed = stats.get("completed", 0)
                failed = stats.get("failed", 0)
                if total > 0:
                    return f"Processed {completed}/{total} documents" + (f" ({failed} failed)" if failed > 0 else "")
            # Case summary - has case_summary with primary_entity
            elif "case_summary" in summary or "primary_entity" in summary:
                case_summary = summary.get("case_summary", summary)
                if isinstance(case_summary, dict):
                    primary = case_summary.get("primary_entity", {})
                    entity_name = primary.get("name", "Unknown")
                    entity_type = primary.get("entity_type", "entity")
                    doc_count = summary.get("document_count", result.get("document_count", 0))
                    return f"Case summary for {entity_name} ({entity_type}) - {doc_count} document(s)"
        
        if "case_reference" in result and "summary" not in result:
            return f"Case: {result['case_reference']}"
        if "processed_documents" in result:
            count = len(result["processed_documents"]) if isinstance(result["processed_documents"], list) else result["processed_documents"]
            return f"Processed {count} documents"
        if "documents_processed" in result:
            return f"Processed {result['documents_processed']} documents"
        if "cases" in result:
            return f"Found {result.get('count', 0)} cases"
        if "success" in result:
            return "Success" if result["success"] else result.get("error", "Failed")
        return str(result)[:100]


def create_supervisor(chat_interface=None) -> SupervisorAgent:
    """Create a supervisor agent instance."""
    return SupervisorAgent(chat_interface=chat_interface)
