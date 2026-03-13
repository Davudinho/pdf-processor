import requests
import time
import sys
import os

API_URL = "http://127.0.0.1:5000"

def test_upload_and_categorization(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return False

    print(f"Uploading {os.path.basename(pdf_path)}...")
    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{API_URL}/upload", files=files)
        
    if response.status_code != 200:
        print(f"Upload failed: {response.text}")
        return False
        
    data = response.json()
    doc_id = data.get('data', {}).get('doc_id')
    print(f"Upload successful. Document ID: {doc_id}")
    
    print("Waiting for processing to complete...")
    max_retries = 60
    for i in range(max_retries):
        status_resp = requests.get(f"{API_URL}/document/{doc_id}/status")
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            if status_data.get('is_complete'):
                print(f"Processing complete after {i*2} seconds.")
                break
        print(".", end="", flush=True)
        time.sleep(2)
    else:
        print("\nProcessing timeout but going to check documents list anyway.")
        
    print("\nFetching documents list to check category...")
    docs_resp = requests.get(f"{API_URL}/documents")
    if docs_resp.status_code == 200:
        docs = docs_resp.json().get('data', [])
        for doc in docs:
            if doc.get('doc_id') == doc_id:
                category = doc.get('category')
                print(f"\nSUCCESS! Found document.")
                print(f"Assigned Category: '{category}'")
                print(f"Summary: {doc.get('document_summary', '')[:100]}...")
                return True
    
    print("\nFailed to find document in list or category missing.")
    return False

if __name__ == "__main__":
    test_pdf = r"C:\Users\User\projects\pdf-processor\uploads\CV_Davut_Ozdemir_Deutsch.pdf"
    test_upload_and_categorization(test_pdf)
