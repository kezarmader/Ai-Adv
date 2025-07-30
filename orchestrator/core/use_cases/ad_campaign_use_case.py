import logging
from core.domain.entities import AdCampaign, Product, Audience, GeneratedImage
from core.ports.inbound import AdCampaignUseCasePort
from core.ports.outbound import LLMPort, ImageGenerationPort, PostingPort, URLGeneratorPort

logger = logging.getLogger(__name__)

class AdCampaignUseCase(AdCampaignUseCasePort):
    """Use case for generating complete ad campaigns"""
    
    def __init__(
        self,
        llm_service: LLMPort,
        image_service: ImageGenerationPort,
        posting_service: PostingPort,
        url_generator: URLGeneratorPort,
        default_host: str = "localhost:8000"
    ):
        self.llm_service = llm_service
        self.image_service = image_service
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
        template: str = None
    ) -> AdCampaign:
        """Generate a complete ad campaign"""
        
        # Use provided host or default
        actual_host = host or self.default_host
        
        logger.info("Starting ad campaign generation", extra={
            "product": product.name,
            "audience": audience.demographics,
            "tone": audience.tone,
            "host": actual_host,
            "template": template
        })
        
        # Step 1: Generate ad text
        ad_text = await self.llm_service.generate_ad_text(product, audience, template)
        logger.info("Ad text generated successfully")
        
        # Step 2: Generate image
        image_filename = await self.image_service.generate_image(ad_text, brand_text, cta_text)
        image_url = self.url_generator.generate_image_url(image_filename, actual_host)
        image = GeneratedImage(filename=image_filename, url=image_url)
        logger.info("Image generated successfully", extra={"filename": image_filename})
        
        # Step 3: Post advertisement
        post_status = await self.posting_service.post_advertisement(ad_text, image_url)
        logger.info("Advertisement posted", extra={"status": post_status.get("status", "unknown")})
        
        # Step 4: Create campaign entity
        campaign = AdCampaign(
            ad_text=ad_text,
            image=image,
            post_status=post_status
        )
        
        logger.info("Ad campaign generation completed successfully")
        return campaign
