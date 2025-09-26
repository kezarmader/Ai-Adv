#!/usr/bin/env python3
"""
Test video generation and download a sample video
"""

import requests
import json
import time
import os

def test_and_download_video():
    """Test video generation and download the result"""
    url = "http://madhouse53.duckdns.org/run"
    payload = {
        "asin": "B009YO1HWS",
        "generate_video": True,
        "video_animation": "zoom_pan",  # Use working animation type
        "video_duration": 3,
        "video_style": "smooth"
    }
    
    print("🎬 Generating and downloading test video...")
    print(f"📡 ASIN: {payload['asin']}")
    print(f"🎥 Animation: {payload['video_animation']}")
    
    try:
        # Generate video
        print("\n🚀 Generating video...")
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=120)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Video generated in {duration:.1f}s")
            
            if "video_url" in data:
                video_url = data["video_url"]
                print(f"🎬 Video URL: {video_url}")
                
                # Download the video
                print("\n⬇️  Downloading video...")
                video_response = requests.get(video_url)
                
                if video_response.status_code == 200:
                    # Save locally for testing
                    filename = "test_video.mp4"
                    with open(filename, "wb") as f:
                        f.write(video_response.content)
                    
                    file_size = len(video_response.content)
                    print(f"✅ Video downloaded: {filename}")
                    print(f"📦 File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
                    
                    # Check if file exists and has content
                    if os.path.exists(filename) and file_size > 0:
                        print("🎯 Video file is valid and ready to test in media player!")
                        print(f"💡 Try opening: {os.path.abspath(filename)}")
                        return True
                    else:
                        print("❌ Downloaded file is invalid")
                        return False
                else:
                    print(f"❌ Failed to download video: HTTP {video_response.status_code}")
                    return False
            else:
                print("⚠️  No video URL in response")
                return False
        else:
            print(f"❌ Failed to generate video: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"🚨 Error: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"🚨 Raw response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_and_download_video()
    if success:
        print("\n🎉 SUCCESS! Video should now play in media players.")
    else:
        print("\n💥 FAILED! Check the logs for issues.")