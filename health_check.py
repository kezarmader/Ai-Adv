#!/usr/bin/env python3
"""
Health monitoring script for AI Advertisement Generator
Run this to check the health and performance of all services
"""

import requests
import json
import time
from datetime import datetime, timedelta
import sys

# Service endpoints
SERVICES = {
    "orchestrator": "http://madhouse53.duckdns.org",
    "image-generator": "http://madhouse53.duckdns.org:5001", 
    "poster-service": "http://madhouse53.duckdns.org:5002",
    "llm-service": "http://madhouse53.duckdns.org:11434"
}

def check_service_health(name, base_url):
    """Check if a service is responding"""
    try:
        if name == "llm-service":
            # Ollama uses /api/tags endpoint
            response = requests.get(f"{base_url}/api/tags", timeout=5)
        else:
            # FastAPI services have /docs endpoint
            response = requests.get(f"{base_url}/docs", timeout=5)
        
        if response.status_code == 200:
            return {"status": "✅ Healthy", "response_time": response.elapsed.total_seconds()}
        else:
            return {"status": f"⚠️ Issues (HTTP {response.status_code})", "response_time": response.elapsed.total_seconds()}
            
    except requests.exceptions.ConnectionError:
        return {"status": "❌ Unreachable", "response_time": None}
    except requests.exceptions.Timeout:
        return {"status": "⏱️ Timeout", "response_time": None}
    except Exception as e:
        return {"status": f"❌ Error: {e}", "response_time": None}

def test_asin_workflow():
    """Test the new ASIN-based workflow"""
    test_payload = {
        "asin": "B009YO1HWS",  # Valid Amazon ASIN for testing
        "generate_video": False  # Skip video for initial test
    }
    
    try:
        print("🧪 Testing ASIN-based workflow...")
        start_time = time.time()
        
        response = requests.post(
            f"{SERVICES['orchestrator']}/run",
            json=test_payload,
            timeout=60
        )
        
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            product_name = data.get("ad_text", {}).get("product", "Unknown")
            return {
                "status": "✅ Success",
                "duration": f"{duration:.2f}s",
                "product_extracted": product_name,
                "has_ad_text": "ad_text" in data,
                "has_image_url": "image_url" in data,
                "post_status": data.get("post_status", {}).get("status", "unknown")
            }
        else:
            error_detail = "Unknown error"
            try:
                error_data = response.json()
                error_detail = error_data.get("detail", response.text[:100])
            except:
                error_detail = response.text[:100]
                
            return {
                "status": f"❌ Failed (HTTP {response.status_code})",
                "duration": f"{duration:.2f}s",
                "error": error_detail
            }
            
    except Exception as e:
        return {
            "status": f"❌ Error: {e}",
            "duration": None
        }

def test_video_generation():
    """Test the complete pipeline with video generation"""
    test_payload = {
        "asin": "B009YO1HWS",  # Valid Amazon ASIN for testing
        "generate_video": True,
        "video_animation": "ai_enhanced",
        "video_duration": 3,
        "video_style": "dynamic"
    }
    
    try:
        print("🎬 Testing video generation...")
        start_time = time.time()
        
        response = requests.post(
            f"{SERVICES['orchestrator']}/run",
            json=test_payload,
            timeout=120
        )
        
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "✅ Success",
                "duration": f"{duration:.2f}s",
                "has_video": "video_url" in data,
                "video_url": data.get("video_url", "Not generated")
            }
        else:
            error_detail = "Unknown error"
            try:
                error_data = response.json()
                error_detail = error_data.get("detail", response.text[:100])
            except:
                error_detail = response.text[:100]
                
            return {
                "status": f"❌ Failed (HTTP {response.status_code})",
                "duration": f"{duration:.2f}s",
                "error": error_detail
            }
            
    except Exception as e:
        return {
            "status": f"❌ Error: {e}",
            "duration": None
        }

def format_table(data, headers):
    """Simple table formatting"""
    col_widths = [max(len(str(row[i])) for row in [headers] + data) for i in range(len(headers))]
    
    # Header
    header_row = " | ".join(f"{headers[i]:<{col_widths[i]}}" for i in range(len(headers)))
    separator = "-+-".join("-" * width for width in col_widths)
    
    print(header_row)
    print(separator)
    
    # Data rows
    for row in data:
        data_row = " | ".join(f"{str(row[i]):<{col_widths[i]}}" for i in range(len(row)))
        print(data_row)

def main():
    print("🏥 AI Advertisement Generator - Health Check")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Check individual services
    print("\n📊 Service Health Status:")
    service_data = []
    
    for name, url in SERVICES.items():
        result = check_service_health(name, url)
        service_data.append([
            name,
            result["status"],
            f"{result['response_time']:.3f}s" if result["response_time"] else "N/A"
        ])
    
    format_table(service_data, ["Service", "Status", "Response Time"])
    
    # Test ASIN workflow
    print("\n🔄 Pipeline Tests:")
    
    # Test 1: Basic ASIN workflow (without video)
    asin_result = test_asin_workflow()
    print("\n� ASIN Workflow Results:")
    for key, value in asin_result.items():
        print(f"  {key}: {value}")
    
    # Test 2: Video generation (only if basic workflow succeeds)
    if "✅" in asin_result["status"]:
        print("\n🎬 Testing video generation...")
        video_result = test_video_generation()
        print("📊 Video Generation Results:")
        for key, value in video_result.items():
            print(f"  {key}: {value}")
    else:
        print("\n🎬 Skipping video test due to ASIN workflow failure")
        video_result = {"status": "⏭️ Skipped"}
    
    # Summary
    print("\n📝 Summary:")
    healthy_services = sum(1 for row in service_data if "✅" in row[1])
    total_services = len(service_data)
    
    orchestrator_healthy = any("orchestrator" in row[0] and "✅" in row[1] for row in service_data)
    asin_working = "✅" in asin_result["status"]
    
    if orchestrator_healthy and asin_working:
        print("🎉 ASIN-based workflow is operational!")
        if "✅" in video_result.get("status", ""):
            print("🎬 Video generation is also working!")
        sys.exit(0)
    elif orchestrator_healthy:
        print("⚠️ Orchestrator healthy but ASIN workflow has issues")
        sys.exit(1)
    else:
        print(f"❌ {total_services - healthy_services}/{total_services} services have issues")
        sys.exit(1)

if __name__ == "__main__":
    main()
