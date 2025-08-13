from abc import ABC, abstractmethod
from typing import Dict, Any
from core.domain.entities import AdText, Product, Audience

class LLMPort(ABC):
    """Port for LLM text generation"""
    
    @abstractmethod
    async def generate_ad_text(self, product: Product, audience: Audience) -> AdText:
        """Generate advertisement text"""
        pass

class ImageGenerationPort(ABC):
    """Port for image generation"""
    
    @abstractmethod
    async def generate_image(self, ad_text: AdText, brand_text: str = None, cta_text: str = None) -> str:
        """Generate image and return filename"""
        pass
    
    @abstractmethod
    async def download_image(self, filename: str) -> bytes:
        """Download image content"""
        pass

class VideoGenerationPort(ABC):
    """Port for video generation"""
    
    @abstractmethod
    async def generate_video(self, image_filename: str, scene: str, duration_seconds: int = 5, fps: int = 24) -> Dict[str, Any]:
        """Generate video from image and return video info"""
        pass
    
    @abstractmethod
    async def download_video(self, filename: str) -> bytes:
        """Download video content"""
        pass

class PostingPort(ABC):
    """Port for posting advertisements"""
    
    @abstractmethod
    async def post_advertisement(self, ad_text: AdText, image_url: str, video_url: str = None) -> Dict[str, Any]:
        """Post advertisement and return status"""
        pass

class URLGeneratorPort(ABC):
    """Port for generating URLs"""
    
    @abstractmethod
    def generate_image_url(self, filename: str, host: str) -> str:
        """Generate external image URL"""
        pass
    
    @abstractmethod
    def generate_video_url(self, filename: str, host: str) -> str:
        """Generate external video URL"""
        pass
