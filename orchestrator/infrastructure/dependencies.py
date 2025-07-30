# Dependency injection and composition root
from core.use_cases.ad_campaign_use_case import AdCampaignUseCase
from core.use_cases.image_download_use_case import ImageDownloadUseCase
from adapters.external.llm_adapter import LLMAdapter
from adapters.external.image_adapter import ImageAdapter
from adapters.external.posting_adapter import PostingAdapter
from adapters.external.url_generator_adapter import URLGeneratorAdapter
from adapters.http.controllers import AdCampaignController
from infrastructure.config import config

def setup_dependencies() -> AdCampaignController:
    """Setup dependency injection and return configured controller"""
    
    # External adapters (outbound ports)
    llm_adapter = LLMAdapter(
        llm_url=config.LLM_SERVICE_URL,
        model=config.LLM_MODEL
    )
    
    image_adapter = ImageAdapter(
        image_service_url=config.IMAGE_SERVICE_URL
    )
    
    posting_adapter = PostingAdapter(
        post_service_url=config.POST_SERVICE_URL
    )
    
    url_generator_adapter = URLGeneratorAdapter()
    
    # Use cases (application layer)
    ad_campaign_use_case = AdCampaignUseCase(
        llm_service=llm_adapter,
        image_service=image_adapter,
        posting_service=posting_adapter,
        url_generator=url_generator_adapter,
        default_host=config.DEFAULT_HOST
    )
    
    image_download_use_case = ImageDownloadUseCase(
        image_service=image_adapter
    )
    
    # HTTP controller (inbound adapter)
    controller = AdCampaignController(
        ad_campaign_use_case=ad_campaign_use_case,
        image_download_use_case=image_download_use_case
    )
    
    return controller
