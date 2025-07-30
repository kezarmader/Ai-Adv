from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Product:
    """Product domain entity"""
    name: str
    features: List[str]
    asin: str

@dataclass
class Audience:
    """Target audience domain entity"""
    demographics: str
    tone: str

@dataclass
class AdText:
    """Advertisement text domain entity"""
    product: str
    audience: str
    tone: str
    description: str
    features: List[str]
    scene: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for external services"""
        return {
            "product": self.product,
            "audience": self.audience,
            "tone": self.tone,
            "description": self.description,
            "features": self.features,
            "scene": self.scene
        }

@dataclass
class GeneratedImage:
    """Generated image domain entity"""
    filename: str
    url: str

@dataclass
class AdCampaign:
    """Complete ad campaign domain entity"""
    ad_text: AdText
    image: GeneratedImage
    post_status: dict
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "ad_text": self.ad_text.to_dict(),
            "image_url": self.image.url,
            "post_status": self.post_status
        }
