import logging
from fastapi import Request, HTTPException
from fastapi.responses import Response
from core.domain.entities import Product, Audience
from core.ports.inbound import AdCampaignUseCasePort, ImageDownloadUseCasePort, VideoDownloadUseCasePort
from adapters.http.models import AdCampaignRequestModel, AdCampaignResponseModel

logger = logging.getLogger(__name__)

class AdCampaignController:
    """HTTP controller for ad campaign endpoints"""
    
    def __init__(
        self, 
        ad_campaign_use_case: AdCampaignUseCasePort,
        image_download_use_case: ImageDownloadUseCasePort,
        video_download_use_case: VideoDownloadUseCasePort
    ):
        self.ad_campaign_use_case = ad_campaign_use_case
        self.image_download_use_case = image_download_use_case
        self.video_download_use_case = video_download_use_case
    
    async def generate_campaign(self, request: Request) -> AdCampaignResponseModel:
        """Handle ad campaign generation request"""
        
        try:
            # Parse request
            body = await request.json()
            request_model = AdCampaignRequestModel(**body)
            
            logger.info("Ad generation request received", extra={
                "product": request_model.product,
                "audience": request_model.audience,
                "tone": request_model.tone,
                "asin": request_model.ASIN,
                "generate_video": request_model.generate_video
            })
            
            # Convert to domain entities
            product = Product(
                name=request_model.product,
                features=[],  # Will be populated by LLM
                asin=request_model.ASIN
            )
            
            audience = Audience(
                demographics=request_model.audience,
                tone=request_model.tone
            )
            
            # Get host for URL generation
            host = request.headers.get("host", "localhost:8000")
            
            # Execute use case
            campaign = await self.ad_campaign_use_case.generate_campaign(
                product=product,
                audience=audience,
                brand_text=request_model.brand_text,
                cta_text=request_model.cta_text,
                host=host,
                generate_video=request_model.generate_video
            )
            
            # Convert to response model
            response_data = {
                "ad_text": campaign.ad_text.to_dict(),
                "image_url": campaign.image.url,
                "post_status": campaign.post_status
            }
            
            # Add video information if available
            if campaign.video:
                response_data["video_url"] = campaign.video.url
                response_data["video_info"] = {
                    "duration_seconds": campaign.video.duration_seconds,
                    "fps": campaign.video.fps,
                    "file_size_mb": campaign.video.file_size_mb
                }
            
            return AdCampaignResponseModel(**response_data)
            
        except ValueError as e:
            logger.error("Validation error", extra={"error": str(e)})
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Unexpected error", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def download_image(self, filename: str, request: Request) -> Response:
        """Handle image download request"""
        
        try:
            client_ip = request.client.host if request.client else "unknown"
            logger.info("Image download request", extra={
                "filename": filename,
                "client_ip": client_ip
            })
            
            # Execute use case
            image_content = await self.image_download_use_case.download_image(filename)
            
            # Return response
            return Response(
                content=image_content,
                media_type="image/png",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Type": "image/png",
                    "Content-Length": str(len(image_content))
                }
            )
            
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Image not found or has expired")
        except Exception as e:
            logger.error("Unexpected error during image download", extra={
                "filename": filename,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(status_code=500, detail="Internal server error")

    async def download_video(self, filename: str, request: Request) -> Response:
        """Handle video download request"""
        
        try:
            client_ip = request.client.host if request.client else "unknown"
            logger.info("Video download request", extra={
                "filename": filename,
                "client_ip": client_ip
            })
            
            # Execute use case
            video_content = await self.video_download_use_case.download_video(filename)
            
            # Return response
            return Response(
                content=video_content,
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(video_content))
                }
            )
            
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Video not found or has expired")
        except Exception as e:
            logger.error("Unexpected error during video download", extra={
                "filename": filename,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(status_code=500, detail="Internal server error")
