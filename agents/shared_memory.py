"""Shared memory system for agent collaboration."""
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
from utilities import logger


class SharedMemory:
    """
    Shared context and communication system for agents.
    Implements a blackboard pattern where agents can:
    - Read/write shared data
    - Post messages to other agents
    - Track workflow state
    - Maintain execution history
    """
    
    def __init__(self, case_reference: Optional[str] = None):
        """Initialize shared memory for a case."""
        self.case_reference = case_reference
        self.data: Dict[str, Any] = {}
        self.agent_messages: List[Dict[str, Any]] = []
        self.workflow_state: Dict[str, Any] = {
            'current_phase': 'initialization',
            'completed_steps': [],
            'pending_steps': [],
            'failed_steps': []
        }
        self.execution_history: List[Dict[str, Any]] = []
        self.metadata_path = None
        
        if case_reference:
            self._load_or_initialize_metadata()
    
    def _load_or_initialize_metadata(self):
        """Load existing metadata or initialize new case."""
        from utilities import settings
        case_dir = Path(settings.documents_dir) / "cases" / self.case_reference
        self.metadata_path = case_dir / "workflow_memory.json"
        
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, 'r') as f:
                    saved_data = json.load(f)
                    self.data = saved_data.get('data', {})
                    self.workflow_state = saved_data.get('workflow_state', self.workflow_state)
                    self.execution_history = saved_data.get('execution_history', [])
                logger.info(f"Loaded workflow memory for case {self.case_reference}")
            except Exception as e:
                logger.error(f"Error loading workflow memory: {e}")
    
    def save(self):
        """Persist shared memory to disk."""
        if not self.metadata_path:
            return
        
        try:
            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
            
            data_to_save = {
                'case_reference': self.case_reference,
                'last_updated': datetime.now().isoformat(),
                'data': self.data,
                'workflow_state': self.workflow_state,
                'execution_history': self.execution_history[-100:],  # Keep last 100 entries
                'agent_messages': self.agent_messages[-50:]  # Keep last 50 messages
            }
            
            with open(self.metadata_path, 'w') as f:
                json.dump(data_to_save, f, indent=2, default=str)
            
            logger.debug(f"Saved workflow memory for case {self.case_reference}")
        except Exception as e:
            logger.error(f"Error saving workflow memory: {e}")
    
    def update(self, key: str, value: Any, agent: str):
        """
        Agent updates shared data.
        
        Args:
            key: Data key
            value: Data value
            agent: Agent name that made the update
        """
        previous_value = self.data.get(key, {}).get('value') if isinstance(self.data.get(key), dict) else None
        
        self.data[key] = {
            'value': value,
            'updated_by': agent,
            'timestamp': datetime.now().isoformat(),
            'version': self.data.get(key, {}).get('version', 0) + 1 if isinstance(self.data.get(key), dict) else 1
        }
        
        # Track change in history
        self.execution_history.append({
            'type': 'data_update',
            'key': key,
            'agent': agent,
            'previous_value': str(previous_value)[:100] if previous_value else None,
            'new_value': str(value)[:100],
            'timestamp': datetime.now().isoformat()
        })
        
        self.save()
        logger.debug(f"SharedMemory: {agent} updated '{key}'")
    
    def get(self, key: str, default=None) -> Any:
        """
        Retrieve value from shared memory.
        
        Args:
            key: Data key
            default: Default value if key not found
        
        Returns:
            Value associated with key
        """
        data = self.data.get(key)
        if isinstance(data, dict) and 'value' in data:
            return data['value']
        return default
    
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get full metadata for a key including version, timestamp, etc."""
        return self.data.get(key)
    
    def post_message(self, from_agent: str, to_agent: str, message: str, data: Optional[Dict] = None):
        """
        Post message from one agent to another.
        
        Args:
            from_agent: Sender agent name
            to_agent: Recipient agent name (or 'all' for broadcast)
            message: Message content
            data: Optional structured data
        """
        msg = {
            'from': from_agent,
            'to': to_agent,
            'message': message,
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'read': False
        }
        self.agent_messages.append(msg)
        
        self.execution_history.append({
            'type': 'agent_message',
            'from': from_agent,
            'to': to_agent,
            'message': message[:100],
            'timestamp': datetime.now().isoformat()
        })
        
        self.save()
        logger.debug(f"SharedMemory: {from_agent} → {to_agent}: {message[:50]}")
    
    def get_messages_for(self, agent: str, mark_read: bool = True) -> List[Dict[str, Any]]:
        """
        Get unread messages for an agent.
        
        Args:
            agent: Agent name
            mark_read: Whether to mark messages as read
        
        Returns:
            List of messages
        """
        messages = [
            msg for msg in self.agent_messages 
            if (msg['to'] == agent or msg['to'] == 'all') and not msg.get('read', False)
        ]
        
        if mark_read:
            for msg in messages:
                msg['read'] = True
            self.save()
        
        return messages
    
    def update_workflow_state(self, phase: Optional[str] = None, 
                            completed_step: Optional[str] = None,
                            pending_step: Optional[str] = None,
                            failed_step: Optional[str] = None):
        """
        Update workflow state.
        
        Args:
            phase: Current workflow phase
            completed_step: Step that was completed
            pending_step: Step to add to pending
            failed_step: Step that failed
        """
        if phase:
            self.workflow_state['current_phase'] = phase
        
        if completed_step:
            if completed_step not in self.workflow_state['completed_steps']:
                self.workflow_state['completed_steps'].append(completed_step)
            if completed_step in self.workflow_state['pending_steps']:
                self.workflow_state['pending_steps'].remove(completed_step)
        
        if pending_step:
            if pending_step not in self.workflow_state['pending_steps']:
                self.workflow_state['pending_steps'].append(pending_step)
        
        if failed_step:
            if failed_step not in self.workflow_state['failed_steps']:
                self.workflow_state['failed_steps'].append(failed_step)
        
        self.save()
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get summary of workflow state."""
        return {
            'phase': self.workflow_state['current_phase'],
            'completed': len(self.workflow_state['completed_steps']),
            'pending': len(self.workflow_state['pending_steps']),
            'failed': len(self.workflow_state['failed_steps']),
            'total_updates': len(self.execution_history)
        }
    
    def record_agent_action(self, agent: str, action: str, result: Dict[str, Any]):
        """
        Record an agent's action and result.
        
        Args:
            agent: Agent name
            action: Action performed
            result: Action result
        """
        self.execution_history.append({
            'type': 'agent_action',
            'agent': agent,
            'action': action,
            'status': result.get('status', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'summary': str(result.get('summary', ''))[:200]
        })
        self.save()
    
    def get_context_for_agent(self, agent: str) -> Dict[str, Any]:
        """
        Get relevant context for an agent.
        
        Args:
            agent: Agent name
        
        Returns:
            Dictionary with relevant context
        """
        return {
            'case_reference': self.case_reference,
            'workflow_phase': self.workflow_state['current_phase'],
            'completed_steps': self.workflow_state['completed_steps'],
            'pending_steps': self.workflow_state['pending_steps'],
            'recent_messages': self.get_messages_for(agent, mark_read=False),
            'shared_data_keys': list(self.data.keys()),
            'recent_actions': [
                h for h in self.execution_history[-10:] 
                if h.get('type') == 'agent_action'
            ]
        }
    
    def clear_messages(self):
        """Clear all messages."""
        self.agent_messages = []
        self.save()
