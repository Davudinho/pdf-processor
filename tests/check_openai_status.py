#!/usr/bin/env python
"""
Check OpenAI API Status and Quota
Verifies API key validity and available credits.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
import openai

# Load environment
load_dotenv(os.path.join(parent_dir, '.env'))

# Colors
class Colors:
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'

def print_success(text):
    try:
        print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.OKGREEN}[OK] {text}{Colors.ENDC}")

def print_error(text):
    try:
        print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.FAIL}[ERROR] {text}{Colors.ENDC}")

def print_info(text):
    try:
        print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.CYAN}[INFO] {text}{Colors.ENDC}")

def print_warning(text):
    try:
        print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.WARNING}[WARNING] {text}{Colors.ENDC}")

def check_api_status():
    """Check OpenAI API key status and quota"""
    print(f"\n{Colors.BOLD}OpenAI API Status Check{Colors.ENDC}")
    print("="*80)
    
    # Get API key
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print_error("OPENAI_API_KEY not found in environment")
        print_info("Please set OPENAI_API_KEY in .env file")
        return False
    
    if api_key == 'your_openai_api_key_here':
        print_error("OPENAI_API_KEY is still the default placeholder")
        print_info("Please replace with your actual API key from platform.openai.com")
        return False
    
    print_success(f"API Key found: {api_key[:15]}...{api_key[-4:]}")
    print()
    
    # Check key format
    if api_key.startswith('sk-proj-'):
        print_success("Key format: Project-based key (new format)")
    elif api_key.startswith('sk-'):
        print_warning("Key format: Legacy key (old format)")
        print_info("Consider generating a new project-based key")
    else:
        print_error("Key format: Invalid format")
        return False
    
    print()
    
    # Test API connection
    try:
        client = openai.OpenAI(api_key=api_key)
        print_info("Testing API connection with minimal request...")
        
        # Make a minimal API call to test
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5
        )
        
        print_success("API connection successful!")
        print_success("API key is valid and has available quota")
        print()
        print_info(f"Model used: {response.model}")
        print_info(f"Tokens used: {response.usage.total_tokens}")
        print()
        
        return True
        
    except openai.AuthenticationError as e:
        print_error("Authentication failed")
        print_error(f"Error: {e}")
        print()
        print_warning("Possible issues:")
        print("  1. API key is invalid or revoked")
        print("  2. API key is from a different organization")
        print("  3. API key has expired")
        print()
        print_info("Solutions:")
        print("  1. Go to: https://platform.openai.com/api-keys")
        print("  2. Create a new API key")
        print("  3. Update your .env file with the new key")
        return False
        
    except openai.RateLimitError as e:
        print_error("Rate limit exceeded")
        print_error(f"Error: {e}")
        print()
        
        # Check error message for quota details
        error_msg = str(e)
        if 'insufficient_quota' in error_msg or 'quota' in error_msg.lower():
            print_warning("Your account has insufficient quota")
            print()
            print_info("Possible reasons:")
            print("  1. Free $5 credit has been used")
            print("  2. Free trial has expired")
            print("  3. Payment method not added")
            print()
            print_info("Solutions:")
            print("  1. Check usage: https://platform.openai.com/usage")
            print("  2. Check billing: https://platform.openai.com/account/billing")
            print("  3. Add payment method if free trial expired")
            print("  4. Add credits to your account")
            print()
            print_info("Free tier information:")
            print("  • New accounts get $5 free credit")
            print("  • Free credit expires after 3 months")
            print("  • gpt-3.5-turbo: ~$0.002 per 1K tokens")
            print("  • This project needs ~$0.10-0.50 for the test document")
        else:
            print_warning("Rate limit (requests per minute)")
            print_info("Wait a few minutes and try again")
        
        return False
        
    except openai.APIError as e:
        print_error("OpenAI API error")
        print_error(f"Error: {e}")
        print()
        print_warning("OpenAI service may be experiencing issues")
        print_info("Check status: https://status.openai.com")
        return False
        
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_recommendations():
    """Show recommendations based on API status"""
    print()
    print(f"{Colors.BOLD}Recommendations:{Colors.ENDC}")
    print()
    
    print_info("If you have free credits:")
    print("  1. Check usage at: https://platform.openai.com/usage")
    print("  2. Credits may have expired (3-month limit)")
    print("  3. Generate a new API key if needed")
    print()
    
    print_info("If free trial expired:")
    print("  1. Go to: https://platform.openai.com/account/billing")
    print("  2. Click 'Add payment method'")
    print("  3. Add $5-10 for testing (will last long)")
    print()
    
    print_info("Cost estimation for this project:")
    print("  • gpt-3.5-turbo: ~$0.002 per 1K tokens")
    print("  • Test PDF (84 pages): ~$0.50-1.00")
    print("  • $5 credit = ~250-500 pages")
    print()
    
    print_info("Alternative (free tier expired):")
    print("  • System still works without AI processing")
    print("  • PDF upload, storage, search all work")
    print("  • Only summaries and keywords won't be generated")
    print()

if __name__ == "__main__":
    success = check_api_status()
    
    print()
    print("="*80)
    
    if success:
        print_success("Your OpenAI API is configured correctly and has available quota!")
        print_info("You can now run: python test_complete_workflow.py")
    else:
        print_error("OpenAI API has issues (see details above)")
        print_info("System will still work for PDF processing and search")
        print_info("Only AI features (summaries, keywords) will be unavailable")
    
    show_recommendations()
    
    sys.exit(0 if success else 1)

