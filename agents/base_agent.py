"""Base agent class with reasoning capabilities."""
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import json
from utilities import logger
from agents.shared_memory import SharedMemory


class BaseAgent(ABC):
    """
    Base class for autonomous agents.
    Implements the Observe-Reason-Plan-Act-Reflect loop.
    """
    
    def __init__(self, name: str, role: str, llm):
        """
        Initialize base agent.
        
        Args:
            name: Agent name
            role: Agent role/specialty
            llm: Language model instance
        """
        self.name = name
        self.role = role
        self.llm = llm
        self.logger = logger
    
    def execute(self, task: Dict[str, Any], shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Main execution loop: Observe → Reason → Plan → Act → Reflect.
        
        Args:
            task: Task to execute
            shared_memory: Shared memory for context and communication
        
        Returns:
            Execution result with reasoning chain
        """
        self.logger.info(f"[{self.name}] Starting execution")
        
        try:
            # OBSERVE: Gather context
            observation = self._observe(task, shared_memory)
            
            # REASON: Analyze situation
            reasoning = self._reason(observation, task, shared_memory)
            
            # PLAN: Create action plan
            plan = self._plan(reasoning, observation, shared_memory)
            
            # ACT: Execute the plan
            execution_result = self._act(plan, shared_memory)
            
            # REFLECT: Evaluate results
            reflection = self._reflect(execution_result, plan, shared_memory)
            
            # Record in shared memory
            result = {
                'status': execution_result.get('status', 'completed'),
                'agent': self.name,
                'observation': observation,
                'reasoning': reasoning,
                'plan': plan,
                'execution': execution_result,
                'reflection': reflection,
                'next_steps': reflection.get('suggestions', [])
            }
            
            shared_memory.record_agent_action(self.name, task.get('action', 'execute'), result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"[{self.name}] Execution failed: {e}", exc_info=True)
            return {
                'status': 'failed',
                'agent': self.name,
                'error': str(e),
                'task': task
            }
    
    def _observe(self, task: Dict[str, Any], shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        OBSERVE: Gather relevant context and information.
        
        Args:
            task: Current task
            shared_memory: Shared memory
        
        Returns:
            Observations dictionary
        """
        context = shared_memory.get_context_for_agent(self.name)
        messages = shared_memory.get_messages_for(self.name, mark_read=False)
        
        return {
            'task': task,
            'context': context,
            'messages': messages,
            'timestamp': self._get_timestamp()
        }
    
    @abstractmethod
    def _reason(self, observation: Dict[str, Any], task: Dict[str, Any], 
                shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        REASON: Analyze the situation and determine what needs to be done.
        Must be implemented by concrete agent classes.
        
        Args:
            observation: Observations from observe phase
            task: Current task
            shared_memory: Shared memory
        
        Returns:
            Reasoning result
        """
        pass
    
    @abstractmethod
    def _plan(self, reasoning: Dict[str, Any], observation: Dict[str, Any],
              shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        PLAN: Create a detailed action plan.
        Must be implemented by concrete agent classes.
        
        Args:
            reasoning: Reasoning from reason phase
            observation: Observations
            shared_memory: Shared memory
        
        Returns:
            Action plan
        """
        pass
    
    @abstractmethod
    def _act(self, plan: Dict[str, Any], shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        ACT: Execute the action plan.
        Must be implemented by concrete agent classes.
        
        Args:
            plan: Action plan from plan phase
            shared_memory: Shared memory
        
        Returns:
            Execution result
        """
        pass
    
    def _reflect(self, execution_result: Dict[str, Any], plan: Dict[str, Any],
                 shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        REFLECT: Evaluate execution and suggest next steps.
        
        Args:
            execution_result: Result from execution
            plan: Original plan
            shared_memory: Shared memory
        
        Returns:
            Reflection and suggestions
        """
        prompt = f"""
As {self.role}, reflect on this execution:

Plan: {json.dumps(plan, indent=2)}

Execution Result: {json.dumps(execution_result, indent=2)}

Reflection questions:
1. Did the execution succeed? Any issues?
2. Was the plan appropriate? What could be improved?
3. Are there any concerns or quality issues?
4. What should happen next?
5. Should other agents be notified?

Provide structured reflection with:
- success: bool
- quality_score: 0-1
- issues: list of issues found
- suggestions: list of next steps
- notify_agents: dict of {{agent_name: message}}
"""
        
        try:
            response = self._invoke_llm(prompt)
            reflection = self._parse_llm_response(response)
            
            # Send messages to other agents if suggested
            if 'notify_agents' in reflection and reflection['notify_agents']:
                for agent_name, message in reflection['notify_agents'].items():
                    shared_memory.post_message(
                        from_agent=self.name,
                        to_agent=agent_name,
                        message=message
                    )
            
            return reflection
        except Exception as e:
            self.logger.error(f"[{self.name}] Reflection failed: {e}", exc_info=True)
            return {
                'success': execution_result.get('status') == 'success',
                'quality_score': 0.5,
                'issues': [str(e)],
                'suggestions': ['Review execution manually']
            }
    
    def _invoke_llm(self, prompt: str) -> str:
        """Invoke LLM with prompt."""
        try:
            response = self.llm.invoke(prompt)
            if hasattr(response, 'content'):
                content = response.content
                if isinstance(content, list):
                    return ''.join([
                        item.get('text', '') if isinstance(item, dict) else str(item)
                        for item in content
                    ])
                return str(content)
            return str(response)
        except Exception as e:
            self.logger.error(f"[{self.name}] LLM invocation failed: {e}")
            return "{}"
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to structured data."""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            # Fallback: return raw response
            return {'raw_response': response}
        except Exception as e:
            self.logger.error(f"[{self.name}] Failed to parse LLM response: {e}")
            return {'raw_response': response}
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
