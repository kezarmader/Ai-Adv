from dataclasses import dataclass
from typing import List, Optional, Optional

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
class GeneratedVideo:
    """Generated video domain entity"""
    filename: str
    url: str
    duration_seconds: int
    fps: int
    file_size_mb: float

@dataclass
class AdCampaign:
    """Complete ad campaign domain entity"""
    ad_text: AdText
    image: GeneratedImage
    video: Optional[GeneratedVideo]
    post_status: dict
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        result = {
            "ad_text": self.ad_text.to_dict(),
            "image_url": self.image.url,
            "post_status": self.post_status
        }
        
        if self.video:
            result["video_url"] = self.video.url
            result["video_info"] = {
                "duration_seconds": self.video.duration_seconds,
                "fps": self.video.fps,
                "file_size_mb": self.video.file_size_mb
            }
            
        return result
