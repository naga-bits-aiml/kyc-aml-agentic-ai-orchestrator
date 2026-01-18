"""
Configuration loader for KYC-AML Agentic AI Orchestrator.

This module loads configuration from all JSON files in the config/ directory
and environment variables, making it available to all agents and modules.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import re
from dotenv import load_dotenv

# Load .env file at module import time
load_dotenv()


class ConfigLoader:
    """Load and manage application configuration from JSON files in config directory."""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        """Singleton pattern to ensure single config instance."""
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config_dir: str = "config"):
        """Initialize configuration loader.
        
        Args:
            config_dir: Directory containing configuration JSON files
        """
        if self._config is None:
            self.config_dir = config_dir
            self._load_config()
            self._create_directories()
    
    def _load_config(self):
        """Load and merge all JSON configuration files from config directory."""
        config_path = Path(self.config_dir)
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration directory not found: {self.config_dir}\n"
                "Please ensure the config/ directory exists with JSON files."
            )
        
        # Load all JSON files from config directory
        self._config = {}
        json_files = sorted(config_path.glob('*.json'))
        
        if not json_files:
            raise FileNotFoundError(
                f"No JSON configuration files found in: {self.config_dir}\n"
                "Please add at least one .json configuration file."
            )
        
        # Merge all JSON files
        for json_file in json_files:
            with open(json_file, 'r') as f:
                file_config = json.load(f)
                self._merge_config(self._config, file_config)
        
        # Replace environment variable placeholders
        self._config = self._resolve_env_vars(self._config)
    
    def _merge_config(self, base: Dict, update: Dict) -> None:
        """Recursively merge update dict into base dict.
        
        Args:
            base: Base configuration dictionary (modified in place)
            update: Configuration to merge into base
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _resolve_env_vars(self, config: Any) -> Any:
        """Recursively resolve environment variable placeholders in config.
        
        Replaces ${VAR_NAME} with the value from environment variable.
        """
        if isinstance(config, dict):
            return {k: self._resolve_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._resolve_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Match ${VAR_NAME} pattern
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, config)
            
            result = config
            for var_name in matches:
                env_value = os.getenv(var_name, "")
                result = result.replace(f"${{{var_name}}}", env_value)
            
            return result
        else:
            return config
    
    def _create_directories(self):
        """Create all required directories from config."""
        paths_config = self.get('paths', {})
        
        # Create document directories
        docs = paths_config.get('documents', {})
        for dir_path in docs.values():
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        # Create logs directory
        logs = paths_config.get('logs', {})
        if 'dir' in logs:
            Path(logs['dir']).mkdir(parents=True, exist_ok=True)
        
        # Create chat directories
        chat = paths_config.get('chat', {})
        for dir_path in chat.values():
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to config value (e.g., 'llm.openai.model')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
            
        Examples:
            >>> config.get('application.name')
            'KYC-AML Agentic AI Orchestrator'
            >>> config.get('llm.openai.model')
            'gpt-4-turbo-preview'
            >>> config.get('paths.documents.intake')
            'documents/intake'
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        
        return value
    
    def reload(self):
        """Reload configuration from all files in config directory."""
        self._config = None
        self._load_config()
        self._create_directories()
    
    def list_config_files(self) -> list:
        """List all configuration files loaded.
        
        Returns:
            List of configuration file names
        """
        config_path = Path(self.config_dir)
        if config_path.exists():
            return [f.name for f in sorted(config_path.glob('*.json'))]
        return []
    
    def get_path(self, key_path: str) -> Path:
        """Get a path configuration as Path object.
        
        Args:
            key_path: Dot-separated path to config value
            
        Returns:
            Path object
        """
        path_str = self.get(key_path, "")
        return Path(path_str).absolute()
    
    def get_all(self) -> Dict:
        """Get entire configuration dictionary."""
        return self._config.copy()
    
    def reload(self):
        """Reload configuration from file."""
        self._config = None
        self._load_config()
        self._create_directories()
    
    # Convenience properties for common configs
    @property
    def app_name(self) -> str:
        return self.get('application.name', 'KYC-AML Orchestrator')
    
    @property
    def app_version(self) -> str:
        return self.get('application.version', '1.0.0')
    
    @property
    def environment(self) -> str:
        return self.get('application.environment', 'development')
    
    @property
    def log_level(self) -> str:
        return self.get('log_settings.level', 'INFO')
    
    @property
    def log_file(self) -> Path:
        log_path = self.get('log_settings.log_file_path') or self.get('paths.logs.file')
        return Path(log_path).absolute() if log_path else Path('logs/kyc_aml_orchestrator.log').absolute()
    
    @property
    def log_format(self) -> str:
        return self.get('log_settings.log_format', 'detailed')
    
    @property
    def logging_config(self) -> Dict:
        """Get the complete logging configuration dictionary."""
        return self.get('logging', {})
    
    @property
    def intake_dir(self) -> Path:
        return self.get_path('paths.documents.intake')
    
    @property
    def processed_dir(self) -> Path:
        return self.get_path('paths.documents.processed')
    
    @property
    def archive_dir(self) -> Path:
        return self.get_path('paths.documents.archive')
    
    @property
    def temp_dir(self) -> Path:
        return self.get_path('paths.documents.temp')
    
    @property
    def metadata_file(self) -> Path:
        return self.get_path('paths.metadata.file_mapping')
    
    @property
    def max_document_size_mb(self) -> int:
        return self.get('document_validation.max_size_mb', 10)
    
    @property
    def max_document_size_bytes(self) -> int:
        return self.max_document_size_mb * 1024 * 1024
    
    @property
    def allowed_extensions(self) -> list:
        return self.get('document_validation.allowed_extensions', ['.pdf'])
    
    @property
    def openai_api_key(self) -> str:
        return self.get('llm.openai.api_key', '')
    
    @property
    def openai_model(self) -> str:
        return self.get('llm.openai.model', 'gpt-4-turbo-preview')
    
    @property
    def openai_temperature(self) -> float:
        return self.get('llm.openai.temperature', 0.1)
    
    @property
    def google_api_key(self) -> str:
        return self.get('llm.google.api_key', '')
    
    @property
    def google_model(self) -> str:
        return self.get('llm.google.model', 'gemini-2.5-flash')
    
    @property
    def google_temperature(self) -> float:
        return self.get('llm.google.temperature', 0.1)
    
    @property
    def classifier_api_url(self) -> str:
        return self.get('api.classifier.base_url', '')
    
    @property
    def classifier_api_key(self) -> str:
        return self.get('api.classifier.api_key', '')
    
    @property
    def classifier_timeout(self) -> int:
        return self.get('api.classifier.timeout', 30)
    
    @property
    def ocr_api_url(self) -> str:
        return self.get('api.ocr.base_url', '')
    
    @property
    def ocr_api_key(self) -> str:
        return self.get('api.ocr.api_key', '')
    
    @property
    def ocr_timeout(self) -> int:
        return self.get('api.ocr.timeout', 60)
    
    @property
    def ocr_provider(self) -> str:
        return self.get('api.ocr.provider', 'tesseract')
    
    @property
    def ocr_confidence_threshold(self) -> float:
        return self.get('api.ocr.confidence_threshold', 0.7)
    
    @property
    def llm_provider(self) -> str:
        return self.get('llm.provider', 'openai')


# Global configuration instance
config = ConfigLoader()


# Backward compatibility - create a settings-like object
class Settings:
    """Backward compatible settings object."""
    
    def __init__(self, config_instance: ConfigLoader):
        self._config = config_instance
    
    @property
    def log_level(self):
        return self._config.log_level
    
    @property
    def max_document_size_mb(self):
        return self._config.max_document_size_mb
    
    @property
    def max_document_size_bytes(self):
        return self._config.max_document_size_bytes
    
    @property
    def allowed_extensions(self):
        return self._config.allowed_extensions
    
    @property
    def openai_api_key(self):
        return self._config.openai_api_key
    
    @property
    def openai_model(self):
        return self._config.openai_model
    
    @property
    def model_name(self):
        return self._config.openai_model
    
    @property
    def google_api_key(self):
        return self._config.google_api_key
    
    @property
    def google_model(self):
        return self._config.google_model
    
    @property
    def google_temperature(self):
        return self._config.google_temperature
    
    @property
    def classifier_api_base_url(self):
        return self._config.classifier_api_url
    
    @property
    def classifier_api_key(self):
        return self._config.classifier_api_key
    
    @property
    def classifier_timeout(self):
        return self._config.classifier_timeout
    
    @property
    def ocr_api_base_url(self):
        return self._config.ocr_api_url
    
    @property
    def ocr_api_key(self):
        return self._config.ocr_api_key
    
    @property
    def ocr_timeout(self):
        return self._config.ocr_timeout
    
    @property
    def ocr_provider(self):
        return self._config.ocr_provider
    
    @property
    def documents_dir(self):
        """Root documents directory path."""
        return self._config.get_path('paths.documents.intake').parent
    
    @property
    def intake_dir(self):
        return self._config.intake_dir
    
    @property
    def processed_dir(self):
        return self._config.processed_dir
    
    @property
    def archive_dir(self):
        return self._config.archive_dir
    
    @property
    def temp_dir(self):
        return self._config.temp_dir


# Create backward compatible settings instance
settings = Settings(config)


__all__ = ['config', 'settings', 'ConfigLoader', 'Settings']
