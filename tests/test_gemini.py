"""Quick test to find the correct Google Gemini model name."""
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    print("❌ GOOGLE_API_KEY not set in .env")
    exit(1)

client = genai.Client(api_key=api_key)

print("\n" + "="*70)
print("🔍 Finding Available Google Gemini Models")
print("="*70 + "\n")

print("Models that support generateContent (chat):\n")

chat_models = []
for model in client.models.list():
    model_name = model.name.replace('models/', '')
    chat_models.append(model_name)
    print(f"  ✓ {model_name}")

print("\n" + "="*70)
print("Testing first available model...")
print("="*70 + "\n")

if chat_models:
    test_model = chat_models[0]
    print(f"Testing: {test_model}")
    
    try:
        response = client.models.generate_content(
            model=test_model,
            contents="Say hello"
        )
        print(f"\n✅ SUCCESS! Model '{test_model}' works!")
        print(f"Response: {response.text[:100]}...")
        
        print(f"\n📝 Use this in config/llm.json:")
        print(f'   "model": "{test_model}"')
        
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("❌ No chat models found!")

print("\n" + "="*70 + "\n")
