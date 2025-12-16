"""
Global logger configuration for KYC-AML Agentic AI Orchestrator.

This module provides a centralized logger that can be imported and used
throughout the application. The logger is configured from config/logging.json.
"""
import logging
import logging.config
from pathlib import Path
from .config_loader import config


def setup_global_logger():
    """Setup and configure the global logger from configuration."""
    # Create logs directory if it doesn't exist
    log_file = config.log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Get logging configuration
    logging_config = config.logging_config
    
    if logging_config:
        # Use dictConfig if available
        try:
            logging.config.dictConfig(logging_config)
        except Exception as e:
            # Fallback to basic config
            logging.basicConfig(
                level=getattr(logging, config.log_level.upper(), logging.INFO),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(log_file)
                ]
            )
            logging.warning(f"Failed to load logging config, using basic config: {e}")
    else:
        # Fallback to basic config
        logging.basicConfig(
            level=getattr(logging, config.log_level.upper(), logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file)
            ]
        )
    
    return logging.getLogger('kyc_aml_orchestrator')


# Initialize global logger
logger = setup_global_logger()


def get_logger(name: str = None):
    """Get a logger instance.
    
    Args:
        name: Logger name. If None, returns the main application logger.
        
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f'kyc_aml_orchestrator.{name}')
    return logger


__all__ = ['logger', 'get_logger']
