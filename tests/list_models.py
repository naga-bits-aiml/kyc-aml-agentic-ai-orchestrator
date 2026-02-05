"""
List available models from OpenAI and Google Gemini.

This script helps you discover which models you have access to.
"""
from openai import OpenAI
from utilities import config
import os

def list_openai_models():
    """List all available OpenAI models."""
    try:
        client = OpenAI(api_key=config.openai_api_key)
        
        print("\n" + "="*70)
        print("📋 Available OpenAI Models")
        print("="*70 + "\n")
        
        models = client.models.list()
        
        # Filter for chat models
        chat_models = []
        other_models = []
        
        for model in models.data:
            if 'gpt' in model.id.lower():
                chat_models.append(model.id)
            else:
                other_models.append(model.id)
        
        print("💬 Chat Models (recommended for this application):")
        print("-" * 70)
        for model in sorted(chat_models)[:20]:  # Show first 20
            print(f"  ✓ {model}")
        
        if len(chat_models) > 20:
            print(f"  ... and {len(chat_models) - 20} more")
        
        print(f"\n📊 Other Models ({len(other_models)} total):")
        print("-" * 70)
        for model in sorted(other_models)[:10]:  # Show first 10
            print(f"  • {model}")
        
        if len(other_models) > 10:
            print(f"  ... and {len(other_models) - 10} more")
        
        print("\n" + "="*70)
        print("💡 Recommended OpenAI models for KYC-AML:")
        print("="*70)
        print("  • gpt-3.5-turbo         - Fast, cost-effective (available to all)")
        print("  • gpt-4o               - Latest GPT-4 model")
        print("  • gpt-4o-mini          - Smaller GPT-4 variant")
        print("="*70 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error listing OpenAI models: {str(e)}")
        print("   OpenAI API key may not be configured or valid.\n")
        return False


def list_google_models():
    """List all available Google Gemini models."""
    try:
        from google import genai
        
        api_key = config.get('llm.google.api_key')
        if not api_key:
            print("\n⚠️  Google API key not configured")
            print("   Set GOOGLE_API_KEY in .env file to see Google models\n")
            return False
        
        client = genai.Client(api_key=api_key)
        
        print("\n" + "="*70)
        print("📋 Available Google Gemini Models")
        print("="*70 + "\n")
        
        models = client.models.list()
        
        # Categorize models
        chat_models = []
        embedding_models = []
        
        for model in models:
            name = model.name.replace('models/', '')
            if 'gemini' in name.lower():
                chat_models.append(name)
            elif 'embed' in name.lower():
                embedding_models.append(name)
        
        print("💬 Chat/Generation Models:")
        print("-" * 70)
        for model in sorted(chat_models):
            print(f"  ✓ {model}")
        
        if embedding_models:
            print(f"\n🔢 Embedding Models:")
            print("-" * 70)
            for model in sorted(embedding_models):
                print(f"  • {model}")
        
        print("\n" + "="*70)
        print("💡 Recommended Google Gemini models for KYC-AML:")
        print("="*70)
        print("  • gemini-2.5-flash          - Fast, cost-effective (FREE tier!)")
        print("  • gemini-2.5-pro            - Most capable")
        print("  • gemini-1.5-flash          - Balanced performance")
        print("\n💰 Pricing:")
        print("  • Gemini 2.5 Flash: FREE for 2M tokens/day")
        print("  • With Google Cloud: $300 free credit")
        print("="*70 + "\n")
        
        return True
        
    except ImportError:
        print("\n⚠️  Google Gen AI package not installed")
        print("   Run: pip install google-genai\n")
        return False
    except Exception as e:
        print(f"\n❌ Error listing Google models: {str(e)}")
        print("   Google API key may not be configured or valid.\n")
        return False


def show_current_config():
    """Show current LLM configuration."""
    print("\n" + "="*70)
    print("⚙️  Current Configuration")
    print("="*70)
    
    provider = config.llm_provider
    print(f"\n📌 Active Provider: {provider.upper()}")
    
    if provider == "openai":
        openai_config = config.get('llm.openai', {})
        print(f"   Model: {openai_config.get('model', 'N/A')}")
        print(f"   API Key: {'✓ Configured' if config.openai_api_key else '✗ Not set'}")
    elif provider == "google":
        google_config = config.get('llm.google', {})
        print(f"   Model: {google_config.get('model', 'N/A')}")
        api_key = google_config.get('api_key')
        print(f"   API Key: {'✓ Configured' if api_key else '✗ Not set'}")
    
    print("\n💡 To change provider, edit config/llm.json")
    print("="*70 + "\n")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔍 LLM Model Discovery Tool")
    print("="*70)
    
    show_current_config()
    
    # List OpenAI models
    openai_ok = list_openai_models()
    
    # List Google models
    google_ok = list_google_models()
    
    # Summary
    print("\n" + "="*70)
    print("📊 Summary")
    print("="*70)
    print(f"  OpenAI:  {'✓ Available' if openai_ok else '✗ Not available'}")
    print(f"  Google:  {'✓ Available' if google_ok else '✗ Not available'}")
    print("="*70 + "\n")
    
    if not openai_ok and not google_ok:
        print("⚠️  No LLM providers configured!")
        print("   Please set up at least one API key in .env file\n")
    else:
        print("✅ Ready to use! Run: python chat_interface.py\n")
