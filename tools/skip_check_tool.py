"""
Skip Check Tool - Programmatic enforcement of smart resume logic
"""
from crewai.tools import tool
from utilities.logger import logger

@tool("check_if_stage_should_skip")
def check_if_stage_should_skip_tool(processing_mode: str, stage_status: str, stage_name: str) -> dict:
    """
    Check if the current stage should be skipped based on processing mode and status.
    
    This tool MUST be called first before any other work in each stage.
    It programmatically enforces the smart resume logic.
    
    Args:
        processing_mode: Either 'process' (skip successful stages) or 'reprocess' (run all)
        stage_status: Current status of the stage ('success', 'fail', 'pending', etc.)
        stage_name: Name of the stage (for logging purposes)
    
    Returns:
        dict with:
        - should_skip: boolean indicating if stage should be skipped
        - reason: explanation of the decision
        - log_message: message to log
    """
    
    # Evaluate skip condition
    should_skip = (processing_mode == 'process' and stage_status == 'success')
    
    if should_skip:
        log_message = f"[SMART RESUME] Skipping {stage_name} stage - already successful (mode={processing_mode}, status={stage_status})"
        logger.info(log_message)
        
        return {
            "should_skip": True,
            "reason": f"{stage_name.capitalize()} stage already completed successfully. Processing mode is 'process', so skipping to save computation.",
            "log_message": log_message,
            "action": "RETURN_IMMEDIATELY_WITH_SKIP_MESSAGE"
        }
    else:
        log_message = f"[PROCESSING] Executing {stage_name} stage (mode={processing_mode}, status={stage_status})"
        logger.info(log_message)
        
        return {
            "should_skip": False,
            "reason": f"Stage needs processing: mode={processing_mode}, status={stage_status}",
            "log_message": log_message,
            "action": "PROCEED_WITH_FULL_PROCESSING"
        }
