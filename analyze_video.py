#!/usr/bin/env python3
"""
Analyze the downloaded video file properties
"""

import os
import subprocess
import sys

def analyze_video_file(filename="test_video.mp4"):
    """Analyze video file properties using ffprobe if available"""
    
    if not os.path.exists(filename):
        print(f"❌ Video file not found: {filename}")
        return False
    
    file_size = os.path.getsize(filename)
    print(f"📁 File: {filename}")
    print(f"📦 Size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
    
    # Try to get video info using ffprobe if available
    try:
        # Check if ffprobe is available
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', filename
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            import json
            info = json.loads(result.stdout)
            
            print("\n📊 Video Analysis:")
            print("="*40)
            
            # Format info
            if 'format' in info:
                fmt = info['format']
                print(f"🎬 Format: {fmt.get('format_name', 'unknown')}")
                print(f"⏱️  Duration: {float(fmt.get('duration', 0)):.1f}s")
                print(f"📊 Bitrate: {int(fmt.get('bit_rate', 0)):,} bps")
            
            # Stream info
            if 'streams' in info:
                for stream in info['streams']:
                    if stream['codec_type'] == 'video':
                        print(f"🎥 Video Codec: {stream.get('codec_name', 'unknown')}")
                        print(f"📐 Resolution: {stream.get('width', '?')}x{stream.get('height', '?')}")
                        print(f"🎞️  Frame Rate: {stream.get('r_frame_rate', 'unknown')}")
                        print(f"🎨 Pixel Format: {stream.get('pix_fmt', 'unknown')}")
                        
                        # Check if it's the compatible format we want
                        pix_fmt = stream.get('pix_fmt', '')
                        if pix_fmt == 'yuv420p':
                            print("✅ Pixel format is compatible (yuv420p)")
                        else:
                            print(f"⚠️  Pixel format might cause issues: {pix_fmt}")
            
            return True
            
    except FileNotFoundError:
        print("⚠️  ffprobe not available - cannot analyze video details")
    except subprocess.TimeoutExpired:
        print("⚠️  ffprobe timeout")
    except Exception as e:
        print(f"⚠️  Error analyzing video: {e}")
    
    # Basic file validation
    print(f"\n📋 Basic Analysis:")
    print(f"✅ File exists and has content ({file_size} bytes)")
    
    # Check if file starts with MP4 signature
    try:
        with open(filename, 'rb') as f:
            header = f.read(12)
            if b'ftyp' in header:
                print("✅ File has MP4 signature")
            else:
                print("❌ File missing MP4 signature")
                print(f"📝 File header: {header}")
    except Exception as e:
        print(f"❌ Error reading file header: {e}")
    
    return True

def test_media_player_compatibility():
    """Suggest ways to test media player compatibility"""
    print("\n🎮 Media Player Testing Suggestions:")
    print("="*50)
    print("1. 🎬 VLC Media Player (most compatible)")
    print("2. 🎞️  Windows Media Player")
    print("3. 🌐 Browser (Chrome/Firefox)")
    print("4. 📱 Mobile device transfer test")
    print("\n💡 If video doesn't play:")
    print("   - Try VLC first (handles most formats)")
    print("   - Check if Windows has codec packs installed")
    print("   - Consider using H.264 baseline profile")

if __name__ == "__main__":
    print("🔍 Video File Analysis")
    print("="*30)
    
    success = analyze_video_file()
    if success:
        test_media_player_compatibility()
    
    print(f"\n📂 Video location: {os.path.abspath('test_video.mp4')}")