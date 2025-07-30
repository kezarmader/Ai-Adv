from abc import ABC, abstractmethod
from typing import Dict, Any
from core.domain.entities import AdCampaign, Product, Audience

class AdCampaignUseCasePort(ABC):
    """Port for ad campaign use case"""
    
    @abstractmethod
    async def generate_campaign(
        self, 
        product: Product, 
        audience: Audience,
        brand_text: str = None,
        cta_text: str = None,
        host: str = None
    ) -> AdCampaign:
        """Generate a complete ad campaign"""
        pass

class ImageDownloadUseCasePort(ABC):
    """Port for image download use case"""
    
    @abstractmethod
    async def download_image(self, filename: str) -> bytes:
        """Download image by filename"""
        pass
