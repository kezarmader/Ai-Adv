import logging
import requests
from typing import Dict, Any
from core.ports.outbound import VideoGenerationPort

logger = logging.getLogger(__name__)

class VideoAdapter(VideoGenerationPort):
    """Adapter for video generation service"""
    
    def __init__(self, base_url: str = "http://video-generator:5003"):
        self.base_url = base_url

    async def generate_video(self, image_filename: str, scene: str, duration_seconds: int = 5, fps: int = 24) -> Dict[str, Any]:
        """Generate video from image and return video info"""
        try:
            logger.info("Requesting video generation", extra={
                "image_filename": image_filename,
                "scene_preview": scene[:100] + "..." if len(scene) > 100 else scene,
                "duration_seconds": duration_seconds,
                "fps": fps
            })
            
            payload = {
                "image_filename": image_filename,
                "scene": scene,
                "duration_seconds": duration_seconds,
                "fps": fps
            }
            
            response = requests.post(f"{self.base_url}/generate", json=payload, timeout=120)
            
            if response.status_code != 200:
                logger.error("Video generation failed", extra={
                    "status_code": response.status_code,
                    "response_text": response.text[:500]
                })
                raise Exception(f"Video generation failed with status {response.status_code}")
            
            video_info = response.json()
            
            logger.info("Video generation successful", extra={
                "video_filename": video_info.get("filename"),
                "file_size_mb": video_info.get("file_size_mb"),
                "duration_seconds": video_info.get("duration_seconds")
            })
            
            return video_info
            
        except requests.RequestException as e:
            logger.error("Network error during video generation", extra={"error": str(e)})
            raise Exception(f"Video generation network error: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error during video generation", extra={"error": str(e)})
            raise

    async def download_video(self, filename: str) -> bytes:
        """Download video content"""
        try:
            logger.info("Downloading video", extra={"video_filename": filename})
            
            response = requests.get(f"{self.base_url}/download/{filename}", timeout=60)
            
            if response.status_code == 404:
                logger.warning("Video not found", extra={"video_filename": filename})
                raise FileNotFoundError(f"Video not found: {filename}")
            elif response.status_code != 200:
                logger.error("Video download failed", extra={
                    "video_filename": filename,
                    "status_code": response.status_code
                })
                raise Exception(f"Video download failed with status {response.status_code}")
            
            video_content = response.content
            
            logger.info("Video download successful", extra={
                "video_filename": filename,
                "content_size_mb": round(len(video_content) / 1024 / 1024, 2)
            })
            
            return video_content
            
        except requests.RequestException as e:
            logger.error("Network error during video download", extra={
                "video_filename": filename,
                "error": str(e)
            })
            raise Exception(f"Video download network error: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error during video download", extra={
                "video_filename": filename, 
                "error": str(e)
            })
            raise
