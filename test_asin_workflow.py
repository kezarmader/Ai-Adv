#!/usr/bin/env python3
"""
Test script for ASIN-based workflow validation
"""
import requests
import json
import sys

def test_asin_extraction(asin="B08N5WRWNW"):
    """Test ASIN extraction service"""
    print(f"🧪 Testing ASIN extraction for: {asin}")
    
    try:
        response = requests.post("http://localhost:5004/extract", 
                               json={"asin": asin}, 
                               timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ ASIN extraction successful!")
            print(f"   Product: {data.get('title', 'N/A')}")
            print(f"   Brand: {data.get('brand', 'N/A')}")
            print(f"   Features: {len(data.get('features', []))} found")
            print(f"   Images: {len(data.get('image_urls', []))} found")
            return data
        else:
            print(f"❌ ASIN extraction failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to ASIN extraction service (port 5004)")
        print("   Make sure Docker services are running: docker-compose up -d")
        return None
    except Exception as e:
        print(f"❌ Error testing ASIN extraction: {e}")
        return None

def test_orchestrator_asin_workflow(asin="B08N5WRWNW"):
    """Test full orchestrator ASIN workflow"""
    print(f"\n🎯 Testing orchestrator ASIN workflow for: {asin}")
    
    try:
        payload = {
            "asin": asin,
            "generate_video": True,
            "video_animation": "ai_enhanced",
            "video_duration": 5,
            "video_style": "dynamic"
        }
        
        response = requests.post("http://localhost:8000/run", 
                               json=payload, 
                               timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Orchestrator workflow successful!")
            print(f"   Product: {data.get('ad_text', {}).get('product', 'N/A')}")
            print(f"   Image URL: {data.get('image_url', 'N/A')}")
            print(f"   Video URL: {data.get('video_url', 'N/A')}")
            print(f"   Post Status: {data.get('post_status', {}).get('status', 'N/A')}")
            return data
        else:
            print(f"❌ Orchestrator workflow failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to orchestrator service (port 8000)")
        print("   Make sure Docker services are running: docker-compose up -d")
        return None
    except Exception as e:
        print(f"❌ Error testing orchestrator workflow: {e}")
        return None

def main():
    """Main test function"""
    print("🚀 ASIN-Based AI Advertisement Generator - Workflow Test")
    print("=" * 60)
    
    # Test individual ASIN extraction
    asin_data = test_asin_extraction()
    
    # If ASIN extraction works, test full workflow
    if asin_data:
        workflow_data = test_orchestrator_asin_workflow()
        
        if workflow_data:
            print("\n🎉 All tests passed! ASIN-based workflow is working.")
        else:
            print("\n⚠️  ASIN extraction works, but orchestrator workflow failed.")
    else:
        print("\n⚠️  ASIN extraction failed. Cannot test full workflow.")
    
    print("\n📋 Test Summary:")
    print("   1. ASIN Extraction Service:", "✅ Working" if asin_data else "❌ Failed")
    print("   2. Orchestrator Workflow:", "✅ Working" if asin_data and 'workflow_data' in locals() and workflow_data else "❌ Failed")
    
    print("\n🔧 If services are not running, start them with:")
    print("   docker-compose up -d")
    print("\n🌐 Access points:")
    print("   - Orchestrator: http://localhost:8000")
    print("   - ASIN Extractor: http://localhost:5004") 
    print("   - Image Generator: http://localhost:5001")
    print("   - Video Generator: http://localhost:5003")

if __name__ == "__main__":
    main()