# Configuration Guide

## � JSON Configuration Directory

All application settings are organized in the `config/` directory with separate JSON files for different concerns.

## 🚀 Quick Start

### 1. Configuration Files

The `config/` directory contains multiple JSON files:

- **config/app.json** - Application settings, validation rules
- **config/paths.json** - File paths and directories  
- **config/llm.json** - Language model configurations
- **config/api.json** - External API settings
- **config/logging.json** - Logging configuration

**Example - config/app.json:**
```json
{
  "application": {
    "name": "KYC-AML Agentic AI Orchestrator",
    "environment": "development"
  }
}
```

**Example - config/paths.json:**
```json
{
  "paths": {
    "documents": {
      "intake": "documents/intake",
      "processed": "documents/processed"
    }
  }
}
```

All files are automatically loaded and merged!

###any config file (e.g., `config/llm.json`)nt Variables

For sensitive data (API keys), use environment variables:

```env
OPENAI_API_KEY=your_key_here
CLASSIFIER_API_KEY=your_key_here
```

In `config.json`, reference them with `${VAR_NAME}`:

```json
{
  "llm": {
    "openai": {
      "api_key": "${OPENAI_API_KEY}"
    }
  }
}
```

### 3. Usage in Code

```python
from utilities import config

# Get any config value using dot notation
model = config.get('llm.openai.model')
intake_path = config.get('paths.documents.intake')

# Or use convenience properties
model = config.openai_model
intake_dir = config.intake_dir
```

## 🎯 Configuration Files

### config/app.json - Application Settings
```json
{
  "application": {
    "name": "App Name",
    "version": "1.0.0",
    "environment": "development",  // development, staging, production
    "log_level": "INFO"             // DEBUG, INFO, WARNING, ERROR
  }
}
```

### config/paths.json - File Paths (Configurable!)
```json
{
  "paths": {
    "documents": {
      "intake": "documents/intake",      // Where uploaded docs are stored
      "processed": "documents/processed", // Classified documents
      "archive": "documents/archive",     // Archived documents
      "temp": "documents/temp"            // Temporary files
    },
    "metadata": {
      "file_mapping": "documents/intake/file_metadata.json"
    },
    "logs": {
      "dir": "logs",
      "file": "logs/kyc_aml_orchestrator.log"
    }
  }
}
```

### config/logging.json - Logging Configuration
```json
{
  "log_settings": {
    "level": "INFO",
    "enable_file_logging": true,
    "log_file_path": "logs/kyc_aml_orchestrator.log",
    "max_log_size_mb": 10,
    "backup_count": 5
  },
  "logging": {
    "formatters": {
      "default": {
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
      }
    },
    "handlers": {
      "console": {
        "class": "logging.StreamHandler",
        "level": "INFO",
        "formatter": "default"
      },
      "file": {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": "logs/kyc_aml_orchestrator.log",
        "maxBytes": 10485760,
        "backupCount": 5
      }
    }
  }
}
```

### config/app.json - Document Validation
```json
{
  "document_validation": {
    "max_size_mb": 10,
    "allowed_extensions": [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc"]
  }
}
```

### config/llm.json - LLM Configuration
```json
{
  "llm": {
    "provider": "openai",  // openai, azure, anthropic, ollama
    "openai": {
      "api_key": "${OPENAI_API_KEY}",
      "model": "gpt-4-turbo-preview",
      "temperature": 0.1
    }
  }
}
```

### config/api.json - API Configuration
```json
{
  "api": {
    "classifier": {
      "base_url": "http://35.184.130.36/api/kyc_document_classifier/v1",
      "api_key": "${CLASSIFIER_API_KEY}",
      "timeout": 30
    }
  }
}
```

## 📝 Usage Examples

### Get Config Values

```python
from utilities import config

# Using dot notation
app_name = config.get('application.name')
log_level = config.get('log_settings.level')
intake_dir = config.get('paths.documents.intake')

# Using properties
app_name = config.app_name
log_level = config.log_level
intake_dir = config.intake_dir  # Returns Path object

# With defaults
custom_value = config.get('custom.setting', default='default_value')
```

### Change Storage Location

**config/paths.json:**
```json
{
  "paths": {
    "documents": {
      "intake": "/mnt/storage/kyc/intake",
      "processed": "/mnt/storage/kyc/processed"
    }
  }
}
```

**Code automatically uses new paths:**
```python
from utilities import config

# Automatically resolves to /mnt/storage/kyc/intake
intake_path = config.intake_dir
```

### Switch LLM Provider

**config/llm.json:**
```json
{
  "llm": {
    "provider": "anthropic",
    "anthropic": {
      "api_key": "${ANTHROPIC_API_KEY}",
      "model": "claude-3-sonnet-20240229"
    }
  }
}
```

## 🔧 Configuration Loader Features

### Singleton Pattern
Config is loaded once at application startup:

```python
from utilities import config  # Loaded once, reused everywhere
```

### Environment Variable Resolution
Automatically replaces `${VAR_NAME}` with environment variable values:

```json
{
  "api_key": "${OPENAI_API_KEY}"
}
```

### Path Objects
Get paths as Path objects with absolute resolution:

```python
intake_path = config.intake_dir  # Returns Path object
absolute_path = config.get_path('paths.documents.intake')
```

### Auto-Create Directories
All configured directories are automatically created at startup.

### Reload Configuration
```python
config.reload()  # Reload all files from config/ directory

# List loaded config files
files = config.list_config_files()
print(files)  # ['api.json', 'app.json', 'llm.json', 'paths.json']
```

## 🔄 Backward Compatibility

Old code still works:

```python
from utilities import settings

settings.log_level
settings.openai_api_key
settings.classifier_api_base_url
```directories:

```
config/              # Default (development)
config_staging/      # Staging environment  
config_production/   # Production environment
```

**config_production/paths.json:**
```json
{
  "paths": {
    "documents": {
      "intake": "/data/production/intake"
    }
  }
}
```

**config_production/app.json:**
```json
{
  "application": {
    "environment": "production",
    "log_level": "WARNING"
  }
}
```

**Load specific environment:**
```python
config = ConfigLoader(config_dir='config_production')
```

## ➕ Adding New Configuration Files

Just add a new JSON file to the `config/` directory:

**config/database.json:**
```jOrganized**: Separate files for different concerns  
✅ **Simple**: Plain JSON, easy to read and edit  
✅ **Modular**: Add new config files without changing code  
✅ **Secure**: Sensitive data in environment variables  
✅ **Flexible**: Easy to change paths and settings  
✅ **Auto-merge**: All files automatically combined  
✅ **Auto-setup**: Directories created automatically  

## 🎯 Best Practices

1. **Logical separation**: Keep related settings in the same file
2. **Keep secrets in .env**: Never commit API keys to JSON files
3. **Use environment-specific dirs**: config/, config_staging/, config_production/
4. **Validate JSON**: Ensure files are valid JSON before committing
5. **Version control**: Commit config/*.json, not .env
6. **Name clearly**: Use descriptive names for new config files

## 📂 Configuration Directory Structure

```
config/
├── app.json       → Application settings & validation
├── paths.json     → File system paths
├── llm.json       → Language model configurations
├── api.json       → External API settings
├── logging.json   → Logging configuration
└── README.md      → Configuration documentation
```

---

**Need to change a setting?** Find the right JSON file in `config/`, edit it,
✅ **Simple**: Plain JSON, easy to read and edit  
✅ **Centralized**: All settings in one place  
✅ **Secure**: Sensitive data in environment variables  
✅ **Flexible**: Easy to change paths and settings  
✅ **Type-safe**: Validation and type hints  
✅ **Auto-setup**: Directories created automatically  

## 🎯 Best Practices

1. **Keep secrets in .env**: Never commit API keys to config.json
2. **Use environment-specific configs**: dev, staging, production
3. **Document changes**: Add comments in JSON when needed
4. **Validate paths**: Ensure paths exist before deployment
5. **Version control**: Commit config.json, not .env

---

**Need to change a setting?** Just edit `config.json` and restart the app!
