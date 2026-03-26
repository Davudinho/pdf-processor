#!/usr/bin/env python
import sys
import os
from pathlib import Path

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv(os.path.join(parent_dir, '.env'))

def check_gemini_status():
    print("Gemini API Status Check")
    print("="*80)
    
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print("✗ GEMINI_API_KEY not found in environment")
        return False
    
    print(f"✓ API Key found: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        print("ℹ Testing API connection with minimal request...")
        response = model.generate_content("Hi")
        
        print("✓ API connection successful!")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = check_gemini_status()
    sys.exit(0 if success else 1)
