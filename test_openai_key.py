import os
import sys
from dotenv import load_dotenv
from openai import OpenAI, AuthenticationError, RateLimitError, APIError

# Load environment variables from .env
load_dotenv()

def test_api_key():
    api_key = os.getenv("OPENAI_API_KEY")
    # CRITICAL: Check for configured model
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo") # Default fallback
    
    print("-" * 50)
    print(f"Testing OpenAI API Key with Model: {model}...")
    print("-" * 50)

    if not api_key:
        print("❌ CRITICAL ERROR: OPENAI_API_KEY not found in environment.")
        return False

    client = OpenAI(api_key=api_key)

    try:
        print(f"Attempting to connect to OpenAI ({model})...")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Say 'Model Check OK' if you can hear me."}
            ],
            max_tokens=10
        )
        
        content = response.choices[0].message.content
        print("\n✅ SUCCESS! Connection established.")
        print(f"Response from AI: \"{content}\"")
        return True

    except Exception as e:
        print(f"\n❌ ERROR with model '{model}': {e}")
        if "model" in str(e).lower():
            print(f"⚠️  It seems '{model}' might be invalid or you don't have access to it.")
    
    return False

if __name__ == "__main__":
    success = test_api_key()
    sys.exit(0 if success else 1)
