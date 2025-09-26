#!/usr/bin/env python3
"""
Quick test script to test the ASIN workflow directly
"""

import requests
import json
import time

def test_asin_directly():
    """Test the ASIN endpoint directly"""
    url = "http://madhouse53.duckdns.org/run"
    payload = {
        "asin": "B009YO1HWS",
        "generate_video": False
    }
    
    print(f"🔍 Testing ASIN workflow with: {payload['asin']}")
    print(f"📡 Sending request to: {url}")
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS!")
            print(f"🏷️  Product: {data.get('ad_text', {}).get('product', 'N/A')}")
            print(f"🖼️  Image URL: {data.get('image_url', 'N/A')}")
            print(f"📝 Features: {len(data.get('ad_text', {}).get('features', []))} features")
        else:
            print("❌ FAILED!")
            try:
                error_data = response.json()
                print(f"🚨 Error: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"🚨 Raw response: {response.text[:200]}")
                
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: {e}")
        print("🔧 Make sure Docker containers are running with: docker ps")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_asin_directly()