# Utilities Package

This package contains all utility modules for the KYC-AML Agentic AI Orchestrator.

## 📦 Modules

### [config_loader.py](config_loader.py)
Configuration loader that loads and merges all JSON files from the `config/` directory.

**Key Classes:**
- `ConfigLoader` - Singleton class that loads configuration
- `Settings` - Backward compatible settings object

**Exports:**
- `config` - Global configuration instance
- `settings` - Backward compatible settings

**Usage:**
```python
from utilities import config

# Get configuration values
model = config.openai_model
intake_dir = config.intake_dir
log_level = config.log_level
```

### [logger.py](logger.py)
Global logger configuration module.

**Key Functions:**
- `setup_global_logger()` - Initialize logger from config
- `get_logger(name)` - Get module-specific logger

**Exports:**
- `logger` - Global application logger
- `get_logger` - Function to get module-specific logger

**Usage:**
```python
from utilities import logger, get_logger

# Use global logger
logger.info("Processing started")

# Get module-specific logger
my_logger = get_logger('my_module')
my_logger.debug("Debug info")
```

### [utils.py](utils.py)
General utility functions for file operations and validation.

**Functions:**
- `validate_file_extension(filename, allowed_extensions)` - Check file extension
- `validate_file_size(file_path, max_size_bytes)` - Check file size
- `compute_file_hash(file_path)` - Calculate SHA256 hash
- `calculate_file_hash(file_path)` - Alias for compute_file_hash
- `create_document_metadata(file_path)` - Generate document metadata
- `ensure_directory(directory_path)` - Create directory if not exists

**Usage:**
```python
from utilities import validate_file_extension, ensure_directory

# Validate file
is_valid = validate_file_extension('doc.pdf', ['.pdf', '.docx'])

# Ensure directory exists
ensure_directory('documents/intake')
```

## 🎯 Package Structure

```
utilities/
├── __init__.py           # Package exports
├── config_loader.py      # Configuration loading
├── logger.py             # Global logging
├── utils.py              # General utilities
└── README.md             # This file
```

## 📝 Importing from Utilities

### Import Everything You Need
```python
from utilities import (
    config,              # Configuration
    settings,            # Backward compatible settings
    logger,              # Global logger
    get_logger,          # Get module logger
    validate_file_extension,
    validate_file_size,
    ensure_directory,
)
```

### Import Specific Modules
```python
from utilities.config_loader import ConfigLoader
from utilities.logger import logger
from utilities.utils import compute_file_hash
```

## 🔧 Configuration

The configuration loader automatically:
1. Loads all `.json` files from `config/` directory
2. Merges them into a single configuration object
3. Resolves environment variable placeholders (`${VAR_NAME}`)
4. Creates necessary directories
5. Provides convenient properties for common settings

## 📊 Logging

The logger module:
1. Loads logging configuration from `config/logging.json`
2. Sets up formatters and handlers
3. Configures log rotation
4. Provides module-specific loggers
5. Falls back to basic config if needed

## ✅ Best Practices

1. **Import from package root**: Use `from utilities import ...` instead of individual modules
2. **Use global instances**: Use `config` and `logger` instances exported from package
3. **Module-specific logging**: Use `get_logger('module_name')` for module-specific logs
4. **Type hints**: All functions include type hints for better IDE support

## 🔄 Migration from Old Imports

**Old:**
```python
from config_loader import config
from logger import logger
from utils import validate_file_extension
```

**New:**
```python
from utilities import config, logger, validate_file_extension
```

---

All utility functionality is now organized in this package for better modularity and maintainability!
