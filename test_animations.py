#!/usr/bin/env python3
"""
Test different animation types to isolate the issue
"""

import requests
import json
import time

def test_animation_type(animation_type):
    """Test a specific animation type"""
    url = "http://madhouse53.duckdns.org/run"
    payload = {
        "asin": "B009YO1HWS",
        "generate_video": True,
        "video_animation": animation_type,
        "video_duration": 3,  # Shorter for faster testing
        "video_style": "smooth"
    }
    
    print(f"🎬 Testing {animation_type} animation...")
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=120)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            has_video = "video_url" in data
            status = "✅ SUCCESS" if has_video else "⚠️ NO VIDEO"
            video_url = data.get("video_url", "Not generated")
            print(f"  {status} ({duration:.1f}s) - Video: {video_url}")
            return has_video
        else:
            print(f"  ❌ FAILED ({duration:.1f}s) - HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ ERROR - {e}")
        return False

def main():
    print("🧪 Testing Different Animation Types")
    print("="*50)
    
    animation_types = [
        "zoom_pan",
        "ken_burns", 
        "parallax",
        "fade_effects",
        "ai_enhanced"
    ]
    
    results = {}
    for anim_type in animation_types:
        results[anim_type] = test_animation_type(anim_type)
        time.sleep(2)  # Brief pause between tests
    
    print("\n📊 Results Summary:")
    print("="*30)
    for anim_type, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {anim_type}")
    
    working_count = sum(results.values())
    print(f"\n🎯 {working_count}/{len(animation_types)} animation types working")

if __name__ == "__main__":
    main()