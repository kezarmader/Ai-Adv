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
    "orchestrator": "http://localhost:8000",
    "image-generator": "http://localhost:5001", 
    "poster-service": "http://localhost:5002",
    "llm-service": "http://localhost:11434"
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

def test_ad_generation():
    """Test the complete ad generation pipeline"""
    test_payload = {
        "product": "Test Product",
        "audience": "tech enthusiasts",
        "tone": "friendly",
        "ASIN": "B08N5WRWNW",
        "brand_text": "TestBrand",
        "cta_text": "Try Now!"
    }
    
    try:
        print("🧪 Testing ad generation pipeline...")
        start_time = time.time()
        
        response = requests.post(
            f"{SERVICES['orchestrator']}/run",
            json=test_payload,
            timeout=60
        )
        
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "✅ Success",
                "duration": f"{duration:.2f}s",
                "has_ad_text": "ad_text" in data,
                "has_image_url": "image_url" in data,
                "post_status": data.get("post_status", {}).get("status", "unknown")
            }
        else:
            return {
                "status": f"❌ Failed (HTTP {response.status_code})",
                "duration": f"{duration:.2f}s",
                "error": response.text[:100]
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
    
    # Test complete pipeline
    print("\n🔄 Pipeline Test:")
    pipeline_result = test_ad_generation()
    
    for key, value in pipeline_result.items():
        print(f"  {key}: {value}")
    
    # Summary
    print("\n📝 Summary:")
    healthy_services = sum(1 for row in service_data if "✅" in row[1])
    total_services = len(service_data)
    
    if healthy_services == total_services and "✅" in pipeline_result["status"]:
        print("🎉 All systems operational!")
        sys.exit(0)
    elif healthy_services == total_services:
        print("⚠️ Services healthy but pipeline has issues")
        sys.exit(1)
    else:
        print(f"❌ {total_services - healthy_services}/{total_services} services have issues")
        sys.exit(1)

if __name__ == "__main__":
    main()
