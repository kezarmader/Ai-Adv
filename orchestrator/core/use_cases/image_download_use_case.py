import logging
from core.ports.inbound import ImageDownloadUseCasePort
from core.ports.outbound import ImageGenerationPort

logger = logging.getLogger(__name__)

class ImageDownloadUseCase(ImageDownloadUseCasePort):
    """Use case for downloading images"""
    
    def __init__(self, image_service: ImageGenerationPort):
        self.image_service = image_service
    
    async def download_image(self, filename: str) -> bytes:
        """Download image by filename"""
        
        logger.info("Starting image download", extra={"filename": filename})
        
        try:
            image_content = await self.image_service.download_image(filename)
            logger.info("Image downloaded successfully", extra={
                "filename": filename,
                "size_bytes": len(image_content)
            })
            return image_content
            
        except Exception as e:
            logger.error("Image download failed", extra={
                "filename": filename,
                "error": str(e)
            })
            raise
