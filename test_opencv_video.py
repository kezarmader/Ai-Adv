#!/usr/bin/env python3
"""
Alternative video encoding test using OpenCV
"""

import cv2
import numpy as np
import requests
from PIL import Image
import io

def create_test_video_opencv():
    """Create a test video using OpenCV encoding which is often more compatible"""
    
    print("🎬 Creating test video with OpenCV encoding...")
    
    # Create a simple test video with OpenCV
    width, height = 1024, 1024
    fps = 30
    duration = 3  # seconds
    total_frames = fps * duration
    
    # Define codec and create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # or try 'XVID'
    out = cv2.VideoWriter('test_opencv_video.mp4', fourcc, fps, (width, height))
    
    print(f"📐 Resolution: {width}x{height}")
    print(f"🎞️  FPS: {fps}")
    print(f"⏱️  Duration: {duration}s ({total_frames} frames)")
    
    # Generate simple animated frames
    for i in range(total_frames):
        # Create a frame with some animation
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add moving circle for animation
        progress = i / total_frames
        center_x = int(width * (0.2 + 0.6 * progress))
        center_y = height // 2
        radius = 50
        color = (0, 255, 0)  # Green
        
        cv2.circle(frame, (center_x, center_y), radius, color, -1)
        
        # Add frame number text
        cv2.putText(frame, f"Frame {i+1}/{total_frames}", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        out.write(frame)
    
    # Release everything
    out.release()
    
    print("✅ OpenCV video created: test_opencv_video.mp4")
    
    # Check file size
    import os
    if os.path.exists('test_opencv_video.mp4'):
        size = os.path.getsize('test_opencv_video.mp4')
        print(f"📦 File size: {size:,} bytes ({size/1024/1024:.2f} MB)")
        return True
    else:
        print("❌ Failed to create video file")
        return False

def test_h264_codec():
    """Test H.264 codec specifically"""
    print("\n🔧 Testing H.264 codec...")
    
    width, height = 1024, 1024
    fps = 30
    
    # Try H.264 codec
    fourcc = cv2.VideoWriter_fourcc(*'H264')
    out = cv2.VideoWriter('test_h264_video.mp4', fourcc, fps, (width, height))
    
    if out.isOpened():
        print("✅ H.264 codec available")
        
        # Create a few test frames
        for i in range(30):  # 1 second
            frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            out.write(frame)
        
        out.release()
        
        import os
        if os.path.exists('test_h264_video.mp4'):
            size = os.path.getsize('test_h264_video.mp4')
            print(f"✅ H.264 video created: {size:,} bytes")
            return True
    else:
        print("❌ H.264 codec not available")
    
    return False

if __name__ == "__main__":
    print("🧪 OpenCV Video Encoding Test")
    print("="*40)
    
    # Test basic OpenCV encoding
    opencv_success = create_test_video_opencv()
    
    # Test H.264 specifically
    h264_success = test_h264_codec()
    
    print("\n📋 Summary:")
    print(f"OpenCV MP4V: {'✅' if opencv_success else '❌'}")
    print(f"OpenCV H264: {'✅' if h264_success else '❌'}")
    
    if opencv_success or h264_success:
        print("\n💡 Try playing these test videos to see if OpenCV encoding works better")
    else:
        print("\n💥 Both OpenCV methods failed - may need different approach")