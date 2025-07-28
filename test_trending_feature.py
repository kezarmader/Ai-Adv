#!/usr/bin/env python3
"""
Test script for the new Google Trends integration feature
Tests the secure multi-source trends system with debugging
"""
import requests
import json
import time
import asyncio

# Configuration
BASE_URL = "http://localhost:8000"
TRENDING_ENDPOINT = f"{BASE_URL}/run/trending"
TRENDS_ENDPOINT = f"{BASE_URL}/trends"
DEBUG_ENDPOINT = f"{BASE_URL}/trends/debug"

def test_trends_debug_endpoint():
    """Test the trends debug endpoint"""
    print("=" * 60)
    print("🔧 Testing Trends Debug Endpoint")
    print("=" * 60)
    
    try:
        response = requests.get(DEBUG_ENDPOINT, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Debug endpoint working!")
            
            debug_info = data.get('debug_info', {})
            print(f"📊 Cache Valid: {debug_info.get('cache_valid')}")
            print(f"📊 Cached Trends Count: {debug_info.get('cached_trends_count')}")
            print(f"📊 Last Request: {debug_info.get('last_request_time')}")
            print(f"📊 Min Interval: {debug_info.get('min_request_interval')}s")
            
            return True
        else:
            print(f"❌ Debug endpoint failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing debug endpoint: {e}")
        return False

def test_trends_endpoint():
    """Test the Google Trends fetching endpoint"""
    print("\n" + "=" * 60)
    print("🔍 Testing Secure Trends Endpoint")
    print("=" * 60)
    
    try:
        response = requests.get(TRENDS_ENDPOINT, timeout=60)  # Longer timeout for multi-source
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Trends endpoint working!")
            print(f"📊 Status: {data.get('status')}")
            
            trending_data = data.get('trending_data', {})
            print(f"🔥 Original Trend: {trending_data.get('original_trend')}")
            print(f"✨ Spiced Story: {trending_data.get('spiced_story')[:100]}...")
            print(f"🎨 Modifier Used: {trending_data.get('modifier_used')}")
            
            return True
        else:
            print(f"❌ Trends endpoint failed: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing trends endpoint: {e}")
        return False

def test_trending_ad_generation():
    """Test the trending ad generation endpoint"""
    print("\n" + "=" * 60)
    print("🚀 Testing Secure Trending Ad Generation")
    print("=" * 60)
    
    test_payload = {
        "product": "Sustainable Coffee Maker",
        "audience": "eco-conscious coffee lovers",
        "tone": "exciting and trendy",
        "ASIN": "B08ECO123",
        "brand_text": "GreenBrew",
        "cta_text": "Brew Better!"
    }
    
    try:
        print("📤 Sending trending ad generation request...")
        start_time = time.time()
        
        response = requests.post(
            TRENDING_ENDPOINT, 
            json=test_payload,
            timeout=300  # 5 minutes timeout
        )
        
        duration = time.time() - start_time
        print(f"⏱️  Request completed in {duration:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Trending ad generation successful!")
            
            # Display ad text information
            ad_text = data.get('ad_text', {})
            print(f"\n📝 Generated Ad Text:")
            print(f"   Product: {ad_text.get('product')}")
            print(f"   Tone: {ad_text.get('tone')}")
            print(f"   Description: {ad_text.get('description', '')[:100]}...")
            print(f"   Features: {ad_text.get('features', [])}")
            print(f"   Scene: {ad_text.get('scene', '')[:100]}...")
            print(f"   Trending Topic: {ad_text.get('trending_topic')}")
            
            # Display trending metadata
            trending_data = data.get('trending_data', {})
            print(f"\n🔥 Trending Information:")
            print(f"   Original Trend: {trending_data.get('original_trend')}")
            print(f"   Topic Used: {trending_data.get('trending_topic_used')}")
            
            # Display image information
            image_url = data.get('image_url')
            if image_url:
                print(f"\n🖼️  Image URL: {image_url}")
                
            # Display post status
            post_status = data.get('post_status', {})
            print(f"\n📮 Post Status: {post_status.get('status')}")
            
            return True
            
        else:
            print(f"❌ Trending ad generation failed: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing trending ad generation: {e}")
        return False

def test_rate_limiting():
    """Test rate limiting functionality"""
    print("\n" + "=" * 60)
    print("⏱️  Testing Rate Limiting")
    print("=" * 60)
    
    try:
        print("📤 Making first trends request...")
        start_time = time.time()
        response1 = requests.get(TRENDS_ENDPOINT, timeout=30)
        duration1 = time.time() - start_time
        
        print(f"First request: {response1.status_code} in {duration1:.2f}s")
        
        print("📤 Making immediate second request...")
        start_time = time.time()
        response2 = requests.get(TRENDS_ENDPOINT, timeout=30)
        duration2 = time.time() - start_time
        
        print(f"Second request: {response2.status_code} in {duration2:.2f}s")
        
        if duration2 < 5:  # Should be fast due to caching
            print("✅ Rate limiting working - second request used cache")
            return True
        else:
            print("⚠️  Rate limiting may not be working as expected")
            return False
            
    except Exception as e:
        print(f"❌ Error testing rate limiting: {e}")
        return False

def test_security_features():
    """Test security and filtering features"""
    print("\n" + "=" * 60)
    print("🛡️  Testing Security Features")
    print("=" * 60)
    
    # This would require access to internal filtering logic
    # For now, just check that the system handles requests properly
    try:
        response = requests.get(TRENDS_ENDPOINT, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            trending_data = data.get('trending_data', {})
            trend = trending_data.get('original_trend', '').lower()
            
            # Check for sensitive keywords
            sensitive_keywords = ['war', 'death', 'violence', 'politics']
            contains_sensitive = any(keyword in trend for keyword in sensitive_keywords)
            
            if not contains_sensitive:
                print("✅ Content filtering working - no sensitive topics detected")
                return True
            else:
                print("⚠️  Sensitive content detected - filtering may need improvement")
                print(f"Trend: {trend}")
                return False
        else:
            print("❌ Could not test security features due to endpoint failure")
            return False
            
    except Exception as e:
        print(f"❌ Error testing security features: {e}")
        return False

def main():
    """Main test function"""
    print("🎯 AI Advertisement Generator - Secure Trends Integration Test")
    print("📅 Testing new secure multi-source trends system")
    print(f"🌐 Base URL: {BASE_URL}")
    
    # Test 1: Debug endpoint
    debug_working = test_trends_debug_endpoint()
    
    # Test 2: Check if trends endpoint works
    trends_working = test_trends_endpoint()
    
    # Test 3: Test rate limiting
    rate_limiting_working = test_rate_limiting()
    
    # Test 4: Test security features
    security_working = test_security_features()
    
    # Test 5: Test trending ad generation
    if trends_working:
        trending_working = test_trending_ad_generation()
    else:
        print("⚠️  Skipping trending ad test due to trends endpoint failure")
        trending_working = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SECURE TRENDS TEST SUMMARY")
    print("=" * 60)
    print(f"� Debug Endpoint: {'✅ PASS' if debug_working else '❌ FAIL'}")
    print(f"�🔍 Trends Endpoint: {'✅ PASS' if trends_working else '❌ FAIL'}")
    print(f"⏱️  Rate Limiting: {'✅ PASS' if rate_limiting_working else '❌ FAIL'}")
    print(f"🛡️  Security Features: {'✅ PASS' if security_working else '❌ FAIL'}")
    print(f"� Trending Ad Generation: {'✅ PASS' if trending_working else '❌ FAIL'}")
    
    passed_tests = sum([debug_working, trends_working, rate_limiting_working, security_working, trending_working])
    total_tests = 5
    
    print(f"\n📊 Overall Score: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests >= 4:
        print("\n🎉 Secure trends system is working well!")
        print("💡 API endpoints available:")
        print("   GET  /trends - Get current trends")
        print("   POST /run/trending - Generate trending ads")
        print("   GET  /trends/debug - Debug information")
    elif passed_tests >= 2:
        print("\n⚠️  Trends system partially working")
        print("💡 Basic functionality available, some features may need attention")
    else:
        print("\n❌ Trends system needs troubleshooting")
        print("💡 Check services: docker-compose up --build")
        print("💡 Check logs: docker-compose logs orchestrator")

if __name__ == "__main__":
    main()
