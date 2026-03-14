import requests
import json

url = "http://localhost:8000/hazard"
payload = {
    "lat": 42.6977,
    "lon": 23.3219,
    "type": "pothole",
    "severity": 8,
    "description": "Big hole here"
}

try:
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 201:
        # Check if it's in the list
        list_resp = requests.get("http://localhost:8000/hazards")
        print(f"Hazards list: {list_resp.text}")
except Exception as e:
    print(f"Error: {e}")
