# Configuration Directory

This directory contains all configuration files for the KYC-AML Agentic AI Orchestrator.

## 📁 Configuration Files

### [app.json](app.json)
Application-wide settings:
- Application metadata (name, version, environment)
- Document validation rules (max size, allowed extensions)
- Processing settings (batch size)
- Chat configuration
- Security settings

### [paths.json](paths.json)
All file and directory paths:
- Document storage locations (intake, processed, archive, temp)
- Metadata file locations
- Log file paths
- Chat history directories

### [llm.json](llm.json)
Language Model configurations:
- Provider selection (openai, azure, anthropic, ollama)
- Model-specific settings for each provider
- API keys (referenced from environment variables)
- Temperature and token limits

### [api.json](api.json)
External API configurations:
- Document classifier API endpoint
- API authentication
- Timeout and retry settings

### [logging.json](logging.json)
Logging configuration:
- Log formatters (default, detailed, simple, json)
- Log handlers (console, file, error file with rotation)
- Logger levels for different modules
- Log file settings (size limits, backup count)
- Enable/disable file and console logging

## 🔧 How It Works

The `config_loader.py` module automatically:
1. Loads all `.json` files from this directory
2. Merges them into a single configuration object
3. Resolves environment variable placeholders (`${VAR_NAME}`)
4. Makes the configuration available throughout the application

## 📝 Usage

### Accessing Configuration

```python
from utilities import config

# Use dot notation
app_name = config.get('application.name')
intake_dir = config.get('paths.documents.intake')
openai_model = config.get('llm.openai.model')

# Or use convenience properties
log_level = config.log_level
intake_path = config.intake_dir
classifier_url = config.classifier_api_url
```

### Modifying Configuration

Simply edit the relevant JSON file:

**To change storage paths:** Edit `paths.json`
```json
{
  "paths": {
    "documents": {
      "intake": "/custom/path/intake"
    }
  }
}
```

**To switch LLM providers:** Edit `llm.json`
```json
{
  "llm": {
    "provider": "anthropic"
  }
}
```

**To adjust validation rules:** Edit `app.json`
```json
{
  "document_validation": {
    "max_size_mb": 20
  }
}
```

**To configure logging:** Edit `logging.json`
```json
{
  "log_settings": {
    "level": "DEBUG",
    "log_format": "detailed"
  }
}
```

## 🔐 Environment Variables

Sensitive data (API keys) should be in `.env` file:

```env
OPENAI_API_KEY=your_key_here
CLASSIFIER_API_KEY=your_key_here
AZURE_OPENAI_API_KEY=your_azure_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

Reference them in JSON files using `${VAR_NAME}` syntax:

```json
{
  "llm": {
    "openai": {
      "api_key": "${OPENAI_API_KEY}"
    }
  }
}
```

## 📦 Adding New Configuration

To add new configuration:

1. **Create a new JSON file** in this directory (e.g., `database.json`)
2. **Add your settings** in valid JSON format
3. **Restart the application** - it will auto-load the new file
4. **Access via config loader** using dot notation

Example - Adding database configuration:

**config/database.json:**
```json
{
  "database": {
    "host": "localhost",
    "port": 5432,
    "name": "kyc_aml_db",
    "user": "${DB_USER}",
    "password": "${DB_PASSWORD}"
  }
}
```

**Usage:**
```python
from utilities import config

db_host = config.get('database.host')
db_port = config.get('database.port')
```

## 🌍 Environment-Specific Configurations

For different environments, you can:

1. **Use environment variable** to switch configs:
   ```env
   APP_ENVIRONMENT=production
   ```

2. **Or use separate config directories:**
   ```
   config/dev/
   config/staging/
   config/production/
   ```

3. **Load specific directory:**
   ```python
   config = ConfigLoader(config_dir='config/production')
   ```

## ✅ Best Practices

1. ✅ **Separate concerns**: Keep related settings in their respective files
2. ✅ **Use environment variables**: For all sensitive data
3. ✅ **Document changes**: Add comments in this README when adding new config files
4. ✅ **Validate JSON**: Ensure files are valid JSON before committing
5. ✅ **Version control**: Commit config files, NOT .env
├── logging.json   → Logging configuration
6. ✅ **Keep it simple**: Don't over-complicate - only add files when needed

## 🔍 Configuration Hierarchy

```
config/
├── app.json       → Application & validation settings
├── paths.json     → File system paths
├── llm.json       → Language model configurations
├── api.json       → External API settings
└── README.md      → This file
```

All files are automatically loaded and merged into one config object accessible via `utilities.config`.

---

**Need to change a setting?** Find the right JSON file, edit it, and restart the app!
