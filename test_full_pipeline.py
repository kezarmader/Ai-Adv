#!/usr/bin/env python3
"""
Test the full ASIN-to-Video pipeline
"""

import requests
import json
import time

def test_full_video_pipeline():
    """Test the complete ASIN to video generation pipeline"""
    url = "http://madhouse53.duckdns.org/run"
    payload = {
        "asin": "B009YO1HWS",
        "generate_video": True,
        "video_animation": "ai_enhanced",
        "video_duration": 5,
        "video_style": "dynamic"
    }
    
    print(f"🎬 Testing FULL AI Video Pipeline")
    print(f"📡 ASIN: {payload['asin']}")
    print(f"🎥 Animation: {payload['video_animation']}")
    print(f"⏱️  Duration: {payload['video_duration']}s")
    print(f"🎨 Style: {payload['video_style']}")
    print()
    print("🚀 Starting pipeline... (this may take a few minutes)")
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=300)  # 5 minute timeout
        duration = time.time() - start_time
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"⏱️  Total Time: {duration:.1f}s")
        
        if response.status_code == 200:
            data = response.json()
            print()
            print("🎉 FULL PIPELINE SUCCESS!")
            print("="*50)
            print(f"🏷️  Product: {data.get('ad_text', {}).get('product', 'N/A')}")
            print(f"🖼️  Image URL: {data.get('image_url', 'N/A')}")
            
            if 'video_url' in data:
                print(f"🎬 Video URL: {data['video_url']}")
                print("✅ AI-Enhanced Video Generated Successfully!")
            else:
                print("⚠️  Video not generated")
                
            features = data.get('ad_text', {}).get('features', [])
            print(f"📝 Features: {len(features)} extracted")
            for i, feature in enumerate(features[:3], 1):
                print(f"   {i}. {feature}")
                
            post_status = data.get('post_status', {})
            print(f"📤 Post Status: {post_status.get('status', 'unknown')}")
            
        else:
            print("❌ PIPELINE FAILED!")
            try:
                error_data = response.json()
                print(f"🚨 Error: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"🚨 Raw response: {response.text[:200]}")
                
    except requests.exceptions.Timeout:
        print("⏱️  TIMEOUT - Pipeline took too long (>5min)")
        print("💡 Try with shorter video duration or simpler animation")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_full_video_pipeline()