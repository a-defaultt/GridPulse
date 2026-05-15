import requests
import os
from src.config import NVD_API_KEY

def debug_nvd():
    url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    headers = {"apiKey": NVD_API_KEY} if NVD_API_KEY else {}
    params = {"resultsPerPage": 1}
    
    print(f"Testing NVD API: {url}")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_nvd()
