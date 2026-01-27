"""Supervisor Agent - Master coordinator for KYC document processing."""
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from agents.base_agent import BaseAgent
from agents.shared_memory import SharedMemory
from utilities import logger


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that coordinates all other agents.
    Implements dynamic workflow planning and adaptive execution.
    """
    
    def __init__(self, llm, specialist_agents: Dict[str, BaseAgent]):
        """
        Initialize supervisor agent.
        
        Args:
            llm: Language model
            specialist_agents: Dictionary of specialist agents {name: agent_instance}
        """
        super().__init__(name="Supervisor", role="Workflow Coordinator", llm=llm)
        self.specialist_agents = specialist_agents
    
    def process_request(self, user_request: str, case_reference: str,
                       shared_memory: Optional[SharedMemory] = None) -> Dict[str, Any]:
        """
        Main entry point: Process a user request end-to-end.
        
        Args:
            user_request: User's request in natural language
            case_reference: KYC case reference
            shared_memory: Optional existing shared memory
        
        Returns:
            Complete execution result with reasoning chain
        """
        # Create or use existing shared memory
        if shared_memory is None:
            shared_memory = SharedMemory(case_reference=case_reference)
        
        self.logger.info(f"[Supervisor] Processing request for case {case_reference}")
        
        # Supervisor's execution loop
        task = {
            'action': 'process_request',
            'user_request': user_request,
            'case_reference': case_reference
        }
        
        return self.execute(task, shared_memory)
    
    def _reason(self, observation: Dict[str, Any], task: Dict[str, Any],
                shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Supervisor analyzes the request and situation.
        """
        user_request = task.get('user_request', '')
        context = observation.get('context', {})
        
        prompt = f"""
You are the Supervisor Agent coordinating KYC document processing.

User Request: "{user_request}"

Current Case: {task.get('case_reference')}
Workflow Phase: {context.get('workflow_phase', 'unknown')}
Completed Steps: {context.get('completed_steps', [])}
Pending Steps: {context.get('pending_steps', [])}

Available Specialist Agents:
{self._format_available_agents()}

Analyze this request:
1. What is the user trying to accomplish?
2. What documents or actions are involved?
3. What's the current state of the case?
4. What processing is needed?
5. What's the priority level (urgent/normal/low)?
6. Are there any special requirements or constraints?

Return JSON:
{{
    "intent": "document_processing|query|status_check|case_management",
    "documents": ["list of document paths if any"],
    "required_processing": ["list of processing steps needed"],
    "priority": "urgent|normal|low",
    "special_requirements": ["any special handling needed"],
    "estimated_complexity": "simple|moderate|complex"
}}
"""
        
        response = self._invoke_llm(prompt)
        reasoning = self._parse_llm_response(response)
        
        self.logger.info(f"[Supervisor] Reasoning: {reasoning.get('intent', 'unknown')} - {reasoning.get('priority', 'normal')} priority")
        
        return reasoning
    
    def _plan(self, reasoning: Dict[str, Any], observation: Dict[str, Any],
              shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Supervisor creates dynamic workflow plan.
        """
        prompt = f"""
You are the Supervisor Agent creating an execution plan.

Analysis: {json.dumps(reasoning, indent=2)}

Available Agents and Capabilities:
{self._format_agent_capabilities()}

Current Workflow State:
- Phase: {observation['context'].get('workflow_phase')}
- Completed: {observation['context'].get('completed_steps', [])}
- Pending: {observation['context'].get('pending_steps', [])}

Create a step-by-step execution plan:

Return JSON array of steps:
[
    {{
        "step_id": "unique_id",
        "agent": "agent_name",
        "action": "action_to_perform",
        "parameters": {{}},
        "dependencies": ["step_ids this depends on"],
        "parallel_allowed": true/false,
        "error_handling": "retry|skip|fail_workflow",
        "description": "what this step does"
    }}
]

Guidelines:
- Order steps by dependencies
- Mark steps that can run in parallel
- Include validation/quality checks
- Plan for error scenarios
- Consider document types and requirements
"""
        
        response = self._invoke_llm(prompt)
        plan_data = self._parse_llm_response(response)
        
        # Ensure plan is a list
        if isinstance(plan_data, dict):
            plan_data = plan_data.get('steps', plan_data.get('plan', []))
        
        plan = {
            'steps': plan_data if isinstance(plan_data, list) else [],
            'created_at': self._get_timestamp(),
            'reasoning': reasoning
        }
        
        self.logger.info(f"[Supervisor] Created plan with {len(plan['steps'])} steps")
        
        # Update shared memory with plan
        shared_memory.update('execution_plan', plan, agent=self.name)
        shared_memory.update_workflow_state(phase='execution')
        
        return plan
    
    def _act(self, plan: Dict[str, Any], shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Supervisor executes the plan by delegating to specialist agents.
        """
        steps = plan.get('steps', [])
        if not steps:
            self.logger.warning("[Supervisor] No steps in plan, using default workflow")
            steps = self._create_default_workflow(shared_memory)
        
        results = {
            'completed_steps': [],
            'failed_steps': [],
            'skipped_steps': []
        }
        
        for step in steps:
            step_id = step.get('step_id', f"step_{len(results['completed_steps'])}")
            agent_name = step.get('agent', '')
            action = step.get('action', '')
            
            self.logger.info(f"[Supervisor] Executing step: {step_id} - {agent_name}.{action}")
            
            # Check dependencies
            dependencies = step.get('dependencies', [])
            if not self._check_dependencies(dependencies, results['completed_steps']):
                self.logger.warning(f"[Supervisor] Dependencies not met for {step_id}, skipping")
                results['skipped_steps'].append(step_id)
                continue
            
            # Get specialist agent
            agent = self.specialist_agents.get(agent_name)
            if not agent:
                self.logger.error(f"[Supervisor] Agent {agent_name} not found")
                results['failed_steps'].append({
                    'step_id': step_id,
                    'error': f'Agent {agent_name} not available'
                })
                
                # Handle error based on strategy
                if step.get('error_handling') == 'fail_workflow':
                    break
                continue
            
            # Execute agent task
            try:
                agent_task = {
                    'action': action,
                    'parameters': step.get('parameters', {}),
                    'step_id': step_id
                }
                
                result = agent.execute(agent_task, shared_memory)
                
                if result.get('status') == 'failed':
                    results['failed_steps'].append({
                        'step_id': step_id,
                        'agent': agent_name,
                        'error': result.get('error', 'Unknown error')
                    })
                    
                    # Adaptive error handling
                    if step.get('error_handling') == 'fail_workflow':
                        break
                    elif step.get('error_handling') == 'retry':
                        # Could implement retry logic here
                        pass
                else:
                    results['completed_steps'].append(step_id)
                    shared_memory.update_workflow_state(completed_step=step_id)
                
                results[step_id] = result
                
            except Exception as e:
                self.logger.error(f"[Supervisor] Step {step_id} failed: {e}")
                results['failed_steps'].append({
                    'step_id': step_id,
                    'error': str(e)
                })
        
        results['status'] = 'completed' if not results['failed_steps'] else 'partial'
        
        return results
    
    def _create_default_workflow(self, shared_memory: SharedMemory) -> List[Dict[str, Any]]:
        """Create a default workflow when LLM planning fails."""
        documents = shared_memory.get('documents', [])
        
        if not documents:
            return [
                {
                    'step_id': 'status_check',
                    'agent': 'intake',
                    'action': 'check_status',
                    'parameters': {},
                    'dependencies': [],
                    'error_handling': 'skip'
                }
            ]
        
        return [
            {
                'step_id': 'intake',
                'agent': 'intake',
                'action': 'validate_documents',
                'parameters': {'documents': documents},
                'dependencies': [],
                'error_handling': 'fail_workflow'
            },
            {
                'step_id': 'extraction',
                'agent': 'extraction',
                'action': 'extract_data',
                'parameters': {},
                'dependencies': ['intake'],
                'error_handling': 'skip'
            },
            {
                'step_id': 'classification',
                'agent': 'classification',
                'action': 'classify_documents',
                'parameters': {},
                'dependencies': ['intake'],
                'error_handling': 'retry'
            }
        ]
    
    def _check_dependencies(self, dependencies: List[str], completed: List[str]) -> bool:
        """Check if all dependencies are met."""
        return all(dep in completed for dep in dependencies)
    
    def _format_available_agents(self) -> str:
        """Format available agents for LLM prompt."""
        return "\n".join([
            f"- {name}: {agent.role}"
            for name, agent in self.specialist_agents.items()
        ])
    
    def _format_agent_capabilities(self) -> str:
        """Format agent capabilities for LLM prompt."""
        capabilities = []
        for name, agent in self.specialist_agents.items():
            capabilities.append(f"\n{name} ({agent.role}):")
            capabilities.append(f"  Can perform: document validation, metadata extraction, quality checks")
        return "\n".join(capabilities)
