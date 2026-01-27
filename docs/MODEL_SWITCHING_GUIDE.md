# Model Switching Guide

## Overview

The KYC-AML chat application now supports dynamic model switching. You can view available models and switch between them at any time during a chat session without restarting the application.

## Default Configuration

- **Default Provider**: OpenAI (configurable in `config/llm.json`)
- **Default Model**: gpt-4o-mini

Note: While Google Gemini is configured, there's a current version incompatibility with `langchain-google-genai`. Use OpenAI models for now.

## Available Commands

### View Current Model
```
/current
current
```
Shows the currently active provider and model.

### List All Available Models
```
/models
models
list models
```
Displays all configured models across all providers with:
- Model name
- Description
- Context window size
- Current selection indicator (✓)

### Switch Models

#### Within Same Provider
```
/switch-model <model-name>
```
Example:
```
/switch-model gpt-4o
/switch-model gpt-3.5-turbo
```

#### Across Providers
```
/switch-model <provider> <model-name>
```
Examples:
```
/switch-model openai gpt-4o
/switch-model google gemini-1.5-pro
/switch-model anthropic claude-3-sonnet-20240229
```

## Available Models

### OpenAI
- **gpt-4o** - Most capable GPT-4 model, multimodal (128K context)
- **gpt-4o-mini** - Affordable and fast GPT-4 level intelligence (128K context)
- **gpt-4-turbo** - GPT-4 Turbo with vision capabilities (128K context)
- **gpt-3.5-turbo** - Fast, inexpensive model for simple tasks (16K context)

### Google Gemini (Currently Unavailable)
- **gemini-2.5-flash** - Fastest Gemini model (1M context)
- **gemini-2.0-flash** - Fast and balanced (1M context)
- **gemini-1.5-pro** - Advanced reasoning (2M context)
- **gemini-1.5-flash** - Fast and versatile (1M context)

### Anthropic Claude
- **claude-3-opus-20240229** - Most capable (200K context)
- **claude-3-sonnet-20240229** - Balanced performance (200K context)
- **claude-3-haiku-20240307** - Fastest (200K context)

### Ollama (Local Models)
- **llama2** - Meta's Llama 2, runs locally (4K context)
- **mistral** - Mistral 7B, fast open model (8K context)
- **codellama** - Code-specialized (16K context)

## Usage Examples

### Example Session
```
👤 You: /current
🤖 Assistant: Current provider: openai
Current model: gpt-4o-mini

👤 You: /models
🤖 Assistant: [Shows full list of models]

👤 You: /switch-model gpt-4o
🤖 Assistant: 🔄 Switching from openai/gpt-4o-mini to openai/gpt-4o...

✅ Model switched successfully!
Now using: openai - gpt-4o

💬 Your conversation context has been preserved.

👤 You: What can you do?
🤖 Assistant: [Response using gpt-4o]
```

### Switching for Different Tasks

**For Fast Processing** (use mini models):
```
/switch-model gpt-4o-mini
/switch-model gpt-3.5-turbo
```

**For Complex Reasoning** (use pro/advanced models):
```
/switch-model gpt-4o
/switch-model google gemini-1.5-pro
/switch-model anthropic claude-3-opus-20240229
```

**For Cost Efficiency**:
```
/switch-model gpt-3.5-turbo
/switch-model ollama mistral
```

## Configuration

### Adding New Models

Edit `config/llm.json` to add new models:

```json
{
  "llm": {
    "available_models": {
      "openai": [
        {
          "name": "new-model-name",
          "description": "Description of the model",
          "context_window": 128000
        }
      ]
    }
  }
}
```

### Changing Default Provider

Edit `config/llm.json`:
```json
{
  "llm": {
    "provider": "openai"  // Change to: google, anthropic, ollama
  }
}
```

### API Key Requirements

Set the appropriate environment variable in `.env`:
```
OPENAI_API_KEY=your-key-here
GOOGLE_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
```

## Features

✅ **Runtime Switching** - Change models without restarting
✅ **Context Preservation** - Chat history maintained across switches
✅ **Multi-Provider** - OpenAI, Google, Anthropic, Ollama support
✅ **Smart Validation** - Validates provider and model before switching
✅ **Graceful Fallback** - Reverts on error, maintains conversation

## Troubleshooting

### "Model not found" Error
- Check spelling of model name
- Run `/models` to see exact model names
- Ensure provider is correctly specified

### Import Errors for Google/Anthropic
- Install required packages:
  ```bash
  pip install langchain-google-genai  # For Gemini
  pip install langchain-anthropic     # For Claude
  ```

### API Key Missing
- Set environment variable in `.env` file
- Restart application to load new keys

### Switch Fails
- Check logs for detailed error
- Verify API key is valid
- Ensure you have quota/credits for the model
