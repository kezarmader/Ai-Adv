import logging
from core.domain.entities import AdCampaign, Product, Audience, GeneratedImage, GeneratedVideo
from core.ports.inbound import AdCampaignUseCasePort
from core.ports.outbound import LLMPort, ImageGenerationPort, VideoGenerationPort, PostingPort, URLGeneratorPort

logger = logging.getLogger(__name__)

class AdCampaignUseCase(AdCampaignUseCasePort):
    """Use case for generating complete ad campaigns"""
    
    def __init__(
        self,
        llm_service: LLMPort,
        image_service: ImageGenerationPort,
        video_service: VideoGenerationPort,
        posting_service: PostingPort,
        url_generator: URLGeneratorPort,
        default_host: str = "localhost:8000"
    ):
        self.llm_service = llm_service
        self.image_service = image_service
        self.video_service = video_service
        self.posting_service = posting_service
        self.url_generator = url_generator
        self.default_host = default_host
    
    async def generate_campaign(
        self, 
        product: Product, 
        audience: Audience,
        brand_text: str = None,
        cta_text: str = None,
        host: str = None,
        generate_video: bool = True
    ) -> AdCampaign:
        """Generate a complete ad campaign"""
        
        # Use provided host or default
        actual_host = host or self.default_host
        
        logger.info("Starting ad campaign generation", extra={
            "product": product.name,
            "audience": audience.demographics,
            "tone": audience.tone,
            "host": actual_host,
            "generate_video": generate_video
        })
        
        # Step 1: Generate ad text
        ad_text = await self.llm_service.generate_ad_text(product, audience)
        logger.info("Ad text generated successfully")
        
        # Step 2: Generate image
        image_filename = await self.image_service.generate_image(ad_text, brand_text, cta_text)
        image_url = self.url_generator.generate_image_url(image_filename, actual_host)
        image = GeneratedImage(filename=image_filename, url=image_url)
        logger.info("Image generated successfully", extra={"filename": image_filename})
        
        # Step 3: Generate video (optional)
        video = None
        video_url = None
        if generate_video:
            try:
                logger.info("Starting video generation")
                video_info = await self.video_service.generate_video(
                    image_filename=image_filename,
                    scene=ad_text.scene,
                    duration_seconds=5,
                    fps=24
                )
                
                video_filename = video_info.get("filename")
                video_url = self.url_generator.generate_video_url(video_filename, actual_host)
                
                video = GeneratedVideo(
                    filename=video_filename,
                    url=video_url,
                    duration_seconds=video_info.get("duration_seconds", 5),
                    fps=video_info.get("fps", 24),
                    file_size_mb=video_info.get("file_size_mb", 0.0)
                )
                
                logger.info("Video generated successfully", extra={
                    "video_filename": video_filename,
                    "file_size_mb": video.file_size_mb
                })
                
            except Exception as e:
                logger.warning("Video generation failed, continuing without video", extra={
                    "error": str(e)
                })
                # Continue without video if generation fails
        
        # Step 4: Post advertisement
        post_status = await self.posting_service.post_advertisement(ad_text, image_url, video_url)
        logger.info("Advertisement posted", extra={"status": post_status.get("status", "unknown")})
        
        # Step 5: Create campaign entity
        campaign = AdCampaign(
            ad_text=ad_text,
            image=image,
            video=video,
            post_status=post_status
        )
        
        logger.info("Ad campaign generation completed successfully")
        return campaign
