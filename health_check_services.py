#!/usr/bin/env python3
"""
Health check script for all AI Advertisement Generator services
"""
import requests
import time
import json

def check_service_health(service_name, url, expected_status=200, timeout=5):
    """Check if a service is healthy"""
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout)
        duration = (time.time() - start_time) * 1000
        
        if response.status_code == expected_status:
            print(f"✅ {service_name:<20} | Status: {response.status_code} | Response: {duration:.0f}ms")
            return True
        else:
            print(f"⚠️  {service_name:<20} | Status: {response.status_code} | Response: {duration:.0f}ms")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ {service_name:<20} | Status: CONNECTION_REFUSED | Service not running")
        return False
    except requests.exceptions.Timeout:
        print(f"⏰ {service_name:<20} | Status: TIMEOUT | Service too slow")
        return False
    except Exception as e:
        print(f"❌ {service_name:<20} | Status: ERROR | {str(e)}")
        return False

def check_gpu_status():
    """Check GPU availability for AI models"""
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,memory.total', '--format=csv,noheader,nounits'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            gpu_info = result.stdout.strip()
            print(f"🎮 GPU Status: {gpu_info}")
            return True
        else:
            print("⚠️  GPU Status: nvidia-smi failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ GPU Status: nvidia-smi timeout")
        return False
    except FileNotFoundError:
        print("❌ GPU Status: nvidia-smi not found (NVIDIA drivers not installed)")
        return False
    except Exception as e:
        print(f"❌ GPU Status: Error checking GPU - {e}")
        return False

def main():
    """Main health check function"""
    print("🏥 AI Advertisement Generator - Health Check")
    print("=" * 60)
    
    # Check GPU first
    gpu_ok = check_gpu_status()
    print()
    
    # Define services to check
    services = [
        ("Orchestrator", "http://localhost:8000/health"),
        ("ASIN Extractor", "http://localhost:5004/health"),
        ("Image Generator", "http://localhost:5001/health"),
        ("Video Generator", "http://localhost:5003/health"),
        ("Poster Service", "http://localhost:5002/health"),
        ("LLM Service", "http://localhost:11434/api/tags"),  # Ollama endpoint
    ]
    
    print("🔍 Service Health Check:")
    print("-" * 60)
    
    healthy_services = []
    for service_name, url in services:
        is_healthy = check_service_health(service_name, url)
        if is_healthy:
            healthy_services.append(service_name)
    
    print("-" * 60)
    print(f"📊 Summary: {len(healthy_services)}/{len(services)} services healthy")
    
    if len(healthy_services) == len(services):
        print("🎉 All services are running and healthy!")
        
        # Test ASIN workflow if all services are up
        print("\n🧪 Running ASIN workflow test...")
        try:
            payload = {"asin": "B08N5WRWNW"}  # Sample ASIN
            response = requests.post("http://localhost:5004/extract", json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ ASIN Test: Successfully extracted '{data.get('title', 'N/A')}'")
            else:
                print(f"⚠️  ASIN Test: Failed with status {response.status_code}")
        except Exception as e:
            print(f"❌ ASIN Test: Error - {e}")
            
    else:
        print("⚠️  Some services are not healthy. Check Docker containers:")
        print("   docker-compose ps")
        print("   docker-compose logs [service_name]")
    
    print(f"\n🎮 GPU Available: {'✅ Yes' if gpu_ok else '❌ No'}")
    print("\n🚀 To start all services:")
    print("   docker-compose up -d")
    print("\n🔧 To rebuild services:")
    print("   docker-compose up -d --build")

if __name__ == "__main__":
    main()