import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

def test_api_key():
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = "gemini-2.5-flash"
    
    print("-" * 50)
    print(f"Testing Gemini API Key with Model: {model_name}...")
    print("-" * 50)

    if not api_key:
        print("❌ CRITICAL ERROR: GEMINI_API_KEY not found in environment.")
        return False

    genai.configure(api_key=api_key)

    try:
        print(f"Attempting to connect to Gemini ({model_name})...")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say 'Model Check OK' if you can hear me.")
        
        print("\n✅ SUCCESS! Connection established.")
        print(f"Response from AI: \"{response.text.strip()}\"")
        return True

    except Exception as e:
        print(f"\n❌ ERROR with model '{model_name}': {e}")
    
    return False

if __name__ == "__main__":
    success = test_api_key()
    sys.exit(0 if success else 1)
