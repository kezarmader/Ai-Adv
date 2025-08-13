import logging
from core.ports.inbound import VideoDownloadUseCasePort
from core.ports.outbound import VideoGenerationPort

logger = logging.getLogger(__name__)

class VideoDownloadUseCase(VideoDownloadUseCasePort):
    """Use case for downloading videos"""
    
    def __init__(self, video_service: VideoGenerationPort):
        self.video_service = video_service
    
    async def download_video(self, filename: str) -> bytes:
        """Download video by filename"""
        logger.info("Downloading video", extra={"video_filename": filename})
        
        try:
            video_content = await self.video_service.download_video(filename)
            
            logger.info("Video download successful", extra={
                "video_filename": filename,
                "content_size_mb": round(len(video_content) / 1024 / 1024, 2)
            })
            
            return video_content
            
        except FileNotFoundError as e:
            logger.warning("Video not found", extra={
                "video_filename": filename,
                "error": str(e)
            })
            raise
        except Exception as e:
            logger.error("Video download failed", extra={
                "video_filename": filename,
                "error": str(e)
            })
            raise
